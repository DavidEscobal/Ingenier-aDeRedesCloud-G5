#!/usr/bin/env python3
"""Paso 5 de punta a punta: login → crear slice por el gateway → READY → borrar → DELETED.

Uso en el app server:
  python3 scripts/smoke_gateway_slices.py --user admin123 [--course TEL141] [--template templates/os-lineal-1g.json]
      [--provider linux --provider openstack] [--zone ZONA] [--hold 60]
      [--image ubuntu-24.04-minimal-cloudimg-amd64 --size 1/1024/4 --guest-user alumno]

Con --provider (repetible) se prueba la misma topología en cada proveedor con un solo login; se muestra la
decisión del VM Placement (R4) y el servidor de cada VM. --hold deja el slice READY esos segundos antes de borrarlo.

Pide la contraseña sin mostrarla; nunca imprime contraseña ni token. Crea el curso en IAM si no existe.
Crea recursos reales en OpenStack y los borra al final (también si se interrumpe tras crearlos).
"""
import argparse
import getpass
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

FINAL = {'READY', 'FAILED', 'FAILED_CLEANED', 'DELETED', 'ERROR'}


def call(base, method, path, token=None, body=None, key=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header('Accept', 'application/json')
    if data is not None:
        request.add_header('Content-Type', 'application/json')
    if token:
        request.add_header('Authorization', 'Bearer ' + token)
    if key:
        request.add_header('Idempotency-Key', key)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, json.loads(response.read() or b'null')
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b'null')
        except ValueError:
            return exc.code, None


def wait(base, token, sid, timeout=600, final=FINAL):
    start, last = time.time(), None
    while time.time() - start < timeout:
        status, body = call(base, 'GET', '/v1/slices/' + sid, token)
        state = body.get('status') if status == 200 else 'HTTP %s' % status
        if state != last:
            print('     t=%5.1fs estado=%s' % (time.time() - start, state))
            last = state
        if state in final:
            return state, body
        time.sleep(5)
    return 'TIMEOUT', None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--user', default='admin123')
    parser.add_argument('--course', default='TEL141')
    parser.add_argument('--template', default='templates/os-lineal-1g.json')
    parser.add_argument('--provider', action='append', choices=['linux', 'openstack', 'auto'])
    parser.add_argument('--zone')
    parser.add_argument('--hold', type=int, default=0)
    parser.add_argument('--image', help='imagen del catálogo para todas las VMs (reemplaza la de la plantilla)')
    parser.add_argument('--timeout', type=int, default=600, help='segundos de espera por estado final')
    parser.add_argument('--delete', metavar='SLICE_ID', help='solo borrar ese slice y esperar DELETED')
    parser.add_argument('--guest-user', help='usuario de las VMs Ubuntu; pide su contraseña sin mostrarla')
    parser.add_argument('--size', help='vcpus/memory_mb/disk_gb para todas las VMs, p. ej. 1/1024/4')
    parser.add_argument('--internet', action='append', default=[], metavar='VM', help='VM con salida a Internet (repetible)')
    args = parser.parse_args()
    base_spec = json.load(open(args.template))
    if args.image:
        for vm in base_spec['vms']:
            vm['image'] = args.image
    for vm in base_spec['vms']:
        if vm['name'] in args.internet:
            vm['internet'] = True
    if args.size:
        vcpus, memory_mb, disk_gb = (int(x) for x in args.size.split('/'))
        for vm in base_spec['vms']:
            vm.update(vcpus=vcpus, memory_mb=memory_mb, disk_gb=disk_gb)
    guest = None
    if args.guest_user:
        vm_password = getpass.getpass('Contraseña para el usuario %s de las VMs: ' % args.guest_user)
        if vm_password != getpass.getpass('Repítela: '):
            print('FAIL las contraseñas de las VMs no coinciden')
            return 1
        if not 8 <= len(vm_password) <= 72:
            print('FAIL la contraseña de las VMs debe tener entre 8 y 72 caracteres')
            return 1
        guest = {'username': args.guest_user, 'password': vm_password}
    args.guest = guest
    password = getpass.getpass('Contraseña de %s: ' % args.user)
    status, body = call(args.url, 'POST', '/v1/auth/login', body={'username': args.user, 'password': password})
    password = None
    if status != 200:
        print('FAIL login HTTP %s' % status)
        return 1
    token = body['access_token']
    ttl = int(body.get('expires_in') or 900)
    if args.hold > ttl - 180:   # el token debe seguir vigente para borrar al final
        print('     --hold %d s supera la vida del token (%d s); se usa %d s' % (args.hold, ttl, ttl - 180))
        args.hold = ttl - 180
    results = []

    def check(name, ok, detail=''):
        results.append(ok)
        print('%-4s %s %s' % ('OK' if ok else 'FAIL', name, detail))

    try:
        check('1. login por el gateway', True, '(token de %ss)' % body.get('expires_in'))
        _, courses = call(args.url, 'GET', '/v1/iam/courses', token)
        if not any(c.get('id') == args.course for c in courses or []):
            status, _ = call(args.url, 'POST', '/v1/iam/courses', token, {'id': args.course, 'name': 'Ingeniería de Redes Cloud'})
            check('2. curso %s creado en IAM' % args.course, status == 201, 'HTTP %s' % status)
        else:
            check('2. curso %s existe en IAM' % args.course, True)
        if args.delete:                       # solo borrar un slice que quedó vivo (p. ej., borrado pedido en DEPLOYING)
            status, _ = call(args.url, 'DELETE', '/v1/slices/' + args.delete, token, key=uuid.uuid4().hex)
            check('7. borrar por el gateway', status == 202, 'HTTP %s' % status)
            state, _ = wait(args.url, token, args.delete, args.timeout, FINAL - {'READY'})
            check('8. el slice llega a DELETED', state == 'DELETED', state)
            return 0 if all(results) else 1
        for provider in args.provider or [base_spec.get('provider', 'openstack')]:
            spec = dict(base_spec, provider=provider)
            print('\n== %s: %s (%d VMs)' % (provider, spec['name'], len(spec['vms'])))
            run_slice(args, token, spec, check)
    finally:
        call(args.url, 'POST', '/v1/auth/logout', token)
        token = None
    print('\nResultado: %d/%d OK' % (sum(results), len(results)))
    return 0 if all(results) else 1


