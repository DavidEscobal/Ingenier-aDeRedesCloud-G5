"""Adaptador SSH real y doble explícito para pruebas sin infraestructura."""
import copy
import json
import subprocess
import threading
import time
from pathlib import Path
from .model import Fault, require, canonical


class RemoteError(Exception):
    pass


class SSHBackend:
    simulated = False

    def __init__(self, config):
        self.config = config
        self.nodes = dict(config['workers'])
        self.nodes[config['gateway']['name']] = config['gateway']
        self.nodes[config['switch']['name']] = config['switch']

    def ssh(self, node):
        cfg = self.nodes[node]
        return ['ssh', '-T', '-i', str(Path(self.config['ssh_key']).expanduser()),
                '-p', str(cfg.get('ssh_port', 22)), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8',
                '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=3',
                cfg.get('ssh_user', 'ubuntu') + '@' + cfg['host']]

    def call(self, node, action, **params):
        payload = canonical(dict(params, action=action)) + '\n'
        try:
            p = subprocess.run(self.ssh(node) + ['sudo -n /usr/local/sbin/g5-cluster-agent'],
                               input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RemoteError('%s/%s: timeout; se consultará el recurso antes de repetir' % (node, action))
        return self.decode(p.returncode, p.stdout, p.stderr, node, action)

    def decode(self, rc, stdout, stderr, node, action):
        try:
            data = json.loads(stdout)
        except ValueError:
            raise RemoteError('%s/%s: SSH o respuesta inválida: %s' % (node, action, stderr[-1200:]))
        if rc or not data.get('ok'):
            raise RemoteError('%s/%s: %s' % (node, action, data.get('error', stderr[-1200:])))
        return data['result']

    def transfer(self, node, image, path):
        if self.call(node, 'image_status', image=image)['cached']:
            return {'cached': True, 'reused': True}
        p = subprocess.Popen(self.ssh(node) + ['sudo -n /usr/local/sbin/g5-cluster-agent'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        timeout = threading.Timer(900, p.kill)
        timeout.start()
        try:
            try:
                p.stdin.write((canonical({'action': 'image_receive', 'image': image, 'size': path.stat().st_size}) + '\n').encode())
                with path.open('rb') as source:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        p.stdin.write(chunk)
                p.stdin.close()
            except BrokenPipeError:
                pass
            p.stdin = None
            out, err = p.communicate()
            return self.decode(p.returncode, out.decode(), err.decode(), node, 'image_receive')
        finally:
            timeout.cancel()
            if p.poll() is None:
                p.kill(); p.wait()

    def tunnel(self, node, local_port, vnc_port, ttl=120):
        command = self.ssh(node)
        target = command.pop()
        command += ['-N', '-o', 'ExitOnForwardFailure=yes', '-L',
                    '127.0.0.1:%s:127.0.0.1:%s' % (local_port, vnc_port), target]
        # El límite sobrevive a una caída del proceso API: coreutils supervisa el SSH.
        p = subprocess.Popen(['timeout', '--signal=TERM', '--kill-after=2', str(ttl)] + command,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.4)
        if p.poll() is not None:
            raise RemoteError('No se pudo abrir el túnel VNC')
        return p


class MemoryBackend:
    """Nunca se presenta como prueba de QEMU/OVS. Activar solo con --simulate."""
    simulated = True

    def __init__(self, config):
        self.config = config
        self.nodes = dict(config['workers'])
        self.nodes[config['gateway']['name']] = config['gateway']
        self.nodes[config['switch']['name']] = config['switch']
        self.resources = {}
        self.images = set()
        self.calls = []
        self.failures = {}
        self.guard = threading.RLock()

    def call(self, node, action, **params):
        with self.guard:
            self.calls.append((node, action, copy.deepcopy(params)))
            failure = (node, action)
            if self.failures.get(failure, 0):
                self.failures[failure] -= 1
                raise RemoteError('Fallo inyectado: ' + node + '/' + action)
            sid = params.get('sid', params.get('plan', {}).get('id'))
            key = (node, sid)
            if action in ('doctor', 'bootstrap'):
                return {'ok': True, 'simulated': True, 'node': node, 'timestamp': time.time(),
                        'memory_available_mb': 65536, 'memory_total_mb': 65536, 'disk_free_gb': 2048, 'cpus': 64, 'problems': []}
            if action == 'prepare':
                old = self.resources.setdefault(key, {'plan': params['plan'], 'vms': {}, 'network': False})
                require(old['plan'] == params['plan'], 'Plan ya existe', 409)
            elif action == 'network':
                self.resources[key]['network'] = True
            elif action == 'vm_ensure':
                self.resources[key]['vms'][params['vm_name']] = {'running': True, 'simulated': True}
            elif action == 'vm_stop':
                self.resources[key]['vms'][params['vm_name']] = {'running': False}
            elif action == 'delete':
                old = self.resources.pop(key, None)
                if old and self.config['common'].get('gc_on_delete', True):
                    candidates = {v['image'] for v in old['plan']['vms'] if v['worker'] == node}
                    pinned = {v['image'] for (n, _), obj in self.resources.items() if n == node for v in obj['plan']['vms'] if v['worker'] == node}
                    self.images -= {(node, im) for im in candidates - pinned}
            elif action == 'inspect':
                obj = self.resources.get(key)
                return {'ok': bool(obj and obj['network']), 'vms': obj['vms'] if obj else {}, 'simulated': True}
            elif action == 'cache_gc':
                pinned = {v['image'] for (n, _), obj in self.resources.items() if n == node for v in obj['plan']['vms'] if v['worker'] == node}
                removed = [im for n, im in self.images if n == node and im not in pinned] if params.get('all_unused') else []
                self.images -= {(node, im) for im in removed}
                return {'removed': removed, 'pinned': sorted(pinned), 'simulated': True}
            return {'ok': True, 'simulated': True}

    def transfer(self, node, image, path):
        with self.guard:
            self.images.add((node, image))
        return {'simulated': True}
