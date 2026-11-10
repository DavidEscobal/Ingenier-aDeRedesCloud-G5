#!/usr/bin/env python3
"""Asigna contraseñas elegidas por el admin a usuarios existentes de IAM (p. ej. prof1 y alumno1 para la demo).

Uso en el app server:  python3 scripts/set_user_passwords.py --admin admin123 prof1 alumno1

Pide la contraseña del admin y la nueva de cada usuario sin mostrarlas (15–128 caracteres); no las imprime
ni las guarda. Restablecer la contraseña cierra las sesiones abiertas de ese usuario.
"""
import argparse
import getpass
import sys

from smoke_gateway_slices import call


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--admin', default='admin123')
    parser.add_argument('users', nargs='+')
    args = parser.parse_args()
    status, body = call(args.url, 'POST', '/v1/auth/login',
                        body={'username': args.admin, 'password': getpass.getpass('Contraseña de %s: ' % args.admin)})
    if status != 200:
        print('FAIL login del admin (HTTP %s)' % status)
        return 1
    token = body['access_token']
    try:
        _, users = call(args.url, 'GET', '/v1/iam/users', token)
        by_name = {u['username']: u for u in users or []}
        ok = True
        for name in args.users:
            user = by_name.get(name)
            if not user:
                print('FAIL %s: no existe en IAM' % name)
                ok = False
                continue
            first = getpass.getpass('Nueva contraseña para %s (%s, 15–128 caracteres): ' % (name, user['role']))
            if first != getpass.getpass('Repite la contraseña de %s: ' % name):
                print('FAIL %s: las contraseñas no coinciden' % name)
                ok = False
                continue
            if not 15 <= len(first) <= 128:
                print('FAIL %s: debe tener entre 15 y 128 caracteres' % name)
                ok = False
                continue
            status, _ = call(args.url, 'POST', '/v1/iam/users/%s/password' % user['id'], token, {'password': first})
            first = None
            print('%-4s %s (%s)%s' % ('OK' if status == 200 else 'FAIL', name, user['role'],
                                      '' if status == 200 else ' HTTP %s' % status))
            ok &= status == 200
    finally:
        call(args.url, 'POST', '/v1/auth/logout', token)
        token = None
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