def run_slice(args, token, spec, check):
    sid = None
    try:
        body = {'course_id': args.course, 'spec': spec}
        if args.guest:
            body['guest'] = args.guest
        if args.zone:
            body['zone'] = args.zone
        status, accepted = call(args.url, 'POST', '/v1/slices', token, body, uuid.uuid4().hex)
        check('3. crear slice por el gateway', status == 202, 'HTTP %s %s' % (status, accepted if status != 202 else ''))
        if status != 202:
            return
        sid = accepted['slice_id']
        print('     slice_id=%s operación=%s' % (sid, accepted['operation_id']))
        placement = accepted.get('placement')
        if placement:
            print('     placement: %s %s, %s host(s) nuevos, %s ms, intento %s' % (
                placement.get('status'), placement.get('algorithm'), placement.get('hosts_opened'),
                placement.get('elapsed_ms'), placement.get('attempts')))
            print('     plan: %s' % json.dumps(placement.get('plan'), sort_keys=True))
        check('3b. el VM Placement decidió el plan', bool(placement) and placement.get('status') == 'PLAN_FOUND',
              'sin placement' if not placement else placement.get('status'))
        state, detail = wait(args.url, token, sid, args.timeout)
        check('4. el slice llega a READY', state == 'READY', state)
        if detail:
            hosts = {v['name']: v.get('host') for v in detail.get('vms', [])}
            print('     servidor por VM (detalle): %s' % json.dumps(hosts, sort_keys=True))
            if placement:
                check('4b. el detalle respeta el plan', hosts == placement.get('plan'))
            for event in detail.get('events', [])[-4:]:
                print('     evento %s %s: %s' % (event.get('seq'), event.get('event'), (event.get('detail') or '')[:110]))
        if state == 'READY' and args.hold:
            print('     en READY %d s antes de borrar…' % args.hold)
            time.sleep(args.hold)
        status, rows = call(args.url, 'GET', '/v1/slices', token)
        row = next((r for r in rows or [] if r.get('id') == sid), {})
        check('5. aparece en la lista con dueño y curso', status == 200 and row.get('course_id') == args.course,
              'dueño=%s curso=%s estado=%s' % (row.get('owner'), row.get('course_id'), row.get('status')))
        status, missing = call(args.url, 'GET', '/v1/slices/' + '0' * 32, token)
        check('6. slice inexistente → 404', status == 404)
    finally:
        if sid:
            status, _ = call(args.url, 'DELETE', '/v1/slices/' + sid, token, key=uuid.uuid4().hex)
            check('7. borrar por el gateway', status == 202, 'HTTP %s' % status)
            state, _ = wait(args.url, token, sid, args.timeout, FINAL - {'READY'})
            check('8. el slice llega a DELETED', state == 'DELETED', state)


if __name__ == '__main__':
    sys.exit(main())
