"""Preparación y evidencias del EX1; las operaciones de ciclo de vida usan la API del driver."""
import argparse
import copy
import ipaddress
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from .backend import SSHBackend
from .cli import request
from .model import require, validate, disk_bytes

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    os.chmod(str(temp), 0o600)
    os.replace(str(temp), str(path))


def wait(call, job, timeout=1800):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        current = call('GET', '/v1/operations/' + job['id'])
        if current['status'] in ('SUCCEEDED', 'FAILED'):
            require(current['status'] == 'SUCCEEDED', 'Operación fallida: ' + json.dumps(current), 503)
            return current
        time.sleep(2)
    raise RuntimeError('Timeout; conserve la carpeta de ejecución y consulte la operación ' + job['id'])


def build(args, cfg, call):
    images = {'ubuntu': json.loads(Path(args.ubuntu_image).read_text())['id'],
              'cirros': json.loads(Path(args.cirros_image).read_text())['id']}
    require(images['ubuntu'] != images['cirros'], 'EX1 requiere dos imágenes distintas: Ubuntu y CirrOS')
    catalog = {im['id']: im for im in call('GET', '/v1/images')}
    keys = [Path(k).expanduser().read_text().strip() for k in args.ssh_key]
    sources = [str(ipaddress.IPv4Network(v, strict=True)) for v in args.allowed_source]
    # Autorizar también las comprobaciones desde el headnode mediante OUTPUT DNAT.
    head = cfg['gateway']['host'] + '/32'
    if head not in sources:
        sources.append(head)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    credentials = out / 'guest-credentials.json'
    if credentials.exists():
        secret = json.loads(credentials.read_text())
    else:
        password = secrets.token_urlsafe(18)
        result = subprocess.run(['openssl', 'passwd', '-6', '-stdin'], input=password+'\n',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
        secret = {'username': 'ex1', 'console_password': password, 'password_hash': result.stdout.strip()}
        save(credentials, secret)
    for kind in ('ex1', 'lineal', 'anillo'):
        spec = json.loads((ROOT / 'templates' / (kind + '.json')).read_text())
        for vm in spec['vms']:
            family = vm['image']
            vm['image'] = images[family]
            require(vm['image'] in catalog, 'Imagen no registrada: ' + family)
            require(catalog[vm['image']]['virtual_size'] <= disk_bytes(vm['disk_gb'], cfg.get('disk_unit','GiB')),
                    'La base %s excede el flavor de %s; no se reduce ni se redondea a 3 GB' % (family, vm['name']))
            if family == 'ubuntu':
                vm['guest'].update(username=secret['username'], password_hash=secret['password_hash'], ssh_authorized_keys=keys)
        for pub in spec['publications']:
            pub['allowed_sources'] = sources
        save(out / (kind + '.json'), validate(spec, cfg))
    print('Plantillas resueltas: ' + str(out.resolve()))
    print('Credenciales VNC del SO: ' + str(credentials.resolve()) + ' (0600). SSH usa su clave pública.')


def process_table(plan, diagnostics):
    rows = []
    for vm in plan['vms']:
        real = diagnostics['nodes'].get(vm['worker'], {}).get('vms', {}).get(vm['name'], {})
        rows.append({'vm': vm['name'], 'worker': vm['worker'], 'pid': real.get('pid'),
                     'running': real.get('running', False), 'image': vm['image'],
                     'disk_bytes': vm['disk_bytes'], 'disk_path': real.get('disk_path'),
                     'qemu_name': real.get('qemu_name'), 'nics': real.get('nics', vm['nics'])})
    return rows


def snapshot(call, run):
    journal = json.loads((run / 'deployment.json').read_text())
    sid = journal['job']['slice_id']
    row = call('GET', '/v1/slices/' + sid)
    save(run / 'slice.json', row)
    diagnostics = call('GET', '/v1/slices/' + sid + '/diagnostics')
    save(run / 'diagnostics.json', diagnostics)
    events = call('GET', '/v1/slices/' + sid + '/events')
    save(run / 'events.json', events)
    table = process_table(row['plan'], diagnostics)
    save(run / 'processes.json', table)
    print('VM     WORKER    PID       RUNNING   DISK')
    for v in table:
        print('{vm:<6} {worker:<9} {pid!s:<9} {running!s:<9} {disk_path}'.format(**v))
    lines = ['vm\tworker\tnic\tmac\tip\tnetwork\tcvid\tsvid']
    for vm in row['plan']['vms']:
        for nic in vm['nics']:
            net = next(n for n in row['plan']['networks'] if n['name'] == nic['network'])
            lines.append('\t'.join(map(str, [vm['name'],vm['worker'],nic.get('name',''),nic['mac'],nic['ip'],nic['network'],net['cvid'],row['plan']['svid']])))
    (run / 'interfaces.tsv').write_text('\n'.join(lines) + '\n')
    print('Estado: ' + row['status'] + '. Evidencias: ' + str(run.resolve()))
    return row


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='config/cluster.json')
    p.add_argument('--url', default='http://127.0.0.1:8085')
    p.add_argument('--token-file', default='config/admin.token')
    sub = p.add_subparsers(dest='command')
    b = sub.add_parser('build')
    b.add_argument('--ubuntu-image', required=True, help='JSON devuelto por import-image')
    b.add_argument('--cirros-image', required=True)
    b.add_argument('--ssh-key', action='append', required=True, help='Clave pública para el usuario ex1 de las VMs')
    b.add_argument('--allowed-source', action='append', required=True, help='CIDR real de notebook/VPN observado por el gateway')
    b.add_argument('--output', default='generated')
    a = sub.add_parser('preflight'); a.add_argument('--empty', action='store_true'); a.add_argument('--output', default='evidencias/preflight.json')
    a = sub.add_parser('deploy'); a.add_argument('--file', required=True); a.add_argument('--run', required=True)
    for cmd in ('status','consoles','cleanup'):
        a = sub.add_parser(cmd); a.add_argument('--run', required=True)
    args = p.parse_args()
    require(args.command, 'Indique build, preflight, deploy, status, consoles o cleanup')
    cfg = json.loads(Path(args.config).read_text())
    token = Path(args.token_file).read_text().strip()
    def call(method, path, body=None, key=None):
        return request(args.url, token, method, path, body, key=key)
    if args.command == 'build':
        return build(args, cfg, call)
    cap = call('GET', '/v1/capabilities')
    require(not cap['simulated'], 'La demo de evaluación requiere backend real')
    if args.command == 'preflight':
        backend = SSHBackend(cfg)
        report = {'capabilities': cap, 'nodes': call('GET','/v1/nodes'), 'workers': {}}
        for node in sorted(cfg['workers']):
            report['workers'][node] = backend.call(node, 'inventory')
        save(args.output, report)
        print(json.dumps(report, indent=2))
        require(all(n['ok'] for n in report['nodes']), 'Preflight fallido: revise nodos')
        if args.empty:
            require(all(n['managed_clean'] for n in report['workers'].values()), 'Hay procesos/discos/reservas: revise inventario antes de presentar')
        return
    run = Path(args.run); run.mkdir(parents=True, exist_ok=True)
    journal_path = run / 'deployment.json'
    if args.command == 'deploy':
        spec = validate(json.loads(Path(args.file).read_text()), cfg)
        if journal_path.exists():
            journal = json.loads(journal_path.read_text())
            require(journal['spec'] == spec, 'Esta carpeta corresponde a otro request; use otra --run')
        else:
            journal = {'spec': spec, 'key': uuid.uuid4().hex, 'created': time.time()}
            save(journal_path, journal)  # escribir clave ANTES de enviar
        job = call('POST', '/v1/slices', spec, journal['key'])
        journal['job'] = job; save(journal_path, journal)
        try:
            wait(call, job)
        finally:
            snapshot(call, run)
        return
    require(journal_path.exists(), 'No existe deployment.json para esta ejecución')
    journal = json.loads(journal_path.read_text()); sid = journal['job']['slice_id']
    if args.command == 'status':
        return snapshot(call, run)
    if args.command == 'consoles':
        row = call('GET', '/v1/slices/' + sid)
        consoles = {}
        for vm in row['plan']['vms']:
            if vm.get('guest', {}).get('os') == 'ubuntu':
                consoles[vm['name']] = call('POST','/v1/slices/%s/vms/%s/console'%(sid,vm['name']),{'ttl':600})
                print(vm['name'] + ': ' + consoles[vm['name']]['url'])
        save(run / 'consoles.json', consoles)
        return
    if args.command == 'cleanup':
        row = call('GET','/v1/slices/' + sid)
        if row['status'] != 'DELETED':
            # Conservar clave ante timeout; regenerar solo si una operación anterior ya FALLÓ.
            old = journal.get('delete_job')
            if old and call('GET','/v1/operations/' + old['id'])['status'] == 'FAILED':
                journal.pop('delete_key', None)
            journal.setdefault('delete_key', uuid.uuid4().hex); save(journal_path,journal)
            job = call('DELETE','/v1/slices/' + sid,key=journal['delete_key'])
            journal['delete_job'] = job; save(journal_path,journal)
            wait(call,job)
        backend = SSHBackend(cfg)
        report = {'slice':call('GET','/v1/slices/' + sid),'workers':{}}
        for node in sorted({v['worker'] for v in row['plan']['vms']}):
            report['workers'][node] = backend.call(node,'inventory')
        save(run / 'cleanup.json', report)
        save(run / 'events.json',call('GET','/v1/slices/' + sid + '/events'))
        print(json.dumps(report,indent=2))
        require(report['slice']['status']=='DELETED' and not report['slice']['reserved'], 'Borrado no confirmado')
        print('Slice eliminado. Bases sin referencias retiradas automáticamente; revisar cleanup.json para evidencia.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
