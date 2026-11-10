#!/usr/bin/env python3
"""MS-06: roles académicos contra el clúster real, entrando por el gateway.

Uso en el app server:
  python3 scripts/smoke_gateway_roles.py --admin admin123 [--course TEL141] [--template templates/os-lineal-1g.json]

Solo pide la contraseña del admin (sin mostrarla). Asegura en IAM los usuarios de prueba prof1, prof2
(profesores) y alumno1 (alumno), matriculados en el curso, con contraseñas aleatorias que nunca se
imprimen ni se guardan (si ya existen, el admin se las restablece). Luego:
prof1 crea un slice real → prof2 no puede verlo ni borrarlo → alumno1 no puede crear → el admin sí lo ve
→ prof1 lo borra. Crea recursos reales en OpenStack y los borra al final, también ante un fallo.
"""
import argparse
import getpass
import json
import secrets
import sys
import uuid

from smoke_gateway_slices import call, wait

TEST_USERS = (('prof1', 'professor', 'Profesor de prueba 1'),
              ('prof2', 'professor', 'Profesor de prueba 2'),
              ('alumno1', 'student', 'Alumno de prueba 1'))


def login(base, username, password):
    status, body = call(base, 'POST', '/v1/auth/login', body={'username': username, 'password': password})
    return body['access_token'] if status == 200 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--admin', default='admin123')
    parser.add_argument('--course', default='TEL141')
    parser.add_argument('--template', default='templates/os-lineal-1g.json')
    args = parser.parse_args()
    base, spec = args.url, json.load(open(args.template))
    results, tokens, sid = [], {}, None

    def check(name, ok, detail=''):
        results.append(ok)
        print('%-4s %s %s' % ('OK' if ok else 'FAIL', name, detail))

    admin = login(base, args.admin, getpass.getpass('Contraseña de %s: ' % args.admin))
    if not admin:
        print('FAIL login del admin')
        return 1
    tokens['admin'] = admin
    try:
        # --- Preparación en IAM (por el gateway, como admin) ---
        _, courses = call(base, 'GET', '/v1/iam/courses', admin)
        if not any(c.get('id') == args.course for c in courses or []):
            call(base, 'POST', '/v1/iam/courses', admin, {'id': args.course, 'name': 'Ingeniería de Redes Cloud'})
        _, users = call(base, 'GET', '/v1/iam/users', admin)
        existing = {u['username']: u for u in users or []}
        ready = True
        for username, role, display in TEST_USERS:
            password = secrets.token_urlsafe(24)
            if username in existing:
                user = existing[username]
                status, _ = call(base, 'POST', '/v1/iam/users/%s/password' % user['id'], admin, {'password': password})
                ok = status == 200 and user['role'] == role and user['active']
            else:
                status, user = call(base, 'POST', '/v1/iam/users', admin,
                                    {'username': username, 'password': password, 'display_name': display, 'role': role})
                ok = status == 201
            status, _ = call(base, 'PUT', '/v1/iam/courses/%s/members/%s' % (args.course, user['id']), admin, {})
            tokens[username] = login(base, username, password) if ok and status == 200 else None
            password = None
            ready &= bool(tokens[username])
        check('1. usuarios prof1, prof2 (profesor) y alumno1 (alumno) listos en %s' % args.course, ready)
        if not ready:
            return 1
        prof1, prof2, alumno1 = tokens['prof1'], tokens['prof2'], tokens['alumno1']

        # --- Alumno y curso ajeno: rechazados antes de tocar la infraestructura ---
        status, body = call(base, 'POST', '/v1/slices', alumno1, {'course_id': args.course, 'spec': spec}, uuid.uuid4().hex)
        check('2. alumno1 NO puede crear slices', status == 403, 'HTTP %s %s' % (status, (body or {}).get('detail', '')))
        status, body = call(base, 'POST', '/v1/slices', prof1, {'course_id': 'CURSO-AJENO', 'spec': spec}, uuid.uuid4().hex)
        check('3. prof1 NO puede crear en un curso ajeno', status == 403, 'HTTP %s' % status)

        # --- prof1 crea un slice real ---
        status, accepted = call(base, 'POST', '/v1/slices', prof1, {'course_id': args.course, 'spec': spec}, uuid.uuid4().hex)
        check('4. prof1 crea un slice en %s' % args.course, status == 202, 'HTTP %s' % status)
        if status != 202:
            return 1
        sid = accepted['slice_id']
        print('     slice_id=%s' % sid)
        state, _ = wait(base, prof1, sid)
        check('5. el slice de prof1 llega a READY', state == 'READY', state)

        # --- Aislamiento ---
        _, rows = call(base, 'GET', '/v1/slices', prof2)
        check('6. prof2 NO lo ve en su lista', sid not in [r.get('id') for r in rows or []], '(%d slices propios)' % len(rows or []))
        status, _ = call(base, 'GET', '/v1/slices/' + sid, prof2)
        check('7. prof2 NO puede consultarlo', status == 404, 'HTTP %s' % status)
        status, _ = call(base, 'DELETE', '/v1/slices/' + sid, prof2, key=uuid.uuid4().hex)
        check('8. prof2 NO puede borrarlo', status == 404, 'HTTP %s' % status)
        status, _ = call(base, 'GET', '/v1/slices/' + sid, alumno1)
        check('9. alumno1 NO puede consultarlo (aún no está asignado)', status == 404, 'HTTP %s' % status)
        _, rows = call(base, 'GET', '/v1/slices', admin)
        row = next((r for r in rows or [] if r.get('id') == sid), {})
        check('10. el admin SÍ lo ve, con dueño prof1', row.get('owner') == 'prof1', 'dueño=%s estado=%s' % (row.get('owner'), row.get('status')))
        _, detail = call(base, 'GET', '/v1/slices/' + sid, prof1)
        check('11. prof1 sigue viéndolo READY (el intento de prof2 no lo afectó)', (detail or {}).get('status') == 'READY',
              (detail or {}).get('status'))
    finally:
        if sid:
            status, _ = call(base, 'DELETE', '/v1/slices/' + sid, tokens.get('prof1') or tokens['admin'], key=uuid.uuid4().hex)
            check('12. prof1 borra su slice', status == 202, 'HTTP %s' % status)
            state, _ = wait(base, tokens['admin'], sid)
            check('13. el slice llega a DELETED', state == 'DELETED', state)
        for token in tokens.values():
            if token:
                call(base, 'POST', '/v1/auth/logout', token)
        tokens.clear()
    print('\nResultado: %d/%d OK' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
