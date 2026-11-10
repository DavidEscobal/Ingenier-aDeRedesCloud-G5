#!/usr/bin/env python3
"""Paso 5 de punta a punta: login → crear slice por el gateway → READY → borrar → DELETED.

Uso en el app server:
  python3 scripts/smoke_gateway_slices.py --user admin123 [--course TEL141] [--template templates/os-lineal-1g.json]

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


def wait(base, token, sid, timeout=600):
    start, last = time.time(), None
    while time.time() - start < timeout:
        status, body = call(base, 'GET', '/v1/slices/' + sid, token)
        state = body.get('status') if status == 200 else 'HTTP %s' % status
        if state != last:
            print('     t=%5.1fs estado=%s' % (time.time() - start, state))
            last = state
        if state in FINAL:
            return state, body
        time.sleep(5)
    return 'TIMEOUT', None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--user', default='admin123')
    parser.add_argument('--course', default='TEL141')
    parser.add_argument('--template', default='templates/os-lineal-1g.json')
    args = parser.parse_args()
    spec = json.load(open(args.template))
    password = getpass.getpass('Contraseña de %s: ' % args.user)
    status, body = call(args.url, 'POST', '/v1/auth/login', body={'username': args.user, 'password': password})
    password = None
    if status != 200:
        print('FAIL login HTTP %s' % status)
        return 1
    token = body['access_token']
    results, sid = [], None

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
        status, accepted = call(args.url, 'POST', '/v1/slices', token, {'course_id': args.course, 'spec': spec}, uuid.uuid4().hex)
        check('3. crear slice por el gateway', status == 202, 'HTTP %s %s' % (status, accepted if status != 202 else ''))
        if status != 202:
            return 1
        sid = accepted['slice_id']
        print('     slice_id=%s operación=%s' % (sid, accepted['operation_id']))
        state, detail = wait(args.url, token, sid)
        check('4. el slice llega a READY', state == 'READY', state)
        if detail:
            for event in detail.get('events', [])[-4:]:
                print('     evento %s %s: %s' % (event.get('seq'), event.get('event'), (event.get('detail') or '')[:110]))
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
            state, _ = wait(args.url, token, sid)
            check('8. el slice llega a DELETED', state == 'DELETED', state)
        call(args.url, 'POST', '/v1/auth/logout', token)
        token = None
    print('\nResultado: %d/%d OK' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
