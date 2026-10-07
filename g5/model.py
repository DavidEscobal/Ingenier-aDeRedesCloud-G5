"""Validación del contrato; no se aceptan órdenes shell del cliente."""
import copy
import hashlib
import ipaddress
import json
import re
import math
from decimal import Decimal, ROUND_CEILING


class Fault(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def require(ok, message, status=400):
    if not ok:
        raise Fault(message, status)


def integer(value, lo, hi, name):
    require(type(value) is int and lo <= value <= hi, '%s: entero %s..%s' % (name, lo, hi))
    return value


def disk_bytes(value, unit='GiB'):
    require(type(value) in (int, float) and math.isfinite(value) and 1 <= value <= 2048,
            'disk_gb: número finito entre 1 y 2048 (admite 2.2)')
    require(unit in ('GB', 'GiB'), 'disk_unit debe ser GB o GiB')
    factor = 1024**3 if unit == 'GiB' else 1000**3
    return int((Decimal(str(value)) * factor / 512).to_integral_value(rounding=ROUND_CEILING)) * 512


def slug(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,31}', value), 'Identificador inválido')
    return value


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Se requiere SHA256 hexadecimal')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(obj, allowed, required=()):
    require(isinstance(obj, dict), 'Se esperaba un objeto JSON')
    require(not set(obj) - set(allowed), 'Campos desconocidos: ' + ', '.join(sorted(set(obj) - set(allowed))))
    require(set(required) <= set(obj), 'Campos obligatorios: ' + ', '.join(required))


def validate(spec, config):
    fields(spec, ('name', 'networks', 'vms', 'publications'), ('name', 'networks', 'vms'))
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
