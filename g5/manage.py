"""Preparación administrativa explícita; ejecutar desde server4 como ubuntu."""
import argparse
import hashlib
import json
import os
import secrets
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from .backend import SSHBackend
from .model import require
from .store import Store


def initialize(config_path, keys_path):
    os.umask(0o077)
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_bytes((Path(__file__).parent.parent / 'config/cluster.example.json').read_bytes())
    require(not keys_path.exists(), 'keys.json ya existe; no se rotan credenciales de forma implícita')
    keys = []
    for subject, role in [('infra-manager', 'admin'), ('alumno-demo', 'user')]:
        token = secrets.token_urlsafe(32)
        keys.append({'subject': subject, 'role': role, 'sha256': hashlib.sha256(token.encode()).hexdigest()})
        (keys_path.parent / (role + '.token')).write_text(token + '\n')
    keys_path.write_text(json.dumps(keys, indent=2) + '\n')
    print('Configuración creada. Revise cluster.json. Credenciales locales: config/admin.token y config/user.token (0600).')


def install(backend, names, packages):
    for name in names:
        node = backend.nodes[name]
        cfg = dict(backend.config['common'], **node)
        remote = '/tmp/g5-install-' + uuid.uuid4().hex
        ssh = backend.ssh(name)
        subprocess.run(ssh + ['umask 077; mkdir ' + shlex.quote(remote)], check=True)
        try:
            files = {'agent.py': (Path(__file__).parent / 'agent.py').read_bytes(),
                     'node.json': (json.dumps(cfg, indent=2) + '\n').encode(),
                     'g5-cluster-agent': b'#!/bin/sh\nexec /usr/bin/python3 -I /opt/g5-cluster/agent.py\n'}
            for filename, content in files.items():
                subprocess.run(ssh + ['cat > ' + shlex.quote(remote + '/' + filename)], input=content, check=True)
            script = r'''set -eu
stage=$1
expected=$2
role=$3
packages=$4
test "$(hostname -s | tr A-Z a-z)" = "$expected"
if test "$packages" = yes; then
    apt-get update
    case "$role" in
      worker) apt-get install -y python3 qemu-utils qemu-system-x86 openvswitch-switch iproute2 tcpdump genisoimage ;;
      gateway) apt-get install -y python3 openvswitch-switch iproute2 iptables dnsmasq-base tcpdump ;;
      switch) apt-get install -y python3 iproute2 tcpdump ;;
    esac
fi
if test "$role" = worker; then
    id g5qemu >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin g5qemu
fi
install -d -m 0755 -o root -g root /opt/g5-cluster /etc/g5-cluster
install -m 0644 -o root -g root "$stage/agent.py" /opt/g5-cluster/agent.py
install -m 0600 -o root -g root "$stage/node.json" /etc/g5-cluster/node.json
install -m 0755 -o root -g root "$stage/g5-cluster-agent" /usr/local/sbin/g5-cluster-agent
printf '%s\n' 'ubuntu ALL=(root) NOPASSWD: /usr/local/sbin/g5-cluster-agent ""' > "$stage/sudoers"
visudo -cf "$stage/sudoers"
install -m 0440 -o root -g root "$stage/sudoers" /etc/sudoers.d/g5-cluster-agent
'''
            command = 'sudo -n bash -s -- ' + ' '.join(shlex.quote(v) for v in (remote, name, node['role'], 'yes' if packages else 'no'))
            subprocess.run(ssh + [command], input=script.encode(), check=True)
            print(name + ': agente instalado; bootstrap aún pendiente')
        finally:
            subprocess.run(ssh + ['rm -rf -- ' + shlex.quote(remote)], check=False)


def service_files(directory):
    directory = directory.resolve()
    require(' ' not in str(directory), 'Use una ruta sin espacios para systemd')
    api = '''[Unit]
Description=Grupo 5 Linux Cluster Driver API
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=ubuntu
WorkingDirectory={root}
ExecStart=/usr/bin/python3 -m g5.api --config config/cluster.json --keys config/keys.json --state state
Restart=on-failure
RestartSec=3
TimeoutStopSec=30
KillMode=control-group
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
'''.format(root=directory)
    console = '''[Unit]
Description=Grupo 5 noVNC token gateway
After=g5-cluster-api.service
Requires=g5-cluster-api.service
[Service]
Type=simple
User=ubuntu
WorkingDirectory={root}
ExecStart=/usr/bin/python3 -m g5.console --state {root}/state
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
'''.format(root=directory)
    out = directory / 'generated'; out.mkdir(exist_ok=True)
    (out / 'g5-cluster-api.service').write_text(api)
    (out / 'g5-cluster-console.service').write_text(console)
    print('Unidades generadas en ' + str(out) + '. Instálelas con las órdenes del README.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/cluster.json')
    parser.add_argument('--keys', default='config/keys.json')
    parser.add_argument('--state', default='state')
    parser.add_argument('command', choices=['init', 'install-agents', 'doctor', 'bootstrap', 'inventory', 'units', 'seed-demo'])
    parser.add_argument('--nodes', default='all')
    parser.add_argument('--skip-packages', action='store_true')
    args = parser.parse_args()
    config_path, keys_path = Path(args.config), Path(args.keys)
    if args.command == 'init':
        return initialize(config_path, keys_path)
    if args.command == 'units':
        return service_files(Path.cwd())
    config = json.loads(config_path.read_text())
    if args.command == 'seed-demo':
        require(Path(args.state).name.startswith('demo'), 'Use --state demo-state; nunca el estado real')
        store = Store(args.state, config)
        image = hashlib.sha256(b'G5-SIMULATION-NOT-QCOW2').hexdigest()
        (store.directory / 'images').mkdir(exist_ok=True)
        (store.directory / 'images' / (image + '.qcow2')).write_bytes(b'G5-SIMULATION-NOT-QCOW2')
        with store.tx() as db:
            db.execute('INSERT OR IGNORE INTO images VALUES(?,?,?,?,?)', (image, 'SIMULATED', 23, 1024**3, time.time()))
        print(image); return
    backend = SSHBackend(config)
    nodes = sorted(backend.nodes) if args.nodes == 'all' else args.nodes.split(',')
    require(all(n in backend.nodes for n in nodes), 'Nodo no registrado')
    if args.command == 'install-agents':
        return install(backend, nodes, not args.skip_packages)
    for name in nodes:
        result = backend.call(name, args.command)
        print(json.dumps(result, indent=2))
        require(result.get('ok', True), name + ': precomprobación fallida')


if __name__ == '__main__':
    main()
