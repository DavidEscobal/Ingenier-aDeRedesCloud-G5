"""Cliente compacto con importación de imágenes en streaming y espera de operaciones."""
import argparse
import hashlib
import http.client
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit


def request(base, token, method, path, body=None, key=None, stream=None, name=None):
    url = urlsplit(base)
    cls = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
    conn = cls(url.hostname, url.port, timeout=300)
    headers = {'Authorization': 'Bearer ' + token, 'Idempotency-Key': key or uuid.uuid4().hex}
    try:
        if stream:
            headers.update({'Content-Length': str(stream.stat().st_size), 'X-Image-Name': name or stream.name,
                            'Content-Type': 'application/octet-stream'})
            with stream.open('rb') as f:
                conn.request(method, path, f, headers)
        else:
            headers['Content-Type'] = 'application/json'
            conn.request(method, path, json.dumps(body or {}), headers)
        response = conn.getresponse()
        result = json.loads(response.read())
        if response.status >= 400:
            raise RuntimeError('HTTP %s: %s' % (response.status, result))
        return result
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default=os.environ.get('G5_API_URL', 'http://127.0.0.1:8085'))
    p.add_argument('--token-file', default='config/admin.token')
    p.add_argument('--key', help='Reutilizar la MISMA clave si se reintenta una petición con resultado incierto')
    sub = p.add_subparsers(dest='command')
    for cmd in ('nodes', 'images', 'list'):
        sub.add_parser(cmd)
    a = sub.add_parser('import-image'); a.add_argument('file')
    a = sub.add_parser('create'); a.add_argument('file')
    for cmd in ('get', 'delete', 'events', 'diagnostics', 'reconcile', 'start', 'stop', 'wait'):
        a = sub.add_parser(cmd); a.add_argument('id')
    a = sub.add_parser('console'); a.add_argument('id'); a.add_argument('vm'); a.add_argument('--ttl', type=int, default=120)
    a = sub.add_parser('cache-gc'); a.add_argument('node'); a.add_argument('--all-unused', action='store_true')
    a = sub.add_parser('drain'); a.add_argument('node'); a.add_argument('--enable', action='store_true')
    args = p.parse_args()
    token = Path(args.token_file).read_text().strip()
    def call(method, path, body=None, **kw):
        return request(args.url, token, method, path, body, args.key, **kw)
    cmd = args.command
    if cmd in ('nodes', 'images', 'list'):
        result = call('GET', '/v1/' + ('slices' if cmd == 'list' else cmd))
    elif cmd == 'import-image':
        path = Path(args.file)
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024**2), b''):
                h.update(block)
        result = call('PUT', '/v1/images/' + h.hexdigest(), stream=path)
    elif cmd == 'create':
        # Imprimir la clave en stderr ANTES de enviar para recuperar ante timeout.
        args.key = args.key or uuid.uuid4().hex
        print('Idempotency-Key=' + args.key, file=sys.stderr)
        result = call('POST', '/v1/slices', json.loads(Path(args.file).read_text()))
    elif cmd == 'wait':
        deadline = time.monotonic() + 1800
        while True:
            result = call('GET', '/v1/operations/' + args.id)
            if result['status'] in ('SUCCEEDED', 'FAILED'):
                break
            if time.monotonic() > deadline:
                raise RuntimeError('Tiempo de espera agotado; la operación sigue consultable')
            time.sleep(2)
    elif cmd == 'console':
        result = call('POST', '/v1/slices/%s/vms/%s/console' % (args.id, args.vm), {'ttl': args.ttl})
    elif cmd == 'cache-gc':
        result = call('POST', '/v1/nodes/' + args.node + '/cache/gc', {'all_unused': args.all_unused})
    elif cmd == 'drain':
        result = call('PATCH', '/v1/nodes/' + args.node, {'enabled': args.enable})
    elif cmd in ('get', 'delete', 'events', 'diagnostics', 'reconcile', 'start', 'stop'):
        method = {'delete': 'DELETE', 'reconcile': 'POST', 'start': 'POST', 'stop': 'POST'}.get(cmd, 'GET')
        if method != 'GET':
            args.key = args.key or uuid.uuid4().hex
            print('Idempotency-Key=' + args.key, file=sys.stderr)
        result = call(method, '/v1/slices/' + args.id + ('/' + cmd if cmd in ('events', 'diagnostics', 'reconcile', 'start', 'stop') else ''))
    else:
        p.error('Indique una operación')
    print(json.dumps(result, indent=2))
    if isinstance(result, dict) and result.get('status') == 'FAILED':
        sys.exit(1)


if __name__ == '__main__':
    main()
