"""Driver Linux: QEMU/KVM, QCOW2, TAP, OVS y QinQ mediante el agente SSH de cada nodo.

Código trasladado sin cambios de comportamiento desde model.validate, Store.create y Engine
(EX1); solo se adaptó para recibir config/backend/contexto en lugar de leerlos de Store/Engine.
"""
import concurrent.futures
import copy
import ipaddress
import re
from ..backend import RemoteError
from ..model import Fault, require, integer, disk_bytes, slug, digest, fields, fingerprint
from .base import ProviderDriver


def validate_spec(spec, config):
    fields(spec, ('name', 'provider', 'networks', 'vms', 'publications'), ('name', 'networks', 'vms'))
    spec = copy.deepcopy(spec)
    slug(spec['name'])
    nets, vms = spec['networks'], spec['vms']
    require(isinstance(nets, list) and 1 <= len(nets) <= 64, 'Se requieren 1..64 redes')
    require(isinstance(vms, list) and 1 <= len(vms) <= 64, 'Se requieren 1..64 VMs')
    networks, ranges, cvlans = {}, [], set()
    for n in nets:
        fields(n, ('name', 'cidr', 'cvid', 'dhcp'), ('name', 'cidr', 'cvid'))
        slug(n['name'])
        require(n['name'] not in networks, 'Nombre de red repetido')
        integer(n['cvid'], 1, 4094, 'cvid')
        require(n['cvid'] not in cvlans, 'C-VLAN repetida dentro del slice')
        cvlans.add(n['cvid'])
        try:
            net = ipaddress.IPv4Network(n['cidr'], strict=True)
        except (ValueError, TypeError):
            raise Fault('CIDR IPv4 de red inválido')
        private = [ipaddress.ip_network(x) for x in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
        require(20 <= net.prefixlen <= 27 and any(net.network_address in p and net.broadcast_address in p for p in private),
                'Red privada RFC1918 con prefijo /20../27 requerida')
        forbidden = [ipaddress.ip_network(config['transit_pool'])] + [ipaddress.ip_network(x) for x in config['management_networks']]
        require(not any(net.overlaps(r) for r in ranges + forbidden), 'Subred superpuesta en slice, tránsito o gestión')
        n['cidr'] = str(net)
        n.setdefault('dhcp', True)
        require(type(n['dhcp']) is bool, 'dhcp debe ser booleano')
        networks[n['name']] = n
        ranges.append(net)
    ids, addresses = set(), set()
    for vm in vms:
        fields(vm, ('name', 'worker', 'image', 'vcpus', 'memory_mb', 'disk_gb', 'nics', 'internet', 'guest'),
               ('name', 'worker', 'image', 'vcpus', 'memory_mb', 'disk_gb', 'nics'))
        slug(vm['name'])
        require(vm['name'] not in ids, 'VM repetida')
        ids.add(vm['name'])
        require(vm['worker'] in config['workers'], 'Worker no registrado')
        digest(vm['image'])
        integer(vm['vcpus'], 1, 64, 'vcpus')
        integer(vm['memory_mb'], 128, 524288, 'memory_mb')
        disk_bytes(vm['disk_gb'], config.get('disk_unit', 'GiB'))
        vm.setdefault('internet', False)
        require(type(vm['internet']) is bool, 'internet debe ser booleano')
        require(isinstance(vm['nics'], list) and 1 <= len(vm['nics']) <= 8, 'Se requieren 1..8 NICs')
        guest = vm.get('guest')
        if guest is not None:
            fields(guest, ('os', 'username', 'password_hash', 'ssh_authorized_keys'), ('os',))
            require(guest['os'] in ('ubuntu', 'cirros'), 'SO invitado no admitido')
            if guest['os'] == 'ubuntu':
                require(isinstance(guest.get('username'), str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', guest['username']), 'Usuario Ubuntu requerido')
                require(isinstance(guest.get('password_hash'), str) and re.fullmatch(r'\$6\$[a-zA-Z0-9./]{1,16}\$[a-zA-Z0-9./]{86}', guest['password_hash']), 'Hash SHA512 crypt requerido para consola Ubuntu')
                keys = guest.get('ssh_authorized_keys', [])
                require(isinstance(keys, list) and 1 <= len(keys) <= 8, 'Indique 1..8 claves SSH públicas')
                for key in keys:
                    require(isinstance(key, str) and len(key) < 8192 and '\n' not in key and re.match(r'^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(?:256|384|521)) [A-Za-z0-9+/]+={0,3}(?: |$)', key), 'Clave SSH pública inválida')
        nic_names = [n.get('name') for n in vm['nics'] if isinstance(n, dict) and n.get('name')]
        require(len(nic_names) == len(set(nic_names)), 'Nombre de NIC repetido')
        attached = set()
        for nic in vm['nics']:
            fields(nic, ('network', 'ip', 'name'), ('network', 'ip'))
            if 'name' in nic:
                require(isinstance(nic['name'], str) and re.fullmatch(r'[a-z][a-z0-9-]{0,14}', nic['name']), 'Nombre de NIC inválido')
            require(nic['network'] in networks and nic['network'] not in attached, 'Red inexistente o NIC duplicada')
            attached.add(nic['network'])
            net = ipaddress.ip_network(networks[nic['network']]['cidr'])
            try:
                addr = ipaddress.IPv4Address(nic['ip'])
            except (ValueError, TypeError):
                raise Fault('IP de VM inválida')
            require(net.network_address + 9 < addr < net.broadcast_address, 'IP fuera del rango de hosts .10..último')
            pair = (nic['network'], str(addr))
            require(pair not in addresses, 'IP repetida en el segmento')
            addresses.add(pair)
            nic['ip'] = str(addr)
    spec.setdefault('publications', [])
    require(isinstance(spec['publications'], list) and len(spec['publications']) <= 128, 'Máximo 128 publicaciones')
    ports = set()
    for pub in spec['publications']:
        fields(pub, ('vm', 'network', 'protocol', 'external_port', 'guest_port', 'allowed_sources'),
               ('vm', 'network', 'protocol', 'external_port', 'guest_port', 'allowed_sources'))
        require(pub['vm'] in ids, 'VM publicada inexistente')
        vm = next(v for v in vms if v['name'] == pub['vm'])
        require(pub['network'] == vm['nics'][0]['network'], 'Publicar por la NIC primaria (ruta de retorno)')
        require(pub['protocol'] in ('tcp', 'udp'), 'Protocolo TCP o UDP requerido')
        integer(pub['external_port'], *config['public_port_range'], name='external_port')
        integer(pub['guest_port'], 1, 65535, 'guest_port')
        key = (pub['protocol'], pub['external_port'])
        require(key not in ports, 'Puerto publicado duplicado')
        ports.add(key)
        require(isinstance(pub['allowed_sources'], list) and 1 <= len(pub['allowed_sources']) <= 16, 'Indique 1..16 CIDR de origen')
        try:
            pub['allowed_sources'] = [str(ipaddress.IPv4Network(x, strict=True)) for x in pub['allowed_sources']]
        except (ValueError, TypeError):
            raise Fault('CIDR de origen inválido')
    return spec


class LinuxDriver(ProviderDriver):
    """Ejecución recuperable: planes inmutables, IDs estables, compensación selectiva."""
    name = 'linux'

    def __init__(self, config, backend=None):
        self.cfg, self.backend = config, backend

    def validate(self, spec):
        return validate_spec(spec, self.cfg)

    def switch(self):
        """Nombre del switch administrado, o None si el transporte de VLAN lo provee el laboratorio (fase 2)."""
        return (self.cfg.get('switch') or {}).get('name')

    def capabilities(self):
        return {'network': ['802.1ad-qinq'], 'images': ['qcow2'], 'console': 'novnc-token',
                'topologies': ['ex1', 'lineal', 'anillo'], 'placement': 'worker explícito en la solicitud'}

    def preflight(self, spec):
        targets = {v['worker'] for v in spec['vms']} | {self.cfg['gateway']['name']} | ({self.switch()} if self.switch() else set())
        for node in sorted(targets):
            report = self.backend.call(node, 'doctor')
            require(report['ok'], 'Preflight falló en ' + node + ': ' + '; '.join(report.get('problems', [])), 503)

    def inspect(self, plan, store):
        results = {}
        for node in self.participants(plan):
            try:
                results[node] = self.backend.call(node, 'inspect', sid=plan['id'])
            except Exception as exc:
                results[node] = {'ok': False, 'error': str(exc)}
        return {'nodes': results, 'simulated': self.backend.simulated}

    def reserve(self, db, sid, plan):
        used = {r[0] for r in db.execute('SELECT svid FROM leases')}
        svid = next((v for v in range(self.cfg['svid_range'][0], self.cfg['svid_range'][1] + 1) if v not in used), None)
        require(svid is not None, 'Pool de S-VLAN agotado', 409)
        used_slots = {r[0] for r in db.execute('SELECT slot FROM leases')}
        pool = ipaddress.ip_network(self.cfg['transit_pool'])
        slot = next((x for x in range(pool.num_addresses // 4) if x not in used_slots), None)
        require(slot is not None, 'Pool de tránsito agotado', 409)
        plan.update(svid=svid, transit=str(ipaddress.ip_network((int(pool.network_address) + slot * 4, 30))))
        for network in plan['networks']:
            network['gateway'] = str(ipaddress.ip_network(network['cidr']).network_address + 1)
        for vm in plan['vms']:
            worker = vm['worker']
            require(db.execute('SELECT enabled FROM nodes WHERE id=?', (worker,)).fetchone()[0], 'Worker en mantenimiento', 409)
            image = db.execute('SELECT * FROM images WHERE id=?', (vm['image'],)).fetchone()
            require(image is not None, 'Imagen no registrada: ' + vm['image'], 404)
            vm['disk_bytes'] = disk_bytes(vm['disk_gb'], self.cfg.get('disk_unit', 'GiB'))
            require(image['virtual_size'] <= vm['disk_bytes'], 'Disco menor que la imagen base', 409)
            vm['image_bytes'] = image['size']
            used_r = db.execute('SELECT COALESCE(SUM(cpu),0),COALESCE(SUM(mem),0),COALESCE(SUM(disk),0) FROM allocations WHERE worker=?', (worker,)).fetchone()
            capacity = self.cfg['workers'][worker]['capacity']
            require(all(used_r[i] + vm[k] <= capacity[k] for i, k in enumerate(('vcpus', 'memory_mb', 'disk_gb'))),
                    'Capacidad reservable insuficiente en ' + worker, 409)
            used_vnc = {r[0] for r in db.execute('SELECT vnc FROM allocations WHERE worker=?', (worker,))}
            vnc = next((p for p in range(5900, 6900) if p not in used_vnc), None)
            require(vnc is not None, 'Puertos VNC agotados', 409)
            vm['vnc'] = vnc
            for idx, nic in enumerate(vm['nics']):
                h = fingerprint([sid, vm['name'], idx])
                nic['mac'] = '02:' + ':'.join(h[i:i+2] for i in range(0, 10, 2))
            db.execute('INSERT INTO allocations VALUES(?,?,?,?,?,?,?,?)',
                       (sid, vm['name'], worker, vm['vcpus'], vm['memory_mb'], vm['disk_gb'], vm['image'], vnc))
        for pub in plan['publications']:
            require(not db.execute('SELECT 1 FROM ports WHERE protocol=? AND port=?', (pub['protocol'], pub['external_port'])).fetchone(),
                    'Puerto externo reservado', 409)
            db.execute('INSERT INTO ports VALUES(?,?,?)', (pub['protocol'], pub['external_port'], sid))
        db.execute('INSERT INTO leases VALUES(?,?,?)', (svid, sid, slot))

    def participants(self, plan):
        return sorted({v['worker'] for v in plan['vms']} | {self.cfg['gateway']['name']})

    def retry(self, node, action, ctx, **params):
        for attempt in range(self.cfg['remote_retries']):
            try:
                return self.backend.call(node, action, **params)
            except RemoteError as exc:
                ctx.event('RETRY', '%s/%s intento %s: %s' % (node, action, attempt + 1, exc))
                if attempt + 1 == self.cfg['remote_retries']:
                    raise
                ctx.wait(min(2**attempt, 8) * self.cfg.get('retry_delay', 1))

    def parallel(self, functions):
        # Esperar a TODOS antes de compensar: una tarea tardía no debe recrear recursos borrados.
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.cfg['parallel_nodes']) as pool:
            futures = [pool.submit(fn) for fn in functions]
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    errors.append(exc)
        if errors:
            raise RemoteError('; '.join(str(x) for x in errors))

    def deploy(self, plan, ctx):
        sid = plan['id']
        switch = self.switch()
        nodes = self.participants(plan)
        if switch:
            self.retry(switch, 'fabric_add', ctx, sid=sid, svid=plan['svid'])
        for node in nodes:
            self.retry(node, 'prepare', ctx, plan=plan)
        ctx.event('PREPARED', ','.join(nodes))

        def worker(node):
            for image in sorted({v['image'] for v in plan['vms'] if v['worker'] == node}):
                for attempt in range(self.cfg['remote_retries']):
                    try:
                        self.backend.transfer(node, image, ctx.store.directory / 'images' / (image + '.qcow2'))
                        break
                    except RemoteError as exc:
                        ctx.event('RETRY', '%s/image_receive intento %s: %s' % (node, attempt + 1, exc))
                        if attempt + 1 == self.cfg['remote_retries']:
                            raise
                        ctx.wait(min(2**attempt, 8) * self.cfg.get('retry_delay', 1))
            self.retry(node, 'network', ctx, sid=sid)
        self.parallel([lambda node=node: worker(node) for node in nodes])
        self.retry(self.cfg['gateway']['name'], 'gateway', ctx, sid=sid)
        ctx.event('NETWORK_READY', 'QinQ, DHCP y política IPv4 aplicados')

        def start(node):
            for vm in plan['vms']:
                if vm['worker'] == node:
                    self.retry(node, 'vm_ensure', ctx, sid=sid, vm_name=vm['name'])
                    if vm.get('guest', {}).get('os') == 'cirros':
                        self.retry(node, 'guest_setup', ctx, sid=sid, vm_name=vm['name'])
        self.parallel([lambda node=node: start(node) for node in sorted({v['worker'] for v in plan['vms']})])
        for node in nodes:
            result = self.retry(node, 'inspect', ctx, sid=sid)
            require(result['ok'], 'Estado real inconsistente en ' + node, 503)
        return 'QEMU y red creados; no implica que el SO invitado haya terminado de arrancar'

    def cleanup(self, plan, ctx):
        sid = plan['id']
        self.parallel([lambda node=node: self.retry(node, 'delete', ctx, sid=sid) for node in self.participants(plan)])
        if self.switch():
            self.retry(self.switch(), 'fabric_delete', ctx, sid=sid)

    def stop(self, plan, ctx):
        sid = plan['id']
        self.parallel([lambda v=v: self.retry(v['worker'], 'vm_stop', ctx, sid=sid, vm_name=v['name']) for v in plan['vms']])
