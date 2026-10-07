"""API REST del Driver Linux, sin dependencias Python externas en el headnode."""
import argparse
import fcntl
import hashlib
import hmac
import json
import os
import re
import socket
import socketserver
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .agent import inspect_image
from .backend import SSHBackend, MemoryBackend, RemoteError
from .console import Consoles
from .engine import Engine
from .model import Fault, require, validate, digest, fields, canonical
from .store import Store


class Application:
    def __init__(self, config, state, keys, simulate=False, backend=None):
        self.config = config
        self.store = Store(state, config)
        self.backend = backend or (MemoryBackend(config) if simulate else SSHBackend(config))
        self.engine = Engine(self.store, self.backend)
        self.consoles = Consoles(self.store, self.backend)
        self.keys = keys
        self.image_lock = threading.RLock()
        (self.store.directory / 'images').mkdir(exist_ok=True)

    def identity(self, bearer):
        require(bearer.startswith('Bearer '), 'Bearer token requerido', 401)
        h = hashlib.sha256(bearer[7:].encode()).hexdigest()
        for key in self.keys:
            if hmac.compare_digest(key['sha256'], h):
                return key['subject'], key['role'] in ('admin', 'service')
        raise Fault('Token inválido', 401)

    def nodes(self):
        result = []
        for name in sorted(self.backend.nodes):
            try:
                report = self.backend.call(name, 'doctor')
            except Exception as exc:
                report = {'ok': False, 'error': str(exc), 'node': name}
            if name in self.config['workers']:
                rows = self.store.rows('SELECT enabled FROM nodes WHERE id=?', (name,))
                report['enabled'] = bool(rows[0]['enabled'])
                report['capacity'] = self.config['workers'][name]['capacity']
                report['allocated'] = self.store.rows('SELECT COALESCE(SUM(cpu),0) AS vcpus, COALESCE(SUM(mem),0) AS memory_mb, COALESCE(SUM(disk),0) AS disk_gb FROM allocations WHERE worker=?', (name,))[0]
            result.append(report)
        return result

    def route(self, method, path, body, owner, admin, key):
        s = self.store
        if method == 'GET' and path == '/v1/capabilities':
            return 200, {'driver': 'linux', 'version': '2.0.0', 'simulated': self.backend.simulated,
                         'network': ['802.1ad-qinq'], 'images': ['qcow2'], 'console': 'novnc-token',
                         'topologies': ['ex1', 'lineal', 'anillo'], 'disk_unit': self.config.get('disk_unit', 'GiB'),
                         'lifecycle': ['create', 'inspect', 'start', 'stop', 'delete', 'reconcile'], 'live_migration': False}
        if method == 'GET' and path == '/v1/nodes':
            require(admin, 'Requiere rol admin/service', 403)
            return 200, self.nodes()
        match = re.fullmatch(r'/v1/nodes/([a-z][a-z0-9-]{0,31})', path)
        if method == 'PATCH' and match:
            require(admin, 'Requiere rol admin/service', 403)
            name = match.group(1)
            require(name in self.config['workers'], 'Worker inexistente', 404)
            fields(body, ('enabled',), ('enabled',))
            require(type(body['enabled']) is bool, 'enabled debe ser booleano')
            with s.tx() as db:
                db.execute('UPDATE nodes SET enabled=? WHERE id=?', (int(body['enabled']), name))
            return 200, {'node': name, 'enabled': body['enabled']}
        if path == '/v1/images' and method == 'GET':
            return 200, s.rows('SELECT * FROM images ORDER BY created')
        match = re.fullmatch(r'/v1/images/([0-9a-f]{64})', path)
        if match and method == 'DELETE':
            require(admin, 'Requiere rol admin/service', 403)
            image = match.group(1)
            with self.image_lock:
                with s.tx() as db:
                    require(not db.execute('SELECT 1 FROM allocations WHERE image=?', (image,)).fetchone(), 'Imagen referenciada por VM o reserva', 409)
                    require(db.execute('SELECT 1 FROM images WHERE id=?', (image,)).fetchone(), 'Imagen inexistente', 404)
                    # Retirar primero el catálogo; archivo huérfano si hay corte es inocuo/reimportable.
                    db.execute('DELETE FROM images WHERE id=?', (image,))
                image_file = s.directory / 'images' / (image + '.qcow2')
                if image_file.exists():
                    image_file.unlink()
            return 200, {'deleted': image, 'worker_copies': 'GC independiente; se preservan bases en uso'}
        match = re.fullmatch(r'/v1/nodes/([a-z][a-z0-9-]{0,31})/cache/gc', path)
        if match and method == 'POST':
            require(admin, 'Requiere rol admin/service', 403)
            node = match.group(1)
            require(node in self.config['workers'], 'Worker inexistente', 404)
            fields(body, ('all_unused',))
            require(type(body.get('all_unused', False)) is bool, 'all_unused debe ser booleano')
            return 200, self.backend.call(node, 'cache_gc', all_unused=body.get('all_unused', False))
        if path == '/v1/slices':
            if method == 'GET':
                return 200, s.rows('SELECT id,owner,name,status,reserved FROM slices' + ('' if admin else ' WHERE owner=?'), () if admin else (owner,))
            if method == 'POST':
                spec = validate(body, self.config)
                # La misma petición ya aceptada conserva respuesta incluso si un nodo cayó después.
                with s.tx() as db:
                    existing = s._existing(db, owner, key, {'action': 'create', 'spec': spec})
                if existing:
                    return 202, existing
                targets = {v['worker'] for v in spec['vms']} | {self.config['gateway']['name'], self.config['switch']['name']}
                for node in sorted(targets):
                    report = self.backend.call(node, 'doctor')
                    require(report['ok'], 'Preflight falló en ' + node + ': ' + '; '.join(report.get('problems', [])), 503)
                with self.image_lock:
                    job = s.create(owner, key, spec)
                s.event(job['slice_id'], job['id'], 'ACCEPTED', owner)
                return 202, job
        match = re.fullmatch(r'/v1/operations/([0-9a-f]{32})', path)
        if match and method == 'GET':
            rows = s.rows('SELECT * FROM jobs WHERE id=?', (match.group(1),))
            require(rows and (admin or rows[0]['owner'] == owner), 'Operación inexistente', 404)
            return 200, rows[0]
        match = re.fullmatch(r'/v1/slices/([0-9a-f]{32})(?:/(events|diagnostics|reconcile|start|stop))?', path)
        if match:
            sid, sub = match.groups()
            row = s.get_slice(sid, owner, admin)
            if method == 'GET' and not sub:
                return 200, row
            if method == 'DELETE' and not sub:
                return 202, s.mutate(sid, owner, admin, key, 'delete')
            if method == 'POST' and sub in ('reconcile', 'start', 'stop'):
                fields(body, ())
                return 202, s.mutate(sid, owner, admin, key, sub)
            if method == 'GET' and sub == 'events':
                return 200, s.rows('SELECT * FROM events WHERE slice_id=? ORDER BY seq DESC LIMIT 1000', (sid,))
            if method == 'GET' and sub == 'diagnostics':
                results = {}
                for node in self.engine.participants(row['plan']):
                    try:
                        results[node] = self.backend.call(node, 'inspect', sid=sid)
                    except Exception as exc:
                        results[node] = {'ok': False, 'error': str(exc)}
                return 200, {'slice_id': sid, 'nodes': results, 'simulated': self.backend.simulated}
        match = re.fullmatch(r'/v1/slices/([0-9a-f]{32})/vms/([a-z][a-z0-9-]{0,31})/console', path)
        if match and method == 'POST':
            fields(body, ('ttl',))
            return 201, self.consoles.issue(match.group(1), match.group(2), owner, admin, body.get('ttl', 120))
        match = re.fullmatch(r'/v1/slices/([0-9a-f]{32})/vms/([a-z][a-z0-9-]{0,31})/probe', path)
        if match and method == 'POST':
            fields(body, ('kind', 'target', 'packet_bytes'))
            row = s.get_slice(match.group(1), owner, admin)
            require(row['status'] == 'READY', 'Slice no disponible', 409)
            require(not self.backend.simulated, 'Sondeo requiere hardware real', 409)
            vm = next((v for v in row['plan']['vms'] if v['name'] == match.group(2)), None)
            require(vm, 'VM inexistente', 404)
            return 200, self.backend.call(vm['worker'], 'guest_probe', sid=row['id'], vm_name=vm['name'], **body)
        raise Fault('Ruta o método inexistente', 404)

    def upload(self, image, name, size, stream):
        digest(image)
        require(0 < size <= self.config['max_image_gb'] * 1024**3, 'Tamaño de imagen fuera del límite', 413)
        require(isinstance(name, str) and 1 <= len(name) <= 100, 'X-Image-Name requerido')
        path = self.store.directory / 'images' / (image + '.qcow2')
        with self.image_lock:
            tmp = path.with_suffix('.part')
            try:
                h, remaining = hashlib.sha256(), size
                with tmp.open('wb') as target:
                    while remaining:
                        data = stream.read(min(1024 * 1024, remaining))
                        require(data, 'Subida incompleta')
                        target.write(data); h.update(data); remaining -= len(data)
                    target.flush(); os.fsync(target.fileno())
                require(h.hexdigest() == image, 'Checksum SHA256 incorrecto')
                require(not self.backend.simulated, 'Importe una imagen de prueba con la CLI seed-demo en modo simulado', 409)
                info = inspect_image(tmp)
                # Nunca sobrescribir una base ya usada con otra estructura.
                os.chmod(str(tmp), 0o444)
                os.replace(str(tmp), str(path))
                with self.store.tx() as db:
                    db.execute('INSERT OR IGNORE INTO images VALUES(?,?,?,?,?)', (image, name, size, info['virtual-size'], time.time()))
                return {'id': image, 'size': size, 'virtual_size': info['virtual-size']}
            finally:
                if tmp.exists():
                    tmp.unlink()

    def close(self):
        self.engine.close(); self.consoles.close()


