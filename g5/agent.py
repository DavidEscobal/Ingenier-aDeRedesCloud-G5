#!/usr/bin/env python3
"""Agente root de acciones cerradas. Compatible con Python 3.6 / OVS 2.9.5.

Entrada: una línea JSON; image_receive añade bytes binarios inmediatamente.
No expone un servidor ni ejecuta comandos arbitrarios recibidos por la API.
"""
import base64
import uuid
import contextlib
import fcntl
import hashlib
import ipaddress
import json
import os
import pwd
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


class AgentError(Exception):
    pass


def ensure(condition, message):
    if not condition:
        raise AgentError(message)


def run(*args, **kw):
    p = subprocess.run([str(x) for x in args], input=kw.get('input'), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=kw.get('timeout', 60), universal_newlines=True,
                       env=dict(os.environ, LC_ALL='C'), close_fds=True)
    if p.returncode and not kw.get('optional'):
        raise AgentError('%s: %s' % (' '.join(str(x) for x in args[:5]), p.stderr.strip()[-1800:]))
    return p.returncode, p.stdout.strip()


def output(*args, **kw):
    return run(*args, **kw)[1]


def atomic(path, value):
    path = Path(path)
    tmp = path.with_suffix('.part')
    with tmp.open('w') as f:
        json.dump(value, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(tmp), str(path))
    fd = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ident(s, pattern=r'[a-z][a-z0-9-]{0,31}'):
    ensure(isinstance(s, str) and re.fullmatch(pattern, s), 'Identificador inválido')
    return s


def tag(s):
    ensure(type(s) is int and 1 <= s <= 4094, 'VLAN inválida')
    return s


def inspect_image(path):
    info = json.loads(output('qemu-img', 'info', '--output=json', '-f', 'qcow2', path))
    ensure(info.get('format') == 'qcow2', 'Solo se admite QCOW2')
    ensure(not info.get('backing-filename'), 'Importar una base autónoma sin backing file')
    specific = info.get('format-specific', {}).get('data', {})
    ensure(not specific.get('data-file') and not info.get('data-file'), 'No se admiten discos con data-file externo')
    ensure(not info.get('encrypted') and not specific.get('encrypt'), 'Imagen cifrada no admitida')
    output('qemu-img', 'check', '-f', 'qcow2', path, timeout=300)
    return info


def qmp(path, command):
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(5)
    try:
        s.connect(str(path))
        f = s.makefile('rwb')
        json.loads(f.readline().decode())
        for cmd in ('qmp_capabilities', command):
            f.write((json.dumps({'execute': cmd}) + '\n').encode()); f.flush()
            while True:
                line = f.readline()
                ensure(bool(line), 'QMP desconectado')
                response = json.loads(line.decode())
                if 'return' in response:
                    break
                ensure('error' not in response, str(response.get('error')))
        return response['return']
    finally:
        s.close()


def serial_execute(path, command, username, password, timeout=180):
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    sock.settimeout(1)
    sock.connect(path)
    deadline=time.monotonic()+timeout
    buf=''; last=time.monotonic(); auth=0
    sock.sendall(b'\n')
    try:
        while time.monotonic()<deadline:
            try:data=sock.recv(65536)
            except socket.timeout:data=b''
            if data:buf+=data.decode(errors='replace').replace('\r','')
            if re.search(r'(?m)^[^\n]*login:\s*$',buf):
                if auth>=3:raise RuntimeError('No se pudo autenticar en la consola.')
                sock.sendall((username+'\n').encode());buf='';auth+=1
            elif re.search(r'(?im)^password:\s*$',buf):
                sock.sendall((password+'\n').encode());buf=''
            elif re.search(r'(?m)^[^\n]*[$#][ \t]*$',buf):
                break
            if time.monotonic()-last>8:
                sock.sendall(b'\n');last=time.monotonic()
        else:raise RuntimeError('Consola no reconocida. Ultima respuesta: ' + repr(buf[-3000:]))
        token=uuid.uuid4().hex
        begin='BEGIN_'+token; end='END_'+token
        encoded=base64.b64encode(command.encode()).decode()
        remote='/tmp/tel141-'+token+'.b64'
        tag='PAYLOAD_'+token
        lines=[f"cat > {remote} <<'{tag}'"]
        lines += [encoded[i:i+120] for i in range(0,len(encoded),120)]
        lines += [tag, f'echo; echo {begin}; base64 -d {remote} | sh; rc=$?; rm -f {remote}; echo; echo "{end}=$rc"']
        for line in lines:
            sock.sendall((line+'\n').encode())
            time.sleep(0.03)
        buf=''
        while time.monotonic()<deadline:
            try:data=sock.recv(65536)
            except socket.timeout:continue
            if not data:raise RuntimeError('QEMU cerro la consola.')
            buf+=data.decode(errors='replace').replace('\r','')
            match=re.search(r'(?m)^'+end+r'=(\d+)\s*$',buf)
            start=re.search(r'(?m)^'+begin+r'\s*\n',buf)
            if match and start:
                return int(match.group(1)),buf[start.end():match.start()]
        raise RuntimeError('La orden del invitado no termino dentro del plazo. Ultima salida: ' + repr(buf[-6000:]))
    finally:sock.close()


def cloud_documents(plan, vm, mtu):
    guest = vm['guest']
    user = {'name': guest['username'], 'shell': '/bin/bash', 'groups': ['sudo'],
            'sudo': 'ALL=(ALL) NOPASSWD:ALL', 'lock_passwd': False,
            'passwd': guest['password_hash'], 'ssh_authorized_keys': guest['ssh_authorized_keys']}
    data = {'hostname': vm['name'], 'manage_etc_hosts': True, 'users': [user],
            'ssh_pwauth': False, 'disable_root': True, 'chpasswd': {'expire': False},
            'package_update': False, 'package_upgrade': False,
            'write_files': [{'path': '/etc/sysctl.d/99-ex1-no-forward.conf',
                             'content': 'net.ipv4.ip_forward=0\nnet.ipv6.conf.all.forwarding=0\n'}],
            'runcmd': [['sysctl', '-p', '/etc/sysctl.d/99-ex1-no-forward.conf'],
                       ['systemctl', 'enable', '--now', 'ssh'],
                       ['systemctl', 'enable', '--now', 'getty@tty1.service']]}
    network = {'version': 2, 'ethernets': {}}
    for idx, nic in enumerate(vm['nics']):
        net = next(n for n in plan['networks'] if n['name'] == nic['network'])
        name = nic.get('name', 'eth' + str(idx))
        cfg = {'match': {'macaddress': nic['mac']}, 'set-name': name,
               'dhcp4': False, 'dhcp6': False, 'accept-ra': False, 'optional': True,
               'mtu': mtu, 'addresses': [nic['ip'] + '/' + net['cidr'].split('/')[1]]}
        if idx == 0 and (vm['internet'] or any(p['vm'] == vm['name'] for p in plan['publications'])):
            cfg['gateway4'] = net['gateway']
            cfg['nameservers'] = {'addresses': ['8.8.8.8']}
        network['ethernets'][name] = cfg
    return {'user-data': '#cloud-config\n' + json.dumps(data, indent=2) + '\n',
            'meta-data': json.dumps({'instance-id': plan['id'] + '-' + vm['name'], 'local-hostname': vm['name']}),
            'network-config': json.dumps(network, indent=2)}


