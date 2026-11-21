"""Credenciales de acceso a VMs con cloud-init (Ubuntu), comunes a los drivers Linux y OpenStack.

La especificación neutral puede traer un bloque `guest` de nivel de slice (lo arma el slice-manager):
    {"username": "ubuntu", "password_hash": "$6$...", "ssh_authorized_keys": ["ssh-ed25519 ..."]}
Solo viaja el hash SHA-512 crypt; la contraseña en claro nunca llega al platform-manager ni se guarda.
"""
import base64
import json
import re
from .model import Fault, fields, require

USERNAME = re.compile(r'[a-z][a-z0-9_-]{0,30}')
PASSWORD_HASH = re.compile(r'\$6\$[a-zA-Z0-9./]{1,16}\$[a-zA-Z0-9./]{86}')
SSH_KEY = re.compile(r'^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(?:256|384|521)) [A-Za-z0-9+/]+={0,3}(?: |$)')
RESERVED = {'root', 'daemon', 'bin', 'sys', 'nobody'}


def validate_access(guest):
    """Valida y normaliza el bloque `guest` del slice; devuelve una copia con `ssh_authorized_keys` siempre lista."""
    require(isinstance(guest, dict), 'guest debe ser un objeto')
    fields(guest, ('username', 'password_hash', 'ssh_authorized_keys'), ('username', 'password_hash'))
    require(isinstance(guest['username'], str) and USERNAME.fullmatch(guest['username'])
            and guest['username'] not in RESERVED, 'Usuario de las VMs inválido')
    require(isinstance(guest['password_hash'], str) and PASSWORD_HASH.fullmatch(guest['password_hash']),
            'Se requiere el hash SHA-512 crypt de la contraseña de las VMs')
    keys = guest.get('ssh_authorized_keys', [])
    require(isinstance(keys, list) and len(keys) <= 8, 'Hasta 8 claves SSH públicas')
    for key in keys:
        require(isinstance(key, str) and len(key) < 8192 and '\n' not in key and SSH_KEY.match(key),
                'Clave SSH pública inválida')
    return {'username': guest['username'], 'password_hash': guest['password_hash'], 'ssh_authorized_keys': list(keys)}


# Nombres de las imágenes cloud oficiales de Canonical (p. ej. focal-server-cloudimg-amd64 = Ubuntu 20.04).
UBUNTU_NAMES = re.compile(r'ubuntu|bionic|focal|jammy|noble', re.I)


def is_ubuntu(image):
    return isinstance(image, str) and bool(UBUNTU_NAMES.search(image))


MAC = re.compile(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}')


def mtu_commands(mac, mtu):
    """Configura por MAC el DHCP de Internet, también cuando Nova describe el circuito como estático."""
    require(MAC.fullmatch(mac) and type(mtu) is int and (mtu == 0 or 576 <= mtu <= 9000), 'MTU o MAC inválidos')
    return ['python3', '-c', INTERNET_CONFIG, mac, str(mtu)]


INTERNET_CONFIG = '''
from pathlib import Path
import subprocess, sys, yaml
mac, mtu = sys.argv[1], int(sys.argv[2])
device = next(p.name for p in Path('/sys/class/net').iterdir() if (p / 'address').read_text().strip() == mac)
found = False
for path in sorted(Path('/etc/netplan').glob('*.yaml')):
    doc = yaml.safe_load(path.read_text()) or {}
    for name, config in ((doc.get('network') or {}).get('ethernets') or {}).items():
        if (config.get('match') or {}).get('macaddress', '').lower() != mac and name != device:
            continue
        for key in ('addresses', 'gateway4', 'routes', 'nameservers'):
            config.pop(key, None)
        config['dhcp4'] = True
        if mtu:
            config['mtu'] = mtu
            config.setdefault('dhcp4-overrides', {})['use-mtu'] = False
        path.write_text(yaml.safe_dump(doc, default_flow_style=False))
        found = True
if not found:
    config = {'match': {'macaddress': mac}, 'dhcp4': True}
    if mtu:
        config.update(mtu=mtu, **{'dhcp4-overrides': {'use-mtu': False}})
    path = Path('/etc/netplan/90-g5-internet.yaml')
    path.touch(mode=0o600)
    path.write_text(yaml.safe_dump({'network': {'version': 2, 'ethernets': {'g5internet': config}}}))
subprocess.run(['netplan', 'generate'], check=True)
subprocess.run(['networkctl', 'reload'], check=True)
subprocess.run(['networkctl', 'reconfigure', device], check=True)
'''