class Server(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 64
    def __init__(self, address, app):
        self.app = app
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(False):
            request.close(); return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release(); raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'G5Driver/1.0'

    def log_message(self, fmt, *args):
        # Sin Authorization, query strings ni contenido de tokens.
        print(canonical({'time': time.time(), 'method': self.command, 'path': urlsplit(self.path).path}), flush=True)

    def setup(self):
        super().setup()
        self.connection.settimeout(120)

    def handle_request(self):
        app = self.server.app
        try:
            path = urlsplit(self.path).path
            if self.command == 'GET' and path == '/healthz':
                return self.reply(200, {'ok': True, 'simulated': app.backend.simulated})
            owner, admin = app.identity(self.headers.get('Authorization', ''))
            if self.command == 'GET' and path == '/openapi.json':
                return self.reply(200, json.loads((Path(__file__).parent.parent / 'docs' / 'openapi.json').read_text()))
            require(not self.headers.get('Transfer-Encoding'), 'Use Content-Length, no chunked')
            length = int(self.headers.get('Content-Length', '0'))
            require(length >= 0, 'Content-Length inválido')
            upload = re.fullmatch(r'/v1/images/([0-9a-f]{64})', path)
            if self.command == 'PUT' and upload:
                require(admin, 'Requiere rol admin/service', 403)
                return self.reply(201, app.upload(upload.group(1), self.headers.get('X-Image-Name', ''), length, self.rfile))
            require(length <= 2 * 1024**2, 'JSON demasiado grande', 413)
            raw = self.rfile.read(length) if length else b'{}'
            body = json.loads(raw.decode())
            code, result = app.route(self.command, path, body, owner, admin, self.headers.get('Idempotency-Key', ''))
            self.reply(code, result)
        except Fault as exc:
            self.reply(exc.status, {'error': str(exc)})
        except (ValueError, UnicodeError, TypeError, KeyError) as exc:
            self.reply(400, {'error': 'Petición inválida: ' + str(exc)[:300]})
        except (RemoteError, socket.timeout) as exc:
            self.reply(503, {'error': str(exc)})
        except Exception as exc:
            print('INTERNAL: ' + repr(exc), flush=True)
            self.reply(500, {'error': 'Fallo interno; revisar journal del servicio'})

    def reply(self, code, value):
        data = canonical(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    do_GET = handle_request
    do_POST = handle_request
    do_DELETE = handle_request
    do_PATCH = handle_request
    do_PUT = handle_request


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', default='config/cluster.json')
    p.add_argument('--state', default='state')
    p.add_argument('--keys', default='config/keys.json')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8085)
    p.add_argument('--cert'); p.add_argument('--key')
    p.add_argument('--simulate', action='store_true')
    args = p.parse_args()
    require(args.host in ('127.0.0.1', '::1', 'localhost') or (args.cert and args.key), 'Para escuchar en red se exige certificado y clave TLS')
    os.umask(0o077)
    Path(args.state).mkdir(parents=True, exist_ok=True)
    lock = (Path(args.state) / 'api.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config = json.loads(Path(args.config).read_text())
    keys = json.loads(Path(args.keys).read_text())
    require(keys, 'Configure al menos una identidad API')
    app = Application(config, args.state, keys, args.simulate)
    server = Server((args.host, args.port), app)
    if args.cert and args.key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    app.engine.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close(); app.close()


if __name__ == '__main__':
    main()
