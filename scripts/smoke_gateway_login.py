#!/usr/bin/env python3
"""Prueba de humo del login a través del gateway (biblioteca estándar, Python >= 3.8).

Uso en el app server:  python3 scripts/smoke_gateway_login.py [--url http://127.0.0.1:8000] [--user admin123]

Pide la contraseña sin mostrarla. Nunca imprime la contraseña ni el token: solo códigos
HTTP y campos no sensibles. Flujo: login -> /me -> capacidades -> logout -> el mismo
token debe ser rechazado (revocación).
"""
import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request


def call(base, method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header('Accept', 'application/json')
    if data is not None:
        request.add_header('Content-Type', 'application/json')
    if token:
        request.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw) if raw else None
        except ValueError:
            return exc.code, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--user', default='admin123')
    args = parser.parse_args()
    password = getpass.getpass('Contraseña de %s: ' % args.user)
    results = []

    def check(name, status, expected, detail=''):
        ok = status == expected
        results.append(ok)
        print('%-4s %-48s HTTP %s (esperado %s) %s' % ('OK' if ok else 'FAIL', name, status, expected, detail))

    status, body = call(args.url, 'POST', '/v1/auth/login', body={'username': args.user, 'password': password})
    password = None
    token = (body or {}).get('access_token') if status == 200 else None
    check('1. login', status, 200, 'expira en %ss' % (body or {}).get('expires_in') if token else '')
    if not token:
        print('Sin token: se detiene la prueba.')
        return 1
    status, body = call(args.url, 'GET', '/v1/auth/me', token)
    check('2. /v1/auth/me', status, 200, 'usuario=%s rol=%s' % ((body or {}).get('username'), (body or {}).get('role')))
    status, body = call(args.url, 'GET', '/v1/platform/capabilities', token)
    check('3. capacidades (gateway -> slice-manager -> IAM)', status, 200,
          'servicio=%s fase=%s' % ((body or {}).get('service'), (body or {}).get('phase')))
    status, body = call(args.url, 'GET', '/v1/iam/users', token)
    check('4. listar usuarios (requiere admin)', status, 200, 'usuarios=%s' % (len(body) if isinstance(body, list) else '?'))
    status, _ = call(args.url, 'POST', '/v1/auth/logout', token)
    check('5. logout', status, 200)
    status, _ = call(args.url, 'GET', '/v1/auth/me', token)
    check('6. mismo token tras logout (revocado)', status, 401)
    status, _ = call(args.url, 'GET', '/v1/platform/capabilities', token)
    check('7. capacidades con token revocado', status, 401)
    token = None
    print('\nResultado: %d/%d OK' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
