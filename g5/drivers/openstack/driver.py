"""Driver OpenStack: un proyecto Keystone por slice, una red/subred Neutron por enlace,
un puerto por NIC y una instancia Nova por VM (secuencia de LAB6 §3.5, automatizada).

Recuperación: cada recurso se anota PENDING en el diario `resources` antes del POST y se
busca por nombre antes de crearlo, así un reintento o un reinicio no duplica nada.
La segmentación la asigna Neutron (tenant_network_types vlan sobre physnet1): sin túneles.
"""
import concurrent.futures
import copy
import ipaddress
import time
import urllib.parse
from ...model import Fault, require, integer, slug, fields
from ..base import ProviderDriver
from .session import OpenStackError, Session

PRIVATE = [ipaddress.ip_network(x) for x in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
NOVA_CONSOLE = {'OpenStack-API-Version': 'compute 2.6', 'X-OpenStack-Nova-API-Version': '2.6'}
DELETE_ORDER = ('server', 'port', 'subnet', 'network', 'project')


def validate_spec(spec, config):
    require('openstack' in config, 'El proveedor OpenStack no está configurado en cluster.json')
    fields(spec, ('name', 'provider', 'networks', 'vms'), ('name', 'provider', 'networks', 'vms'))
    spec = copy.deepcopy(spec)
    slug(spec['name'])
    nets, vms = spec['networks'], spec['vms']
    require(isinstance(nets, list) and 1 <= len(nets) <= 64, 'Se requieren 1..64 redes')
    require(isinstance(vms, list) and 1 <= len(vms) <= 64, 'Se requieren 1..64 VMs')
    networks, ranges = {}, []
    for n in nets:
        fields(n, ('name', 'cidr', 'dhcp'), ('name', 'cidr'))
        slug(n['name'])
        require(n['name'] not in networks, 'Nombre de red repetido')
        try:
            net = ipaddress.IPv4Network(n['cidr'], strict=True)
        except (ValueError, TypeError):
            raise Fault('CIDR IPv4 de red inválido')
        require(16 <= net.prefixlen <= 29 and any(net.subnet_of(p) for p in PRIVATE),
                'Red privada RFC1918 con prefijo /16../29 requerida')
        require(not any(net.overlaps(r) for r in ranges), 'Subred superpuesta dentro del slice')
        n['cidr'] = str(net)
        n.setdefault('dhcp', False)
        require(type(n['dhcp']) is bool, 'dhcp debe ser booleano')
        networks[n['name']] = n
        ranges.append(net)
    ids, addresses = set(), set()
    for vm in vms:
        fields(vm, ('name', 'image', 'vcpus', 'memory_mb', 'disk_gb', 'nics'),
               ('name', 'image', 'vcpus', 'memory_mb', 'disk_gb', 'nics'))
        slug(vm['name'])
        require(vm['name'] not in ids, 'VM repetida')
        ids.add(vm['name'])
        require(isinstance(vm['image'], str) and 1 <= len(vm['image']) <= 255, 'Nombre de imagen Glance requerido')
        integer(vm['vcpus'], 1, 64, 'vcpus')
        integer(vm['memory_mb'], 64, 524288, 'memory_mb')
        integer(vm['disk_gb'], 1, 2048, 'disk_gb')
        require(isinstance(vm['nics'], list) and 1 <= len(vm['nics']) <= 8, 'Se requieren 1..8 NICs')
        attached = set()
        for nic in vm['nics']:
            fields(nic, ('network', 'ip'), ('network',))
            require(nic['network'] in networks and nic['network'] not in attached, 'Red inexistente o NIC duplicada')
            attached.add(nic['network'])
            if 'ip' in nic:
                net = ipaddress.ip_network(networks[nic['network']]['cidr'])
                try:
                    addr = ipaddress.IPv4Address(nic['ip'])
                except (ValueError, TypeError):
                    raise Fault('IP de VM inválida')
                require(net.network_address < addr < net.broadcast_address, 'IP fuera de la subred')
                require((nic['network'], addr) not in addresses, 'IP repetida en el segmento')
                addresses.add((nic['network'], addr))
                nic['ip'] = str(addr)
    return spec


class OpenStackDriver(ProviderDriver):
    name = 'openstack'

    def __init__(self, config, session=None):
        self.cfg = config
        self.os_cfg = config.get('openstack', {})
        self._session = session

    @property
    def session(self):
        if self._session is None:
            self._session = Session(self.os_cfg)
        return self._session

    def validate(self, spec):
        return validate_spec(spec, self.cfg)

    def capabilities(self):
        return {'network': ['neutron-vlan'], 'images': ['glance'], 'console': 'nova-novnc',
                'isolation': 'un proyecto Keystone por slice', 'placement': 'Nova Scheduler (VM Placement G5 en F3)'}

    def preflight(self, spec):
        # Antes de admitir: Keystone responde y cada imagen existe en Glance (rechazo sin efectos).
        for name in sorted({vm['image'] for vm in spec['vms']}):
            self.image(name)

    def inspect(self, plan, store):
        servers = {}
        for row in store.resources(plan['id']):
            if row['kind'] != 'server' or not row['external_id'] or row['status'] == 'DELETED':
                continue
            try:
                s = self.call('GET', 'compute', '/servers/' + row['external_id'])['server']
                servers[row['name']] = {'id': s['id'], 'status': s['status'], 'host': s.get('OS-EXT-SRV-ATTR:host')}
            except OpenStackError as exc:
                servers[row['name']] = {'status': 'UNKNOWN', 'error': str(exc)}
        ok = bool(servers) and all(s['status'] == 'ACTIVE' for s in servers.values())
        return {'servers': servers, 'ok': ok, 'project': plan.get('project_name'), 'simulated': False}

    # ---- admisión -------------------------------------------------------------------------
    def reserve(self, db, sid, plan):
        # Sin llamadas de red dentro de la transacción SQLite: solo se fijan nombres estables.
        short = sid[:8]
        plan['project_name'] = 'g5-' + sid
        for net in plan['networks']:
            net['os_name'] = 'g5-%s-%s' % (short, net['name'])
        for vm in plan['vms']:
            vm['os_name'] = 'g5-%s-%s' % (short, vm['name'])
            for nic in vm['nics']:
                nic['os_name'] = 'g5-%s-%s-%s' % (short, vm['name'], nic['network'])

    # ---- utilidades -----------------------------------------------------------------------
    def call(self, method, service, path, body=None, project_id=None, headers=None):
        return self.session.request(method, service, path, body, project_id, headers)[1]

    def find(self, service, path, key, scope=None, **query):
        """Busca por filtros de query; `scope` es el proyecto del token, `project_id` un filtro más."""
        items = self.call('GET', service, path + '?' + urllib.parse.urlencode(query), project_id=scope)[key]
        require(len(items) <= 1, 'Más de un recurso %s con %s' % (key, query), 409)
        return items[0] if items else None

    def ensure(self, ctx, kind, name, lookup, create):
        """Crea un recurso una sola vez: diario PENDING -> búsqueda por nombre -> POST -> CREATED."""
        row = ctx.store.resource_pending(ctx.sid, kind, name)
        found = lookup()
        if found is None:
            found = create()
            ctx.event('OS_CREATED', '%s %s' % (kind, name))
        if row['external_id'] != found['id'] or row['status'] == 'PENDING':
            ctx.store.resource_set(ctx.sid, kind, name, 'CREATED', found['id'])
        return found

    def domain_id(self):
        domain = self.find('identity', '/domains', 'domains', name=self.os_cfg.get('domain', 'Cloud'))
        require(domain, 'Dominio Keystone inexistente', 503)
        return domain['id']

    def flavor(self, vm):
        for f in self.call('GET', 'compute', '/flavors/detail')['flavors']:
            if (f['vcpus'], f['ram'], f['disk']) == (vm['vcpus'], vm['memory_mb'], vm['disk_gb']):
                return f['id']
        name = 'g5-%dc-%dm-%dg' % (vm['vcpus'], vm['memory_mb'], vm['disk_gb'])
        require(self.os_cfg.get('create_flavors', False),
                'No existe flavor %s y create_flavors está deshabilitado' % name, 409)
        body = {'flavor': {'name': name, 'vcpus': vm['vcpus'], 'ram': vm['memory_mb'], 'disk': vm['disk_gb']}}
        return self.call('POST', 'compute', '/flavors', body)['flavor']['id']

    def image(self, name):
        images = [i for i in self.call('GET', 'image', '/v2/images?' + urllib.parse.urlencode({'name': name}))['images']
                  if i['status'] == 'active']
        require(len(images) == 1, 'Imagen Glance inexistente o ambigua: ' + name, 409)
        return images[0]['id']

    def parallel(self, functions):
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.os_cfg.get('parallel_servers', 3)) as pool:
            for future in [pool.submit(fn) for fn in functions]:
                try:
                    future.result()
                except Exception as exc:
                    errors.append(exc)
        if errors:
            raise OpenStackError('; '.join(str(x) for x in errors))

    def wait_server(self, ctx, server_id, project_id, wanted):
        deadline = time.monotonic() + self.os_cfg.get('server_timeout', 300)
        while True:
            server = self.call('GET', 'compute', '/servers/' + server_id, project_id=project_id)['server']
            if server['status'] == wanted:
                return server
            require(server['status'] != 'ERROR', 'Nova marcó ERROR en %s: %s' % (
                server['name'], server.get('fault', {}).get('message', 'sin detalle')), 503)
            require(time.monotonic() < deadline, 'Timeout esperando %s en %s' % (wanted, server['name']), 503)
            ctx.wait(self.os_cfg.get('poll_interval', 2))

    # ---- despliegue -----------------------------------------------------------------------
    def deploy(self, plan, ctx):
        admin = self.session.user()
        domain = self.domain_id()
        project = self.ensure(ctx, 'project', plan['project_name'],
                              lambda: self.find('identity', '/projects', 'projects', name=plan['project_name'], domain_id=domain),
                              lambda: self.call('POST', 'identity', '/projects', {'project': {
                                  'name': plan['project_name'], 'domain_id': domain, 'description': 'G5 slice ' + plan['name']}})['project'])
        pid = project['id']
        role = self.find('identity', '/roles', 'roles', name=self.os_cfg.get('role', 'admin'))
        require(role, 'Rol Keystone inexistente', 503)
        self.call('PUT', 'identity', '/projects/%s/users/%s/roles/%s' % (pid, admin['id'], role['id']))
        ctx.event('OS_PROJECT', plan['project_name'])

        subnets = {}
        for net in plan['networks']:
            n = self.ensure(ctx, 'network', net['name'],
                            lambda: self.find('network', '/v2.0/networks', 'networks', pid, name=net['os_name'], project_id=pid),
                            lambda: self.call('POST', 'network', '/v2.0/networks', {'network': {
                                'name': net['os_name'], 'port_security_enabled': False}}, pid)['network'])
            s = self.ensure(ctx, 'subnet', net['name'],
                            lambda: self.find('network', '/v2.0/subnets', 'subnets', pid, name=net['os_name'], network_id=n['id']),
                            lambda: self.call('POST', 'network', '/v2.0/subnets', {'subnet': {
                                'name': net['os_name'], 'network_id': n['id'], 'ip_version': 4, 'cidr': net['cidr'],
                                'gateway_ip': None, 'enable_dhcp': net['dhcp']}}, pid)['subnet'])
            subnets[net['name']] = (n['id'], s['id'])
        ctx.event('OS_NETWORKS', ', '.join(sorted(subnets)))

        def server(vm):
            ports = []
            for nic in vm['nics']:
                net_id, subnet_id = subnets[nic['network']]
                body = {'port': {'name': nic['os_name'], 'network_id': net_id, 'port_security_enabled': False}}
                if 'ip' in nic:
                    body['port']['fixed_ips'] = [{'subnet_id': subnet_id, 'ip_address': nic['ip']}]
                port = self.ensure(ctx, 'port', '%s.%s' % (vm['name'], nic['network']),
                                   lambda: self.find('network', '/v2.0/ports', 'ports', pid, name=nic['os_name'], network_id=net_id),
                                   lambda: self.call('POST', 'network', '/v2.0/ports', body, pid)['port'])
                ports.append({'port': port['id']})
            image, flavor = self.image(vm['image']), self.flavor(vm)
            created = self.ensure(ctx, 'server', vm['name'],
                                  lambda: self.find('compute', '/servers', 'servers', pid, name='^%s$' % vm['os_name']),
                                  lambda: self.call('POST', 'compute', '/servers', {'server': {
                                      'name': vm['os_name'], 'imageRef': image, 'flavorRef': flavor, 'networks': ports}}, pid)['server'])
            current = self.call('GET', 'compute', '/servers/' + created['id'], project_id=pid)['server']
            if current['status'] == 'SHUTOFF':  # 'start' reutiliza deploy sobre VMs detenidas
                self.call('POST', 'compute', '/servers/%s/action' % created['id'], {'os-start': None}, pid)
            active = self.wait_server(ctx, created['id'], pid, 'ACTIVE')
            ctx.store.resource_set(ctx.sid, 'server', vm['name'], 'ACTIVE')
            placed[vm['name']] = active.get('OS-EXT-SRV-ATTR:host', '?')
        placed = {}
        self.parallel([lambda vm=vm: server(vm) for vm in plan['vms']])
        detail = ', '.join('%s@%s' % (k, placed[k]) for k in sorted(placed))
        ctx.event('OS_PLACED', detail)
        return 'Instancias ACTIVE en Nova: ' + detail

    # ---- borrado ------------------------------------------------------------------------------
    def cleanup(self, plan, ctx):
        journal = {(r['kind'], r['name']): r for r in ctx.store.resources(ctx.sid)}
        project = journal.get(('project', plan['project_name']))
        pid = project and project['external_id']
        if not pid:
            found = self.find('identity', '/projects', 'projects', name=plan['project_name'], domain_id=self.domain_id())
            pid = found and found['id']
        if not pid:
            for key, row in journal.items():
                ctx.store.resource_set(ctx.sid, key[0], key[1], 'DELETED')
            return
        lookups = {
            'server': lambda r: self.find('compute', '/servers', 'servers', name='^g5-%s-%s$' % (ctx.sid[:8], r['name']),
                                          all_tenants=1, project_id=pid),
            'port': lambda r: self.find('network', '/v2.0/ports', 'ports', name='g5-%s-%s' % (ctx.sid[:8], r['name'].replace('.', '-')), project_id=pid),
            'subnet': lambda r: self.find('network', '/v2.0/subnets', 'subnets', name='g5-%s-%s' % (ctx.sid[:8], r['name']), project_id=pid),
            'network': lambda r: self.find('network', '/v2.0/networks', 'networks', name='g5-%s-%s' % (ctx.sid[:8], r['name']), project_id=pid),
        }
        paths = {'server': ('compute', '/servers/'), 'port': ('network', '/v2.0/ports/'),
                 'subnet': ('network', '/v2.0/subnets/'), 'network': ('network', '/v2.0/networks/'),
                 'project': ('identity', '/projects/')}
        for kind in DELETE_ORDER:
            rows = [r for (k, _), r in journal.items() if k == kind and r['status'] != 'DELETED']
            if kind == 'project' and not rows:
                rows = [{'kind': 'project', 'name': plan['project_name'], 'external_id': pid}]
                ctx.store.resource_pending(ctx.sid, 'project', plan['project_name'])
            for row in rows:
                rid = row['external_id']
                if not rid and kind in lookups:
                    found = lookups[kind](row)
                    rid = found and found['id']
                if rid:
                    service, path = paths[kind]
                    try:
                        self.call('DELETE', service, path + rid)
                    except OpenStackError as exc:
                        if exc.status != 404:
                            raise
                    if kind == 'server':
                        self.wait_gone(ctx, rid)
                ctx.store.resource_set(ctx.sid, kind, row['name'], 'DELETED')
        leftovers = (self.call('GET', 'network', '/v2.0/ports?project_id=' + pid)['ports'] +
                     self.call('GET', 'network', '/v2.0/networks?project_id=' + pid)['networks'])
        require(not leftovers, 'Quedan %d recursos Neutron del proyecto %s' % (len(leftovers), pid), 503)
        ctx.event('OS_DELETED', plan['project_name'])

    def wait_gone(self, ctx, server_id):
        deadline = time.monotonic() + self.os_cfg.get('server_timeout', 300)
        while True:
            try:
                self.call('GET', 'compute', '/servers/' + server_id)
            except OpenStackError as exc:
                if exc.status == 404:
                    return
                raise
            require(time.monotonic() < deadline, 'Timeout esperando la eliminación de ' + server_id, 503)
            ctx.wait(self.os_cfg.get('poll_interval', 2))

    # ---- ciclo de vida y consola ------------------------------------------------------------
    def stop(self, plan, ctx):
        servers = {r['name']: r['external_id'] for r in ctx.store.resources(ctx.sid) if r['kind'] == 'server'}

        def stop_one(vm):
            sid = servers[vm['name']]
            if self.call('GET', 'compute', '/servers/' + sid)['server']['status'] != 'SHUTOFF':
                self.call('POST', 'compute', '/servers/%s/action' % sid, {'os-stop': None})
            self.wait_server(ctx, sid, None, 'SHUTOFF')
        self.parallel([lambda vm=vm: stop_one(vm) for vm in plan['vms']])

    def console(self, store, sid, vm_name):
        rows = [r for r in store.resources(sid) if r['kind'] == 'server' and r['name'] == vm_name]
        require(rows and rows[0]['external_id'], 'VM inexistente', 404)
        body = {'remote_console': {'protocol': 'vnc', 'type': 'novnc'}}
        url = self.call('POST', 'compute', '/servers/%s/remote-consoles' % rows[0]['external_id'], body,
                        headers=NOVA_CONSOLE)['remote_console']['url']
        for prefix, target in self.os_cfg.get('console_map', {}).items():
            if url.startswith(prefix):
                url = target.rstrip('/') + url[len(prefix):]
        return {'url': url, 'provider': 'openstack'}