def flush_commands(macs):
    """Deja sin IPv4 las NICs de enlaces «sin IP» (VM que hará de switch, Ex2 15b), en cada arranque.

    En OpenStack esos puertos llevan una IP de relleno (Nova no acepta puertos sin IP fija) que cloud-init escribe en
    el netplan desde network_data.json. Se quita también del netplan (direcciones, rutas y DNS de esas NICs): si solo
    se borrara la IP, volvería con cualquier `netplan apply`, p. ej. al instalar openvswitch-switch."""
    for mac in macs:
        require(MAC.fullmatch(mac), 'MAC inválida')
    return ['python3', '-c', UNADDRESS_SCRIPT] + list(macs)


UNADDRESS_SCRIPT = '''
import glob, subprocess, sys, yaml
macs = set(sys.argv[1:])
changed = False
for path in glob.glob('/etc/netplan/*.yaml'):
    try:
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
    except Exception:
        continue
    edited = False
    for conf in ((doc.get('network') or {}).get('ethernets') or {}).values():
        if isinstance(conf, dict) and str((conf.get('match') or {}).get('macaddress', '')).lower() in macs:
            for key in ('addresses', 'routes', 'nameservers', 'gateway4'):
                edited = conf.pop(key, None) is not None or edited
            if conf.get('dhcp4'):
                conf['dhcp4'], edited = False, True
    if edited:
        with open(path, 'w') as f:
            yaml.safe_dump(doc, f, default_flow_style=False)
        changed = True
if changed:
    subprocess.call(['netplan', 'generate'])
    subprocess.call(['networkctl', 'reload'])
for d in glob.glob('/sys/class/net/*'):
    try:
        with open(d + '/address') as f:
            mac = f.read().strip()
    except OSError:
        continue
    if mac in macs:
        subprocess.call(['ip', '-4', 'addr', 'flush', 'dev', d.rsplit('/', 1)[1]])
'''


def cloud_config(guest, hostname, mtu=None, unaddressed=(), ovs_bridge=False, internet=False):
    """`#cloud-config` para OpenStack (la red la configura cloud-init desde el config drive de Nova).

    `mtu`: (MAC, MTU) de la NIC de salida a Internet, si la VM la tiene; `unaddressed`: MACs que quedan sin IPv4."""
    user = {'name': guest['username'], 'shell': '/bin/bash', 'groups': ['sudo'], 'sudo': 'ALL=(ALL) NOPASSWD:ALL',
            'lock_passwd': False, 'passwd': guest['password_hash'],
            'ssh_authorized_keys': guest['ssh_authorized_keys']}
    data = {'hostname': hostname, 'manage_etc_hosts': True, 'users': [user],
            # Sin clave SSH, la contraseña es la única forma de entrar por SSH desde otras VMs del slice.
            'ssh_pwauth': not guest['ssh_authorized_keys'], 'disable_root': True, 'chpasswd': {'expire': False},
            'package_update': False, 'package_upgrade': False}
    commands = ([mtu_commands(*mtu)] if mtu else []) + ([flush_commands(unaddressed)] if unaddressed else [])
    if ovs_bridge:
        if internet:
            data['packages'] = ['openvswitch-switch']
        data['runcmd'] = [['ovs-vsctl', '--may-exist', 'add-br', 'br0']]
        for mac in unaddressed:
            require(MAC.fullmatch(mac), 'MAC inválida')
            data['runcmd'].append(['sh', '-ec',
                'for d in /sys/class/net/*; do [ "$(cat "$d/address")" = "$1" ] || continue; '
                'exec ovs-vsctl --may-exist add-port br0 "${d##*/}"; done; exit 1', 'sh', mac])
        data['runcmd'].append(['ip', 'link', 'set', 'br0', 'up'])
    if commands:
        data['bootcmd'] = commands
    return '#cloud-config\n' + json.dumps(data, indent=2) + '\n'


def user_data(guest, hostname, mtu=None, unaddressed=(), ovs_bridge=False, internet=False):
    text = cloud_config(guest, hostname, mtu, unaddressed, ovs_bridge, internet)
    if len(text.encode()) > 48 * 1024:
        raise Fault('user_data demasiado grande para Nova')
    return base64.b64encode(text.encode()).decode()