class Agent:
    def __init__(self, cfg):
        self.cfg = cfg
        self.root = Path(cfg.get('state_dir', '/var/lib/g5-cluster'))
        for name in ('slices', 'vms', 'images', 'locks', 'switch', 'tombstones'):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def lock(self, name):
        with (self.root / 'locks' / (name + '.lock')).open('a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def manifest_path(self, sid):
        ident(sid, r'[0-9a-f]{32}')
        return self.root / 'slices' / (sid + '.json')

    def load(self, sid, allow_deleted=False):
        path = self.manifest_path(sid)
        ensure(allow_deleted or not (self.root / 'tombstones' / (sid + '.json')).exists(), 'Slice en eliminación; se rechaza un trabajo tardío')
        ensure(path.exists(), 'Slice no preparado en este nodo')
        return json.loads(path.read_text())

    def names(self, plan):
        h = plan['id'][:10]
        return {'bridge': 'g5b' + h, 'customer': 'g5c' + h, 'provider': 'g5p' + h,
                'ns': 'g5n' + h, 'wan': 'g5w' + h}

    def vm_dir(self, sid, name):
        ident(name)
        ident(sid, r'[0-9a-f]{32}')
        return self.root / 'vms' / (sid + '-' + name)

    def vm_token(self, plan, vm):
        return 'g5-' + plan['id'] + '-' + vm['name']

    def tap(self, plan, vm, index):
        return 'g5t' + hashlib.sha256((plan['id'] + vm['name'] + str(index)).encode()).hexdigest()[:11]

    def local_vms(self, plan):
        return [v for v in plan['vms'] if v['worker'] == self.cfg['name']]

    def owned_ovs(self, table, name, sid):
        rc, _ = run('ovs-vsctl', 'list', table, name, optional=True)
        if rc == 0:
            rc, value = run('ovs-vsctl', 'get', table, name, 'external_ids:g5_slice', optional=True)
            ensure(rc == 0 and value.strip('"') == sid, 'Recurso OVS ajeno: ' + name)

    def doctor(self, **_):
        problems = []
        for binary in ('ip', 'ovs-vsctl', 'ovs-ofctl', 'python3'):
            if not shutil.which(binary):
                problems.append('Falta ' + binary)
        if self.cfg['role'] == 'worker':
            for binary in ('qemu-img', 'qemu-system-x86_64', 'genisoimage'):
                if not shutil.which(binary):
                    problems.append('Falta ' + binary)
            if not os.access('/dev/kvm', os.R_OK | os.W_OK):
                problems.append('/dev/kvm no disponible')
        if self.cfg['role'] == 'gateway':
            for binary in ('dnsmasq', 'iptables', 'iptables-restore'):
                if not shutil.which(binary):
                    problems.append('Falta ' + binary)
        mem = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            k, v = line.split(':', 1); mem[k] = int(v.split()[0])
        try:
            version = output('ovs-vsctl', '--version').splitlines()[0]
            v = re.search(r'(\d+)\.(\d+)', version)
            if not v or tuple(map(int, v.groups())) < (2, 8):
                problems.append('Se requiere OVS >= 2.8 para QinQ')
            bridge = self.cfg['bridge']
            management = self.cfg['management_interface']
            management_addresses = output('ip', '-o', '-4', 'addr', 'show', 'dev', management).split()
            if not any(x.split('/')[0] == self.cfg['host'] for x in management_addresses):
                problems.append('IP de gestión no coincide en ' + management)
            if management in self.cfg['data_ports']:
                problems.append('La interfaz de gestión no puede ser un puerto de datos')
            if self.cfg['role'] == 'gateway':
                external = output('ip', '-o', '-4', 'addr', 'show', 'dev', self.cfg['external_interface']).split()
                if not any(x.split('/')[0] == self.cfg['external_ip'] for x in external):
                    problems.append('external_ip no está asignada a external_interface')
            if output('ovs-vsctl', 'get-controller', bridge, optional=True):
                problems.append('Bridge de transporte con controlador externo')
            for iface in self.cfg['data_ports']:
                rc, _ = run('ip', 'link', 'show', 'dev', iface, optional=True)
                if rc:
                    problems.append('Interfaz no encontrada: ' + iface)
                if output('ip', '-o', 'addr', 'show', 'dev', iface, 'scope', 'global'):
                    problems.append('Interfaz de datos con dirección IP: ' + iface)
        except Exception as exc:
            version = 'unknown'; problems.append(str(exc))
        return {'node': self.cfg['name'], 'ok': not problems, 'problems': problems,
                'timestamp': time.time(), 'ovs': version, 'cpus': os.cpu_count(),
                'memory_available_mb': mem.get('MemAvailable', mem['MemFree']) // 1024,
                'memory_total_mb': mem['MemTotal'] // 1024,
                'disk_free_gb': shutil.disk_usage(str(self.root)).free // 1024**3,
                'load': list(os.getloadavg())}

    def bootstrap(self, **_):
        report = self.doctor()
        ensure(report['ok'], '; '.join(report['problems']))
        with self.lock('fabric'):
            bridge = self.cfg['bridge']
            for iface in self.cfg['data_ports']:
                current = output('ovs-vsctl', 'iface-to-br', iface, optional=True)
                ensure(not current or current == bridge, iface + ' está en otro bridge: ' + current)
            output('ovs-vsctl', '--may-exist', 'add-br', bridge)
            ensure(not output('ovs-vsctl', 'get-controller', bridge), 'No modificar un bridge controlado externamente')
            output('ovs-vsctl', 'set', 'Open_vSwitch', '.', 'other_config:vlan-limit=2')
            for iface in self.cfg['data_ports']:
                output('ovs-vsctl', '--may-exist', 'add-port', bridge, iface)
                ensure(output('ovs-vsctl', 'get', 'Port', iface, 'tag') == '[]', 'Puerto físico en modo access')
                mode = output('ovs-vsctl', 'get', 'Port', iface, 'vlan_mode').strip('"')
                ensure(mode in ('[]', 'trunk'), 'Modo físico no compatible')
                output('ovs-vsctl', 'set', 'Port', iface, 'vlan_mode=trunk')
                output('ip', 'link', 'set', iface, 'mtu', str(self.cfg['underlay_mtu']), 'up')
            output('ip', 'link', 'set', bridge, 'up')
            ensure('NORMAL' in output('ovs-ofctl', 'dump-flows', bridge), 'El transporte debe conmutar con NORMAL')
            if self.cfg['role'] == 'gateway':
                output('sysctl', '-w', 'net.ipv4.ip_forward=1')
            atomic(self.root / 'bootstrap.json', {'time': time.time(), 'bridge': bridge})
        return report

    def fabric_add(self, sid, svid, **_):
        ident(sid, r'[0-9a-f]{32}'); tag(svid)
        ensure(not (self.root / 'tombstones' / (sid + '.json')).exists(), 'Slice ya retirado')
        ensure((self.root / 'bootstrap.json').exists(), 'Ejecute bootstrap antes de desplegar')
        path = self.root / 'switch' / (sid + '.json')
        with self.lock('fabric'):
            record = json.loads(path.read_text()) if path.exists() else {'svid': svid, 'added': []}
            ensure(record['svid'] == svid, 'SVID no coincide')
            for iface in self.cfg['data_ports']:
                trunks = json.loads(output('ovs-vsctl', 'get', 'Port', iface, 'trunks'))
                if isinstance(trunks, int):
                    trunks = [trunks]
                if trunks and svid not in trunks:
                    if iface not in record['added']:
                        record['added'].append(iface)
                        atomic(path, record)  # registrar antes del efecto remoto
                    output('ovs-vsctl', 'add', 'Port', iface, 'trunks', str(svid))
            atomic(path, record)
        return record

    def fabric_delete(self, sid, **_):
        ident(sid, r'[0-9a-f]{32}')
        atomic(self.root / 'tombstones' / (sid + '.json'), {'deleted_at': time.time()})
        path = self.root / 'switch' / (sid + '.json')
        with self.lock('fabric'):
            if path.exists():
                record = json.loads(path.read_text())
                for iface in record['added']:
                    output('ovs-vsctl', 'remove', 'Port', iface, 'trunks', str(record['svid']))
                path.unlink()
        return {'deleted': True}

    def prepare(self, plan, **_):
        # La configuración del nodo es root-owned. El plan no decide rutas ni interfaces físicas.
        path = self.manifest_path(plan['id'])
        ensure(not (self.root / 'tombstones' / (plan['id'] + '.json')).exists(), 'Slice ya retirado; no reutilizar ID')
        tag(plan['svid'])
        ensure(1 <= len(plan['networks']) <= 64 and 1 <= len(plan['vms']) <= 64, 'Plan demasiado grande')
        for n in plan['networks']:
            ident(n['name']); tag(n['cvid']); ipaddress.IPv4Network(n['cidr'])
            ipaddress.IPv4Address(n['gateway'])
        ipaddress.IPv4Network(plan['transit'])
        for vm in plan['vms']:
            ident(vm['name']); ident(vm['worker']); ident(vm['image'], r'[0-9a-f]{64}')
            ensure(all(type(vm[x]) is int and vm[x] > 0 for x in ('memory_mb', 'disk_bytes', 'vcpus', 'vnc')), 'Recursos inválidos')
            ensure(type(vm.get('image_bytes')) is int and 0 < vm['image_bytes'] <= self.cfg['max_image_gb'] * 1024**3, 'Tamaño de base inválido')
            ensure(5900 <= vm['vnc'] < 6900 and 1 <= len(vm['nics']) <= 8, 'VNC o NIC inválido')
            for nic in vm['nics']:
                ident(nic['network']); ipaddress.IPv4Address(nic['ip'])
                ident(nic['mac'], r'02(:[0-9a-f]{2}){5}')
        for pub in plan['publications']:
            ensure(pub['protocol'] in ('tcp', 'udp'), 'Protocolo inválido')
            for field in ('external_port', 'guest_port'):
                ensure(type(pub[field]) is int and 1 <= pub[field] <= 65535, 'Puerto inválido')
            for source in pub['allowed_sources']:
                ipaddress.IPv4Network(source)
        with self.lock('reservations'):
            if path.exists():
                ensure(json.loads(path.read_text()) == plan, 'El ID ya tiene otro plan')
                return {'prepared': True}
            if self.cfg['role'] == 'worker':
                all_vms = self.local_vms(plan)
                for p in (self.root / 'slices').glob('*.json'):
                    all_vms += self.local_vms(json.loads(p.read_text()))
                for key, limit in self.cfg['capacity'].items():
                    ensure(sum(v[key] for v in all_vms) <= limit, 'Capacidad local excedida: ' + key)
                report = self.doctor()
                ensure(report['ok'], '; '.join(report['problems']))
                ensure(sum(v['vcpus'] for v in all_vms) <= report['cpus'], 'vCPU comprometidas superan CPUs del worker')
                ensure(sum(v['memory_mb'] for v in all_vms) + self.cfg['memory_margin_mb'] <= report['memory_total_mb'], 'RAM comprometida supera memoria física')
                # Reservar también el crecimiento que aún no ocupa bloques en los QCOW2 existentes.
                growth = 0
                memory_growth = sum(v['memory_mb'] for v in self.local_vms(plan))
                for old in (self.root / 'slices').glob('*.json'):
                    previous = json.loads(old.read_text())
                    for v in self.local_vms(previous):
                        disk = self.vm_dir(previous['id'], v['name']) / 'disk.qcow2'
                        allocated = disk.stat().st_blocks * 512 if disk.exists() else 0
                        growth += max(0, v['disk_bytes'] - allocated)
                        pid = self.process(disk.parent, 'qemu-system', self.vm_token(previous, v))
                        resident = 0
                        if pid:
                            stat = Path('/proc/' + str(pid) + '/stat').read_text().split()
                            resident = int(stat[23]) * os.sysconf('SC_PAGE_SIZE') / 1024**2
                        memory_growth += max(0, v['memory_mb'] - resident)
                growth += sum(v['disk_bytes'] for v in self.local_vms(plan))
                ensure(report['memory_available_mb'] >= memory_growth + self.cfg['memory_margin_mb'], 'Memoria insuficiente para reservas pendientes')
                missing_images = {v['image']: v['image_bytes'] for v in all_vms if not (self.root / 'images' / (v['image'] + '.qcow2')).exists()}
                ensure(shutil.disk_usage(str(self.root)).free >= growth + sum(missing_images.values()) + self.cfg['disk_margin_gb'] * 1024**3, 'Disco insuficiente para bases pendientes y crecimiento ya reservado')
            atomic(path, plan)
        return {'prepared': True}

    def referenced_images(self):
        refs = set()
        for path in (self.root / 'slices').glob('*.json'):
            refs.update(v['image'] for v in self.local_vms(json.loads(path.read_text())))
        # Protección adicional de overlays huérfanos incluso si falta un manifiesto.
        for disk in (self.root / 'vms').glob('*/disk.qcow2'):
            info = json.loads(output('qemu-img', 'info', '--force-share', '--output=json', disk))
            base = Path(info.get('full-backing-filename', info.get('backing-filename', ''))).stem
            if re.fullmatch(r'[0-9a-f]{64}', base):
                refs.add(base)
        return refs

    def image_status(self, image, **_):
        ident(image, r'[0-9a-f]{64}')
        with self.lock('images'):
            path = self.root / 'images' / (image + '.qcow2')
            if path.exists():
                os.utime(str(path), None)
            return {'cached': path.exists(), 'size': path.stat().st_size if path.exists() else 0}

    def cache_gc(self, all_unused=False, required_bytes=0, **_):
        with self.lock('reservations'), self.lock('images'):
            return self._gc(all_unused, required_bytes)

    def _gc(self, all_unused=False, required_bytes=0, candidates=None):
        refs = self.referenced_images()
        files = sorted((self.root / 'images').glob('*.qcow2'), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        removed = []
        budget = self.cfg['cache_max_gb'] * 1024**3
        for path in files:
            enough = (total + required_bytes <= budget and
                      shutil.disk_usage(str(self.root)).free >= required_bytes + self.cfg['disk_margin_gb'] * 1024**3)
            if enough and not all_unused:
                break
            if path.stem not in refs and (candidates is None or path.stem in candidates):
                total -= path.stat().st_size
                removed.append(path.stem); path.unlink()
        ensure(total + required_bytes <= budget, 'Caché llena de imágenes referenciadas; aumente cache_max_gb')
        return {'removed': removed, 'bytes': total, 'pinned': sorted(refs)}

    def image_receive(self, image, size, stream=None, **_):
        ident(image, r'[0-9a-f]{64}')
        ensure(type(size) is int and 0 < size <= self.cfg['max_image_gb'] * 1024**3, 'Tamaño de imagen no admitido')
        dest = self.root / 'images' / (image + '.qcow2')
        with self.lock('reservations'), self.lock('images'):
            if dest.exists():
                # Dos operaciones pueden haber observado un cache miss antes de esta exclusión.
                # Consumir/verificar el segundo envío sin necesitar otra copia temporal de la base.
                h, remaining = hashlib.sha256(), size
                while remaining:
                    data = stream.read(min(1024 * 1024, remaining))
                    ensure(data, 'Transferencia incompleta')
                    h.update(data); remaining -= len(data)
                ensure(h.hexdigest() == image, 'Checksum de imagen no coincide')
                os.utime(str(dest), None)
                return {'cached': True, 'sha256': image, 'reused': True}
            self._gc(required_bytes=0 if dest.exists() else size)
            tmp = dest.with_suffix('.part')
            try:
                h, remaining = hashlib.sha256(), size
                with tmp.open('wb') as out:
                    while remaining:
                        data = stream.read(min(1024 * 1024, remaining))
                        ensure(data, 'Transferencia incompleta')
                        out.write(data); h.update(data); remaining -= len(data)
                    out.flush(); os.fsync(out.fileno())
                ensure(h.hexdigest() == image, 'Checksum de imagen no coincide')
                inspect_image(tmp)
                os.chmod(str(tmp), 0o444)
                os.replace(str(tmp), str(dest))
            finally:
                if tmp.exists():
                    tmp.unlink()
        return {'cached': True, 'sha256': image}

    def network(self, sid, **_):
        plan = self.load(sid); n = self.names(plan)
        self.fabric_add(sid, plan['svid'])
        with self.lock('fabric'):
            for table, name in (('Bridge', n['bridge']), ('Port', n['customer']), ('Port', n['provider'])):
                self.owned_ovs(table, name, sid)
            output('ovs-vsctl', '--may-exist', 'add-br', n['bridge'], '--', 'set', 'Bridge', n['bridge'],
                   'external_ids:g5_slice=' + sid)
            cvlans = ','.join(str(x['cvid']) for x in plan['networks'])
            output('ovs-vsctl', '--may-exist', 'add-port', n['bridge'], n['customer'], '--',
                   'set', 'Interface', n['customer'], 'type=patch', 'options:peer=' + n['provider'], '--',
                   'set', 'Port', n['customer'], 'vlan_mode=trunk', 'trunks=' + cvlans, 'external_ids:g5_slice=' + sid)
            output('ovs-vsctl', '--may-exist', 'add-port', self.cfg['bridge'], n['provider'], '--',
                   'set', 'Interface', n['provider'], 'type=patch', 'options:peer=' + n['customer'], '--',
                   'set', 'Port', n['provider'], 'vlan_mode=dot1q-tunnel', 'tag=' + str(plan['svid']),
                   'cvlans=' + cvlans, 'other_config:qinq-ethtype=802.1ad', 'external_ids:g5_slice=' + sid)
            output('ip', 'link', 'set', n['bridge'], 'up')
        return {'bridge': n['bridge'], 'svid': plan['svid'], 'cvids': cvlans}

    def process(self, directory, binary, token):
        path = directory / ('qemu.pid' if binary == 'qemu-system' else 'dnsmasq.pid')
        if not path.exists():
            return None
        text = path.read_text().strip()
        ensure(text.isdigit(), 'PID inválido')
        proc = Path('/proc') / text
        if not proc.exists():
            return None
        if (proc / 'stat').read_text().split()[2] == 'Z':
            return None
        args = (proc / 'cmdline').read_bytes().split(b'\0')
        exe = os.readlink(str(proc / 'exe')).split('/')[-1]
        ensure(exe.startswith(binary) and token.encode() in args, 'PID reutilizado por otro proceso')
        return int(text)

    def stop_process(self, directory, binary, token):
        pid = self.process(directory, binary, token)
        if pid:
            os.kill(pid, signal.SIGTERM)
            for _ in range(60):
                if self.process(directory, binary, token) is None:
                    return
                time.sleep(0.1)
            ensure(self.process(directory, binary, token) == pid, 'PID cambió durante detención')
            os.kill(pid, signal.SIGKILL)
            for _ in range(30):
                if self.process(directory, binary, token) is None:
                    return
                time.sleep(0.1)
            raise AgentError('No se confirmó la detención del proceso propio')

    def vm_ensure(self, sid, vm_name, **_):
        plan = self.load(sid)
        vm = next((v for v in self.local_vms(plan) if v['name'] == vm_name), None)
        ensure(vm is not None, 'VM no asignada a este worker')
        directory = self.vm_dir(sid, vm_name)
        directory.mkdir(exist_ok=True)
        token = self.vm_token(plan, vm)
        if self.process(directory, 'qemu-system', token):
            status = qmp(directory / 'qmp.sock', 'query-status')
            ensure(status['running'], 'VM existente pero detenida/pausada: revisar diagnóstico')
            return {'running': True, 'reused': True}
        for stale in ('qemu.pid', 'qmp.sock', 'serial.sock'):
            path = directory / stale
            if path.exists():
                path.unlink()
        base = self.root / 'images' / (vm['image'] + '.qcow2')
        disk = directory / 'disk.qcow2'
        with self.lock('images'):
            ensure(base.exists(), 'Imagen no transferida')
            if not disk.exists():
                tmp = directory / 'disk.part'
                if tmp.exists():
                    tmp.unlink()
                output('qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', base, tmp, str(vm['disk_bytes']))
                os.replace(str(tmp), str(disk))
            info = json.loads(output('qemu-img', 'info', '--output=json', disk))
            ensure(info.get('full-backing-filename', info.get('backing-filename')) == str(base), 'Backing file inesperado')
            user = pwd.getpwnam(self.cfg['qemu_user'])
            os.chown(str(directory), user.pw_uid, user.pw_gid); os.chmod(str(directory), 0o750)
            os.chown(str(disk), user.pw_uid, user.pw_gid); os.chmod(str(disk), 0o600)
        seed = self.cloud_seed(plan, vm, directory) if vm.get('guest', {}).get('os') == 'ubuntu' else None
        argv = ['qemu-system-x86_64', '-name', token, '-enable-kvm', '-m', str(vm['memory_mb']),
                '-smp', str(vm['vcpus']), '-drive', 'file=%s,format=qcow2,if=virtio' % disk,
                '-vnc', '127.0.0.1:%s' % (vm['vnc'] - 5900), '-monitor', 'none',
                '-qmp', 'unix:%s,server,nowait' % (directory / 'qmp.sock'),
                '-serial', 'unix:%s,server,nowait' % (directory / 'serial.sock'),
                '-daemonize', '-pidfile', str(directory / 'qemu.pid'), '-runas', self.cfg['qemu_user']]
        if seed:
            argv += ['-drive', 'file=%s,format=raw,if=ide,media=cdrom,readonly=on' % seed]
        bridge = self.names(plan)['bridge']
        with self.lock('fabric'):
            for i, nic in enumerate(vm['nics']):
                tap = self.tap(plan, vm, i)
                self.owned_ovs('Port', tap, sid)
                if run('ip', 'link', 'show', tap, optional=True)[0]:
                    output('ip', 'tuntap', 'add', 'dev', tap, 'mode', 'tap')
                    output('ip', 'link', 'set', tap, 'alias', 'g5:' + sid)
                else:
                    ensure(output('cat', '/sys/class/net/' + tap + '/ifalias') == 'g5:' + sid, 'TAP ajeno')
                net = next(x for x in plan['networks'] if x['name'] == nic['network'])
                output('ovs-vsctl', '--may-exist', 'add-port', bridge, tap, '--', 'set', 'Port', tap,
                       'vlan_mode=access', 'tag=' + str(net['cvid']), 'external_ids:g5_slice=' + sid)
                output('ip', 'link', 'set', tap, 'mtu', str(self.cfg['guest_mtu']), 'up')
                argv += ['-netdev', 'tap,id=n%s,ifname=%s,script=no,downscript=no' % (i, tap),
                         '-device', 'e1000,netdev=n%s,mac=%s' % (i, nic['mac'])]
        output(*argv, timeout=90)
        ensure(self.process(directory, 'qemu-system', token), 'QEMU no quedó activo')
        ensure(qmp(directory / 'qmp.sock', 'query-status')['running'], 'QEMU no confirmó ejecución')
        return {'running': True, 'pid': self.process(directory, 'qemu-system', token), 'worker': self.cfg['name'], 'vm': vm_name, 'vnc': vm['vnc'], 'disk': str(disk)}

    def cloud_seed(self, plan, vm, directory):
        seed = directory / 'seed.iso'
        if seed.exists():
            return seed
        documents = cloud_documents(plan, vm, self.cfg['guest_mtu'])
        staging = directory / 'seed-data'
        staging.mkdir(exist_ok=True)
        for name, value in documents.items():
            (staging / name).write_text(value)
            os.chmod(str(staging / name), 0o600)
        temp = directory / 'seed.part'
        try:
            output('genisoimage', '-quiet', '-output', temp, '-volid', 'cidata', '-joliet', '-rock',
                   *[str(staging / name) for name in ('user-data', 'meta-data', 'network-config')])
            user = pwd.getpwnam(self.cfg['qemu_user'])
            os.chown(str(temp), user.pw_uid, user.pw_gid); os.chmod(str(temp), 0o600)
            os.replace(str(temp), str(seed))
        finally:
            if temp.exists():
                temp.unlink()
            shutil.rmtree(str(staging))
        return seed

    def guest_setup(self, sid, vm_name, **_):
        plan = self.load(sid)
        vm = next((v for v in self.local_vms(plan) if v['name'] == vm_name), None)
        ensure(vm and vm.get('guest', {}).get('os') == 'cirros', 'Esta inicialización solo aplica a CirrOS')
        directory = self.vm_dir(sid, vm_name)
        pid = self.process(directory, 'qemu-system', self.vm_token(plan, vm))
        ensure(pid, 'QEMU no activo')
        marker = directory / 'guest-ready.json'
        identity = {'pid': pid, 'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'start': Path('/proc/' + str(pid) + '/stat').read_text().split()[21]}
        if marker.exists() and json.loads(marker.read_text()) == identity:
            return {'configured': True, 'reused': True}
        lines = ['set -eu', 'sudo sysctl -w net.ipv4.ip_forward=0 >/dev/null',
                 'sudo killall udhcpc 2>/dev/null || true', 'sudo ip route del default 2>/dev/null || true']
        for idx, nic in enumerate(vm['nics']):
            net = next(n for n in plan['networks'] if n['name'] == nic['network'])
            name = nic.get('name', 'eth' + str(idx))
            ident(name, r'[a-z][a-z0-9-]{0,14}')
            lines += ['dev=""; for p in /sys/class/net/*; do [ "$(cat "$p/address")" != "' + nic['mac'] + '" ] || dev=${p##*/}; done',
                      'test -n "$dev"',
                      'if [ "$dev" != "' + name + '" ]; then sudo ip link set "$dev" down; sudo ip link set "$dev" name ' + name + '; fi',
                      'sudo ip addr flush dev ' + name,
                      'sudo ip addr add ' + nic['ip'] + '/' + net['cidr'].split('/')[1] + ' dev ' + name,
                      'sudo ip link set ' + name + ' mtu ' + str(self.cfg['guest_mtu']) + ' up']
            if idx == 0 and vm['internet']:
                lines += ['sudo ip route replace default via ' + net['gateway'] + ' dev ' + name]
        rc, result = serial_execute(str(directory / 'serial.sock'), '\n'.join(lines),
                                    self.cfg['probe_user'], self.cfg['probe_password'])
        ensure(rc == 0, 'No se configuró CirrOS: ' + result[-2000:])
        atomic(marker, identity)
        return {'configured': True, 'pid': pid, 'interfaces': [n.get('name') for n in vm['nics']]}

    def inventory(self, **_):
        processes = []
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                args = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
                exe = os.readlink(str(proc / 'exe')).split('/')[-1]
                if exe.startswith('qemu-system'):
                    processes.append({'pid': int(proc.name), 'command': args})
            except (OSError, ProcessLookupError):
                pass
        images = [str(p) for p in (self.root / 'images').glob('*') if p.is_file()]
        disks = [str(p) for p in (self.root / 'vms').glob('*/*') if p.suffix in ('.qcow2', '.iso', '.part')]
        manifests = [str(p) for p in (self.root / 'slices').glob('*.json')]
        return {'node': self.cfg['name'], 'all_qemu_processes': processes,
                'managed_base_images': images, 'managed_vm_disks': disks, 'managed_manifests': manifests,
                'managed_clean': not (processes or images or disks or manifests),
                'scope': 'QEMU de todo el host; archivos solo del directorio administrado ' + str(self.root)}

    def ipt(self, table, chain, rule, namespace=None, remove=False):
        prefix = ['ip', 'netns', 'exec', namespace] if namespace else []
        args = prefix + ['iptables', '-w', '10', '-t', table]
        exists = run(*(args + ['-C', chain] + rule), optional=True)[0] == 0
        if remove and exists:
            output(*(args + ['-D', chain] + rule))
        elif not remove and not exists:
            output(*(args + ['-I', chain, '1'] + rule))

    def vm_stop(self, sid, vm_name, **_):
        plan = self.load(sid)
        vm = next((v for v in self.local_vms(plan) if v['name'] == vm_name), None)
        ensure(vm is not None, 'VM no asignada al nodo')
        directory = self.vm_dir(sid, vm_name)
        token = self.vm_token(plan, vm)
        if self.process(directory, 'qemu-system', token):
            qmp(directory / 'qmp.sock', 'system_powerdown')
            for _ in range(50):
                if not self.process(directory, 'qemu-system', token):
                    return {'stopped': True, 'forced': False}
                time.sleep(0.2)
            self.stop_process(directory, 'qemu-system', token)
            return {'stopped': True, 'forced': True}
        return {'stopped': True, 'forced': False}

    def guest_probe(self, sid, vm_name, kind='addresses', target=None, packet_bytes=56, **_):
        ensure(self.cfg.get('guest_probes', False), 'Sondeos serie deshabilitados en este nodo')
        plan = self.load(sid)
        vm = next((v for v in self.local_vms(plan) if v['name'] == vm_name), None)
        ensure(vm is not None, 'VM no pertenece al worker')
        ensure(vm.get('guest', {}).get('os', 'cirros') == 'cirros',
               'Probe serie disponible para CirrOS; para Ubuntu utilice SSH, VNC o validate_ex1.py')
        ensure(kind in ('addresses', 'ping', 'neighbors'), 'Sondeo no admitido')
        commands = {'addresses': 'ip -4 addr; ip -4 route', 'neighbors': 'ip neigh show'}
        if kind == 'ping':
            target = str(ipaddress.IPv4Address(target))
            ensure(type(packet_bytes) is int and 16 <= packet_bytes <= 1400, 'Tamaño ICMP inválido')
            command = 'ping -c 3 -W 2 -s %s %s' % (packet_bytes, target)
        else:
            command = commands[kind]
        directory = self.vm_dir(sid, vm_name)
        ensure(self.process(directory, 'qemu-system', self.vm_token(plan, vm)), 'VM detenida')
        rc, text = serial_execute(str(directory / 'serial.sock'), command,
                                  self.cfg['probe_user'], self.cfg['probe_password'])
        return {'returncode': rc, 'stdout': text[-16000:], 'kind': kind, 'target': target}

    def firewall_plan(self, plan):
        n = self.names(plan); h = plan['id'][:10]
        subnet = ipaddress.ip_network(plan['transit'])
        hostip, wanip = str(subnet.network_address + 1), str(subnet.network_address + 2)
        ext = self.cfg['external_interface']; public = self.cfg['external_ip']
        chains = {'filter': 'G5F' + h, 'nat': 'G5N' + h}
        hooks = [('filter', 'FORWARD', ['-i', n['wan'], '-j', chains['filter']]),
                 ('filter', 'FORWARD', ['-o', n['wan'], '-j', chains['filter']]),
                 ('filter', 'INPUT', ['-i', n['wan'], '-j', 'DROP']),
                 ('filter', 'INPUT', ['-i', n['wan'], '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT']),
                 ('nat', 'PREROUTING', ['-i', ext, '-d', public, '-j', chains['nat']]),
                 ('nat', 'OUTPUT', ['-d', public, '-j', chains['nat']]),
                 ('nat', 'POSTROUTING', ['-s', wanip + '/32', '-o', ext, '-m', 'comment', '--comment', 'g5:' + plan['id'], '-j', 'MASQUERADE'])]
        rules = {'filter': [], 'nat': []}
        f = rules['filter']
        f.append(['-m', 'conntrack', '--ctstate', 'INVALID', '-j', 'DROP'])
        f.append(['-i', ext, '-o', n['wan'], '-d', wanip, '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
        f.append(['-i', n['wan'], '-s', wanip, '-o', ext, '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
        for pub in plan['publications']:
            for src in pub['allowed_sources']:
                rules['nat'].append(['-s', src, '-p', pub['protocol'], '--dport', str(pub['external_port']), '-j', 'DNAT', '--to-destination', wanip + ':' + str(pub['external_port'])])
                f.append(['-i', ext, '-o', n['wan'], '-d', wanip, '-s', src, '-p', pub['protocol'], '--dport', str(pub['external_port']), '-m', 'conntrack', '--ctstate', 'NEW', '-j', 'ACCEPT'])
        for cidr in self.cfg['blocked_egress']:
            f.append(['-i', n['wan'], '-d', cidr, '-j', 'DROP'])
        if any(v['internet'] for v in plan['vms']):
            f.append(['-i', n['wan'], '-s', wanip, '-o', ext, '-j', 'ACCEPT'])
        f.append(['-j', 'DROP'])
        return hostip, wanip, chains, hooks, rules

    def gateway(self, sid, **_):
        ensure(self.cfg['role'] == 'gateway', 'Nodo no es gateway')
        plan = self.load(sid); n = self.names(plan)
        ns = n['ns']; directory = self.root / 'slices' / sid
        directory.mkdir(exist_ok=True)
        namespaces = [x.split()[0] for x in output('ip', 'netns', 'list').splitlines()]
        if ns not in namespaces:
            output('ip', 'netns', 'add', ns)
        hostip, wanip, chains, hooks, rules = self.firewall_plan(plan)
        with self.lock('fabric'):
            self.ensure_veth(sid, n['wan'], 'g5u' + sid[:10], ns, 'wan0')
            output('ip', 'addr', 'replace', hostip + '/30', 'dev', n['wan'])
            output('ip', 'link', 'set', n['wan'], 'up')
            output('ip', '-n', ns, 'addr', 'replace', wanip + '/30', 'dev', 'wan0')
            output('ip', '-n', ns, 'link', 'set', 'wan0', 'up')
            output('ip', '-n', ns, 'link', 'set', 'lo', 'up')
            output('ip', '-n', ns, 'route', 'replace', 'default', 'via', hostip)
            for idx, net in enumerate(plan['networks']):
                port, local = 'g5g' + sid[:8] + str(idx), 'lan' + str(idx)
                self.owned_ovs('Port', port, sid)
                self.ensure_veth(sid, port, 'g5l' + sid[:8] + str(idx), ns, local)
                output('ovs-vsctl', '--may-exist', 'add-port', n['bridge'], port, '--', 'set', 'Port', port,
                       'tag=' + str(net['cvid']), 'vlan_mode=access', 'external_ids:g5_slice=' + sid)
                output('ip', 'link', 'set', port, 'mtu', str(self.cfg['guest_mtu']), 'up')
                output('ip', '-n', ns, 'addr', 'replace', net['gateway'] + '/' + net['cidr'].split('/')[1], 'dev', local)
                output('ip', '-n', ns, 'link', 'set', local, 'mtu', str(self.cfg['guest_mtu']), 'up')
        output('ip', 'netns', 'exec', ns, 'sysctl', '-w', 'net.ipv4.ip_forward=1')
        # El namespace es exclusivo del slice. Política cerrada antes de activar publicación.
        for chain in ('INPUT', 'FORWARD'):
            output('ip', 'netns', 'exec', ns, 'iptables', '-P', chain, 'DROP')
        for table in ('filter', 'nat'):
            output('ip', 'netns', 'exec', ns, 'iptables', '-t', table, '-F')
        def add(chain, *rule, **kw):
            output('ip', 'netns', 'exec', ns, 'iptables', '-t', kw.get('table', 'filter'), '-A', chain, *rule)
        add('INPUT', '-i', 'lo', '-j', 'ACCEPT')
        add('INPUT', '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT')
        add('FORWARD', '-m', 'conntrack', '--ctstate', 'INVALID', '-j', 'DROP')
        add('FORWARD', '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT')
        for idx, net in enumerate(plan['networks']):
            local = 'lan' + str(idx)
            add('INPUT', '-i', local, '-p', 'icmp', '-j', 'ACCEPT')
            if net['dhcp']:
                add('INPUT', '-i', local, '-p', 'udp', '--dport', '67', '-j', 'ACCEPT')
            for vm in plan['vms']:
                nic = vm['nics'][0]
                if nic['network'] == net['name'] and vm['internet']:
                    add('FORWARD', '-i', local, '-s', nic['ip'], '-o', 'wan0', '-j', 'ACCEPT')
                    add('POSTROUTING', '-s', nic['ip'], '-o', 'wan0', '-j', 'MASQUERADE', table='nat')
        for pub in plan['publications']:
            vm = next(v for v in plan['vms'] if v['name'] == pub['vm'])
            nic = vm['nics'][0]
            idx = next(i for i, net in enumerate(plan['networks']) if net['name'] == nic['network'])
            for src in pub['allowed_sources']:
                add('PREROUTING', '-i', 'wan0', '-s', src, '-p', pub['protocol'], '--dport', str(pub['external_port']),
                    '-j', 'DNAT', '--to-destination', nic['ip'] + ':' + str(pub['guest_port']), table='nat')
                add('FORWARD', '-i', 'wan0', '-o', 'lan' + str(idx), '-s', src, '-d', nic['ip'], '-p', pub['protocol'],
                    '--dport', str(pub['guest_port']), '-j', 'ACCEPT')
        with self.lock('firewall'):
            for table, chain in chains.items():
                if run('iptables', '-w', '10', '-t', table, '-S', chain, optional=True)[0]:
                    output('iptables', '-w', '10', '-t', table, '-N', chain)
                # COMMIT atómico de la cadena exclusiva; --noflush conserva el firewall ajeno.
                lines = ['*' + table, ':' + chain + ' - [0:0]', '-F ' + chain]
                lines += ['-A ' + chain + ' ' + ' '.join(shlex.quote(x) for x in rule) for rule in rules[table]]
                lines += ['COMMIT', '']
                output('iptables-restore', '--noflush', '-w', '10', input='\n'.join(lines))
            for table, chain, rule in hooks:
                self.ipt(table, chain, rule)
        conf = directory / 'dnsmasq.conf'
        lines = ['port=0', 'bind-interfaces', 'dhcp-authoritative', 'user=root',
                 'pid-file=' + str(directory / 'dnsmasq.pid'),
                 'dhcp-leasefile=' + str(directory / 'leases'), 'log-facility=' + str(directory / 'dnsmasq.log')]
        active = False
        for idx, net in enumerate(plan['networks']):
            if not net['dhcp']:
                continue
            active = True
            subnet = ipaddress.ip_network(net['cidr'])
            lines += ['interface=lan' + str(idx),
                      'dhcp-range=set:n%s,%s,static,%s,12h' % (idx, subnet.network_address, subnet.netmask),
                      'dhcp-option=tag:n%s,3,%s' % (idx, net['gateway']),
                      'dhcp-option=tag:n%s,6,%s' % (idx, self.cfg['dns_server']),
                      'dhcp-option=tag:n%s,26,%s' % (idx, self.cfg['guest_mtu'])]
            for vm in plan['vms']:
                for nic in vm['nics']:
                    if nic['network'] == net['name']:
                        lines.append('dhcp-host=%s,%s,%s,12h' % (nic['mac'], nic['ip'], vm['name']))
        self.stop_process(directory, 'dnsmasq', '--conf-file=' + str(conf))
        if active:
            conf.write_text('\n'.join(lines) + '\n')
            output('dnsmasq', '--test', '--conf-file=' + str(conf))
            output('ip', 'netns', 'exec', ns, 'dnsmasq', '--conf-file=' + str(conf))
        return {'namespace': ns, 'dhcp': active, 'external_ip': self.cfg['external_ip']}

    def ensure_veth(self, sid, host, peer, namespace, local):
        """Completar también un par creado antes de un corte, sin duplicarlo."""
        ledger = self.root / 'slices' / sid / ('link-' + host + '.json')
        exists = not run('ip', 'link', 'show', host, optional=True)[0]
        if not ledger.exists():
            ensure(not exists, 'veth preexistente sin registro de propiedad: ' + host)
            atomic(ledger, {'host': host, 'peer': peer, 'namespace': namespace, 'local': local})
        if not exists:
            output('ip', 'link', 'add', host, 'type', 'veth', 'peer', 'name', peer)
        alias = output('cat', '/sys/class/net/' + host + '/ifalias')
        ensure(alias in ('', 'g5:' + sid), 'veth pertenece a otro slice')
        output('ip', 'link', 'set', host, 'alias', 'g5:' + sid)
        if not run('ip', 'link', 'show', peer, optional=True)[0]:
            output('ip', 'link', 'set', peer, 'netns', namespace)
        if not run('ip', '-n', namespace, 'link', 'show', peer, optional=True)[0]:
            output('ip', '-n', namespace, 'link', 'set', peer, 'name', local)
        output('ip', '-n', namespace, 'link', 'show', local)

    def inspect(self, sid, **_):
        plan = self.load(sid, allow_deleted=True); n = self.names(plan)
        result = {'node': self.cfg['name'], 'vms': {}, 'time': time.time()}
        result['bridge_present'] = run('ovs-vsctl', 'br-exists', n['bridge'], optional=True)[0] == 0
        result['ports'] = output('ovs-vsctl', 'list-ports', n['bridge'], optional=True).splitlines()
        for vm in self.local_vms(plan):
            directory = self.vm_dir(sid, vm['name'])
            alive = self.process(directory, 'qemu-system', self.vm_token(plan, vm))
            record = {'pid': alive, 'running': False, 'worker': self.cfg['name'], 'vm': vm['name'],
                      'qemu_name': self.vm_token(plan, vm), 'disk_path': str(directory / 'disk.qcow2'),
                      'nics': [dict(nic, tap=self.tap(plan, vm, i)) for i, nic in enumerate(vm['nics'])]}
            disk = directory / 'disk.qcow2'
            if disk.exists():
                info = json.loads(output('qemu-img', 'info', '--force-share', '--output=json', disk))
                record['disk'] = {key: info.get(key) for key in ('format', 'virtual-size', 'actual-size', 'full-backing-filename')}
            if alive:
                record.update(qmp(directory / 'qmp.sock', 'query-status'))
                stat = Path('/proc/' + str(alive) + '/stat').read_text().split()
                record['cpu_seconds'] = (int(stat[13]) + int(stat[14])) / os.sysconf('SC_CLK_TCK')
                record['rss_mb'] = int(stat[23]) * os.sysconf('SC_PAGE_SIZE') / 1024**2
            result['vms'][vm['name']] = record
        if self.cfg['role'] == 'gateway':
            result['namespace_present'] = n['ns'] in [x.split()[0] for x in output('ip', 'netns', 'list').splitlines()]
            result['firewall'] = output('ip', 'netns', 'exec', n['ns'], 'iptables', '-S', optional=True) if result['namespace_present'] else ''
            lease = self.root / 'slices' / sid / 'leases'
            result['dhcp_leases'] = lease.read_text() if lease.exists() else ''
            if any(net['dhcp'] for net in plan['networks']):
                directory = self.root / 'slices' / sid
                result['dhcp_running'] = bool(self.process(directory, 'dnsmasq', '--conf-file=' + str(directory / 'dnsmasq.conf')))
            else:
                result['dhcp_running'] = None
        result['ok'] = result['bridge_present'] and all(v['running'] for v in result['vms'].values())
        expected_taps = [self.tap(plan, vm, i) for vm in self.local_vms(plan) for i in range(len(vm['nics']))]
        result['ok'] = result['ok'] and all(t in result['ports'] for t in expected_taps)
        if self.cfg['role'] == 'gateway':
            result['ok'] = result['ok'] and result['namespace_present'] and result['dhcp_running'] is not False
        return result

    def qinq_capture(self, **_):
        ensure(self.cfg['role'] == 'switch', 'Capturar QinQ en OFS')
        args = ['tcpdump', '-l', '-i', 'any', '-nn', '-e', '-c', '6', 'ether proto 0x88a8']
        try:
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, timeout=20)
            return {'stdout': result.stdout, 'stderr': result.stderr, 'returncode': result.returncode}
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or b''
            return {'stdout': out.decode(errors='replace') if isinstance(out, bytes) else out, 'returncode': 124}

    def delete(self, sid, **_):
        path = self.manifest_path(sid)
        atomic(self.root / 'tombstones' / (sid + '.json'), {'deleting_at': time.time()})
        if not path.exists():
            self.fabric_delete(sid)
            # Reintento tras corte entre retirar manifiesto y GC: mantener bases usadas.
            gc = self.cache_gc(all_unused=True) if self.cfg.get('gc_on_delete', True) else {'removed': []}
            return {'deleted': True, 'cache': gc}
        plan = self.load(sid, allow_deleted=True); n = self.names(plan)
        # No se liberan reservas ni se borra el manifiesto ante cualquier fallo.
        for vm in self.local_vms(plan):
            directory = self.vm_dir(sid, vm['name'])
            self.stop_process(directory, 'qemu-system', self.vm_token(plan, vm))
            for idx in range(len(vm['nics'])):
                tap = self.tap(plan, vm, idx)
                self.owned_ovs('Port', tap, sid)
                output('ovs-vsctl', '--if-exists', 'del-port', tap)
                if not run('ip', 'link', 'show', tap, optional=True)[0]:
                    ensure(output('cat', '/sys/class/net/' + tap + '/ifalias') == 'g5:' + sid, 'TAP ajeno')
                    output('ip', 'link', 'del', tap)
            with self.lock('images'):
                if directory.exists():
                    shutil.rmtree(str(directory))
        if self.cfg['role'] == 'gateway':
            directory = self.root / 'slices' / sid
            self.stop_process(directory, 'dnsmasq', '--conf-file=' + str(directory / 'dnsmasq.conf'))
            _, _, chains, hooks, _ = self.firewall_plan(plan)
            with self.lock('firewall'):
                for table, chain, rule in hooks:
                    self.ipt(table, chain, rule, remove=True)
                for table, chain in chains.items():
                    if not run('iptables', '-w', '10', '-t', table, '-S', chain, optional=True)[0]:
                        output('iptables', '-w', '10', '-t', table, '-F', chain)
                        output('iptables', '-w', '10', '-t', table, '-X', chain)
            if n['ns'] in [x.split()[0] for x in output('ip', 'netns', 'list').splitlines()]:
                ensure(not output('ip', 'netns', 'pids', n['ns']), 'Quedan procesos en el namespace')
                output('ip', 'netns', 'del', n['ns'])
            for iface in [n['wan']] + ['g5g' + sid[:8] + str(i) for i in range(len(plan['networks']))]:
                if not run('ip', 'link', 'show', iface, optional=True)[0]:
                    ensure(output('cat', '/sys/class/net/' + iface + '/ifalias') == 'g5:' + sid, 'veth ajeno')
                    output('ip', 'link', 'del', iface)
            if directory.exists():
                shutil.rmtree(str(directory))
        with self.lock('fabric'):
            self.owned_ovs('Port', n['provider'], sid)
            self.owned_ovs('Bridge', n['bridge'], sid)
            output('ovs-vsctl', '--if-exists', 'del-port', self.cfg['bridge'], n['provider'])
            output('ovs-vsctl', '--if-exists', 'del-br', n['bridge'])
        self.fabric_delete(sid)
        with self.lock('reservations'), self.lock('images'):
            path.unlink()
            gc = self._gc(all_unused=True, candidates={v['image'] for v in self.local_vms(plan)}) if self.cfg.get('gc_on_delete', True) else {'removed': []}
        return {'deleted': True, 'cache': gc}


def main():
    ensure(os.geteuid() == 0, 'El agente requiere root mediante el wrapper autorizado')
    os.umask(0o022)
    cfg = json.loads(Path('/etc/g5-cluster/node.json').read_text())
    ensure(socket.gethostname().split('.')[0].lower() == cfg['name'].lower(), 'Hostname no coincide con el inventario')
    a = Agent(cfg)
    line = sys.stdin.buffer.readline(2 * 1024 * 1024 + 1)
    ensure(len(line) <= 2 * 1024 * 1024, 'Petición demasiado grande')
    request = json.loads(line.decode())
    action = request.pop('action')
    actions = ('doctor', 'bootstrap', 'prepare', 'image_status', 'image_receive', 'cache_gc',
               'fabric_add', 'fabric_delete', 'network', 'gateway', 'vm_ensure', 'vm_stop', 'guest_setup', 'guest_probe', 'inventory', 'qinq_capture', 'inspect', 'delete')
    ensure(action in actions, 'Acción no admitida')
    if action == 'image_receive':
        request['stream'] = sys.stdin.buffer
    sid = request.get('sid') or request.get('plan', {}).get('id')
    if sid:
        ident(sid, r'[0-9a-f]{32}')
    with a.lock('slice-' + sid if sid else 'action-' + action):
        result = getattr(a, action)(**request)
    print(json.dumps({'ok': True, 'result': result}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        sys.exit(1)
