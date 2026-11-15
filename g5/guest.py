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


def is_ubuntu(image):
    return isinstance(image, str) and 'ubuntu' in image.lower()


MAC = re.compile(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}')


def mtu_commands(mac, mtu):
    """Fija el MTU de la NIC con esa MAC ahora y en los siguientes arranques (netplan, sin usar el MTU del DHCP).

    La red provider `external` anuncia 1500, pero el camino hacia Internet no deja pasar tramas tan grandes: la
    conexión TCP se abre y las respuestas grandes se pierden (apt queda en «Waiting for headers»)."""
    require(MAC.fullmatch(mac) and isinstance(mtu, int) and 576 <= mtu <= 9000, 'MTU o MAC inválidos')
    script = ('for d in /sys/class/net/*; do [ "$(cat $d/address)" = "%s" ] || continue; n=${d##*/}; '
              'ip link set dev "$n" mtu %d; '
              'printf "network:\\n  version: 2\\n  ethernets:\\n    %%s:\\n      mtu: %d\\n'
              '      dhcp4: true\\n      dhcp4-overrides:\\n        use-mtu: false\\n" "$n" > /etc/netplan/90-g5-mtu.yaml; '
              'chmod 600 /etc/netplan/90-g5-mtu.yaml; done') % (mac, mtu, mtu)
    return ['sh', '-c', script]


def cloud_config(guest, hostname, mtu=None):
    """`#cloud-config` para OpenStack (la red la configura cloud-init desde el config drive de Nova).

    `mtu`: (MAC, MTU) de la NIC de salida a Internet, si la VM la tiene."""
    user = {'name': guest['username'], 'shell': '/bin/bash', 'groups': ['sudo'], 'sudo': 'ALL=(ALL) NOPASSWD:ALL',
            'lock_passwd': False, 'passwd': guest['password_hash'],
            'ssh_authorized_keys': guest['ssh_authorized_keys']}
    data = {'hostname': hostname, 'manage_etc_hosts': True, 'users': [user],
            # Sin clave SSH, la contraseña es la única forma de entrar por SSH desde otras VMs del slice.
            'ssh_pwauth': not guest['ssh_authorized_keys'], 'disable_root': True, 'chpasswd': {'expire': False},
            'package_update': False, 'package_upgrade': False}
    if mtu:
        data['bootcmd'] = [mtu_commands(*mtu)]
    return '#cloud-config\n' + json.dumps(data, indent=2) + '\n'


def user_data(guest, hostname, mtu=None):
    text = cloud_config(guest, hostname, mtu)
    if len(text.encode()) > 48 * 1024:
        raise Fault('user_data demasiado grande para Nova')
    return base64.b64encode(text.encode()).decode()
