"""Consola web mínima (R1B) sobre la API del Driver Linux.

Se ejecuta en server4 como ubuntu y escucha SOLO en 127.0.0.1. Se accede desde la
notebook con un túnel SSH. El token de la API se lee en el servidor y nunca llega al
navegador. Los despliegues hechos desde la web dejan una carpeta evidencias/ui-* con
el mismo deployment.json que g5.demo, así que `g5.demo status/consoles/cleanup` y
`scripts/validate_ex1.py` funcionan igual sobre ellos.

Uso:
    python3 -m g5.web --port 8090
"""
import argparse
import ast
import contextlib
import io
import json
import os
import re
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit
from .cli import request
from .model import validate

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ('ex1', 'ex1-b', 'lineal', 'anillo')
API_PATH = re.compile(r'/v1/[a-z0-9/_-]{0,200}')
MAX_BODY = 64 * 1024


def scrub(value):
    """Quita secretos del invitado (hash de contraseña, claves) antes de enviarlos al navegador."""
    if isinstance(value, dict):
        value = dict(value)
        value.pop('spec', None)
        if isinstance(value.get('guest'), dict):
            value['guest'] = {'os': value['guest'].get('os')}
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


class UI:
    def __init__(self, args):
        self.api = args.api
        self.token = Path(args.token_file).read_text().strip()
        self.config = json.loads(Path(args.config).read_text())
        self.generated = Path(args.generated)
        self.evidence = Path(args.evidence)
        self.index = (ROOT / 'web' / 'index.html').read_bytes()

    def call(self, method, path, body=None, key=None):
        return request(self.api, self.token, method, path, body, key=key)

    def templates(self):
        result = []
        for name in TEMPLATES:
            path = self.generated / (name + '.json')
            if not path.exists():
                continue
            spec = json.loads(path.read_text())
            links = [n['name'] for n in spec['networks'] if not n['name'].startswith('access')]
            result.append({'name': name, 'vms': len(spec['vms']), 'links': links,
                           'internet': [v['name'] for v in spec['vms'] if v.get('internet')],
                           'ports': [x['external_port'] for x in spec.get('publications', [])],
                           'workers': sorted({v['worker'] for v in spec['vms']})})
        return result

    def runs(self):
        out = {}
        if self.evidence.exists():
            for journal in self.evidence.glob('*/deployment.json'):
                try:
                    sid = json.loads(journal.read_text())['job']['slice_id']
                except (ValueError, KeyError, OSError):
                    continue
                out.setdefault(sid, []).append(journal.parent.name)
        return out

    def deploy(self, body):
        name = body.get('template')
        if name not in TEMPLATES:
            raise ValueError('Plantilla no admitida')
        path = self.generated / (name + '.json')
        if not path.exists():
            raise ValueError('No existe generated/%s.json: ejecute primero g5.demo build' % name)
        spec = validate(json.loads(path.read_text()), self.config)
        run = self.evidence / ('ui-%s-%s' % (name, time.strftime('%Y%m%dT%H%M%S')))
        run.mkdir(parents=True, exist_ok=False)
        journal = {'spec': spec, 'key': uuid.uuid4().hex, 'created': time.time(), 'source': 'g5.web'}
        save(run / 'deployment.json', journal)  # clave guardada ANTES de enviar, igual que g5.demo
        try:
            job = self.call('POST', '/v1/slices', spec, journal['key'])
        except RuntimeError as exc:
            # 4xx/503 = rechazo definitivo (capacidad, preflight): no dejar carpeta huérfana.
            if re.match(r'HTTP (4\d\d|503):', str(exc)):
                (run / 'deployment.json').unlink()
                run.rmdir()
            raise
        journal['job'] = job
        save(run / 'deployment.json', journal)
        return {'job': job, 'run': str(run)}

    def snapshot(self, body):
        from .demo import snapshot
        sid = body.get('slice_id', '')
        names = self.runs().get(sid)
        if not names:
            raise LookupError('Slice sin carpeta de evidencias (no se creó con g5.demo ni con la web)')
        run = self.evidence / sorted(names)[-1]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            snapshot(self.call, run)
        return {'run': str(run), 'output': buffer.getvalue()}


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    os.chmod(str(tmp), 0o600)
    os.replace(str(tmp), str(path))


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    server_version = 'G5Web/1.0'

    def log_message(self, fmt, *args):
        print(json.dumps({'time': time.time(), 'method': self.command, 'path': urlsplit(self.path).path}), flush=True)

    def send(self, code, value, ctype='application/json; charset=utf-8'):
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self):
        ui = self.server.ui
        path = urlsplit(self.path).path
        host = (self.headers.get('Host') or '').split(':')[0]
        if host not in ('127.0.0.1', 'localhost'):
            return self.send(403, {'error': 'Acceda por el túnel SSH a 127.0.0.1'})
        if self.command != 'GET' and self.headers.get('X-G5-UI') != '1':
            return self.send(403, {'error': 'Cabecera X-G5-UI requerida'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= MAX_BODY:
                return self.send(413, {'error': 'Cuerpo demasiado grande'})
            body = json.loads(self.rfile.read(length).decode()) if length else {}
            if self.command == 'GET' and path in ('/', '/index.html'):
                return self.send(200, ui.index, 'text/html; charset=utf-8')
            if self.command == 'GET' and path == '/ui/templates':
                return self.send(200, ui.templates())
            if self.command == 'GET' and path == '/ui/runs':
                return self.send(200, ui.runs())
            if self.command == 'POST' and path == '/ui/deploy':
                return self.send(202, ui.deploy(body))
            if self.command == 'POST' and path == '/ui/snapshot':
                return self.send(200, ui.snapshot(body))
            if path.startswith('/api/') and API_PATH.fullmatch(path[4:]) and '..' not in path:
                key = self.headers.get('X-Idempotency-Key') or None
                if key is not None and not re.fullmatch(r'[0-9a-f]{32}', key):
                    return self.send(400, {'error': 'Clave de idempotencia inválida'})
                result = ui.call(self.command, path[4:], body if self.command != 'GET' else None, key)
                return self.send(200, scrub(result))
            return self.send(404, {'error': 'Ruta inexistente'})
        except LookupError as exc:
            self.send(404, {'error': str(exc)})
        except RuntimeError as exc:
            # request() de la CLI eleva 'HTTP <código>: {...}'
            match = re.match(r'HTTP (\d{3}): (.*)', str(exc), re.S)
            if not match:
                return self.send(502, {'error': str(exc)})
            try:
                detail = ast.literal_eval(match.group(2)).get('error', match.group(2))
            except (ValueError, SyntaxError, AttributeError):
                detail = match.group(2)
            self.send(int(match.group(1)), {'error': detail})
        except (ValueError, KeyError, TypeError) as exc:
            self.send(400, {'error': str(exc)[:300]})
        except OSError as exc:
            self.send(502, {'error': 'API del driver no disponible: ' + str(exc)[:200]})

    do_GET = do_POST = do_DELETE = do_PATCH = handle_any


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default=os.environ.get('G5_API_URL', 'http://127.0.0.1:8085'))
    p.add_argument('--token-file', default='config/admin.token')
    p.add_argument('--config', default='config/cluster.json')
    p.add_argument('--generated', default='generated')
    p.add_argument('--evidence', default='evidencias')
    p.add_argument('--port', type=int, default=8090)
    args = p.parse_args()
    os.umask(0o077)
    server = Server(('127.0.0.1', args.port), Handler)
    server.ui = UI(args)
    print('G5 web en http://127.0.0.1:%d (solo loopback; use túnel SSH)' % args.port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    sys.exit(main())
