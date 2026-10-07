#!/usr/bin/env python3
"""Establece SSH administrativo; la verificación de huellas es interactiva y obligatoria."""
import argparse
import json
import os
import subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--config', default='config/cluster.json')
a = p.parse_args()
cfg = json.loads(Path(a.config).read_text())
key = Path(cfg['ssh_key']).expanduser()
key.parent.mkdir(parents=True, exist_ok=True)
os.chmod(str(key.parent), 0o700)
if not key.exists():
    subprocess.run(['ssh-keygen','-t','ed25519','-N','','-f',str(key),'-C','ex1-headnode'],check=True)
if not key.with_suffix(key.suffix+'.pub').exists():
    raise SystemExit('Falta la clave pública asociada; no se sobrescribe la clave existente')
nodes = dict(cfg['workers'])
nodes[cfg['gateway']['name']] = cfg['gateway']
nodes[cfg['switch']['name']] = cfg['switch']
for name,node in sorted(nodes.items()):
    user = node.get('ssh_user','ubuntu')
    port = str(node.get('ssh_port',22))
    target = user+'@'+node['host']
    print(name+': verifique la huella con su inventario antes de aceptarla.',flush=True)
    subprocess.run(['ssh-copy-id','-i',str(key)+'.pub','-p',port,'-o','StrictHostKeyChecking=ask',target],check=True)
    subprocess.run(['ssh','-i',str(key),'-p',port,'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',target,'hostname; sudo -n true'],check=True)
