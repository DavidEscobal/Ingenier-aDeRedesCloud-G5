#!/usr/bin/env python3
"""Prueba de punta a punta contra la API del platform-manager (desde dentro de su contenedor).

Uso:  cat admin.token | python3 pm_slice_e2e.py create <plantilla.json>
      cat admin.token | python3 pm_slice_e2e.py delete <slice_id>
El token se lee de stdin y nunca se imprime. Imprime JSON con estados, tiempos y eventos.
"""
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = 'http://127.0.0.1:8000'
FINAL = {'READY', 'FAILED', 'FAILED_CLEANED', 'DELETED', 'ERROR'}


def call(token, method, path, body=None, key=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header('Authorization', 'Bearer ' + token)
    if data is not None:
        request.add_header('Content-Type', 'application/json')
    if key:
        request.add_header('Idempotency-Key', key)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b'null')
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw.decode(errors='replace')[:300]


def wait(token, sid, timeout):
    start, last = time.time(), None
    while time.time() - start < timeout:
        status, row = call(token, 'GET', '/v1/slices/' + sid)
        state = row.get('status') if isinstance(row, dict) else None
        if state != last:
            print('  t=%5.1fs estado=%s' % (time.time() - start, state), file=sys.stderr)
            last = state
        if state in FINAL:
            return state, round(time.time() - start, 1)
        time.sleep(5)
    return 'TIMEOUT', round(time.time() - start, 1)


def events(token, sid):
    _, rows = call(token, 'GET', '/v1/slices/%s/events' % sid)
    rows = rows if isinstance(rows, list) else []
    return [{k: r.get(k) for k in ('seq', 'kind', 'detail', 'time') if k in r} for r in reversed(rows)]


def main():
    action, arg = sys.argv[1], sys.argv[2]
    token = sys.stdin.read().strip()
    result = {'action': action}
    if action == 'create':
        spec = json.load(open(arg))
        key = uuid.uuid4().hex
        status, job = call(token, 'POST', '/v1/slices', spec, key)
        result.update(http=status, job=job if not isinstance(job, dict) else {k: job.get(k) for k in ('id', 'slice_id', 'action', 'status')})
        if status != 202:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1
        sid = job['slice_id']
        result['slice_id'] = sid
        result['final'], result['seconds'] = wait(token, sid, 600)
    elif action == 'delete':
        sid = arg
        status, job = call(token, 'DELETE', '/v1/slices/' + sid, key=uuid.uuid4().hex)
        result.update(http=status, slice_id=sid)
        result['final'], result['seconds'] = wait(token, sid, 600)
    else:
        raise SystemExit('acción desconocida')
    _, row = call(token, 'GET', '/v1/slices/' + sid)
    if isinstance(row, dict):
        result['slice'] = {k: row.get(k) for k in ('id', 'name', 'provider', 'status', 'owner')}
    result['events'] = events(token, sid)
    token = None
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result['final'] in ('READY', 'DELETED') else 1


if __name__ == '__main__':
    sys.exit(main())
