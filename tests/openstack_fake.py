"""OpenStack falso en un hilo (Keystone + rutas configurables) para probar sin el clúster real."""
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

USER = {'OS_USERNAME': 'cloud_admin', 'OS_PASSWORD': 'not-a-real-secret', 'OS_USER_DOMAIN_NAME': 'Cloud',
        'OS_PROJECT_NAME': 'cloud_admin', 'OS_PROJECT_DOMAIN_NAME': 'Cloud'}


class FakeOpenStack:
    """Keystone emite tokens; el resto de rutas se registran con `route(method, path, fn)`.

    fn(request) -> (status, body) ; `fail(method, path, *codes)` encola respuestas de error.
    """
    def __init__(self, token_ttl=3600):
        self.token_ttl = token_ttl
        self.tokens, self.auth_bodies, self.requests = [], [], []
        self.routes, self.failures = {}, {}
        self.lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def handle_any(self):
                length = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(length)) if length else None
                path = self.path.split('?')[0]
                status, payload, headers = fake.dispatch(self.command, path, self.path, body, self.headers)
                data = json.dumps(payload).encode() if payload is not None else b''
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            do_GET = do_POST = do_PUT = do_DELETE = handle_any

        class Server(ThreadingMixIn, HTTPServer):
            daemon_threads = True

        self.server = Server(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.base = 'http://127.0.0.1:%d' % self.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def config(self, **extra):
        cfg = {'auth_url': 'http://controller:5000/v3', 'retry_delay': 0,
               'endpoint_map': {'http://controller:%d' % p: self.base for p in (5000, 8774, 9696, 9292)}}
        cfg.update(extra)
        return cfg

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def route(self, method, path, fn):
        self.routes[(method, path)] = fn

    def fail(self, method, path, *codes):
        self.failures.setdefault((method, path), []).extend(codes)

    def valid(self, headers):
        return headers.get('X-Auth-Token') in self.tokens

    def dispatch(self, method, path, raw_path, body, headers):
        with self.lock:
            self.requests.append((method, path, headers.get('X-Auth-Token')))
            queued = self.failures.get((method, path))
            if queued:
                return queued.pop(0), {'error': 'inyectado'}, {}
        if (method, path) == ('POST', '/v3/auth/tokens'):
            return self.auth(body)
        if not self.valid(headers):
            return 401, {'error': 'token inválido'}, {}
        fn = self.routes.get((method, path))
        if not fn:
            return 404, {'itemNotFound': {'message': 'ruta falsa inexistente'}}, {}
        status, payload = fn({'method': method, 'path': path, 'raw_path': raw_path, 'body': body, 'headers': headers})
        return status, payload, {}

    def auth(self, body):
        user = body['auth']['identity']['password']['user']
        if (user['name'], user['password']) != (USER['OS_USERNAME'], USER['OS_PASSWORD']):
            return 401, {'error': 'credenciales'}, {}
        with self.lock:
            self.auth_bodies.append(body)
            token = 'tok-' + uuid.uuid4().hex
            self.tokens.append(token)
        expires = time.strftime('%Y-%m-%dT%H:%M:%S.000000Z', time.gmtime(time.time() + self.token_ttl))
        scope = body['auth']['scope']['project']
        catalog = [{'type': t, 'name': n, 'endpoints': [{'interface': 'public', 'url': u}]} for t, n, u in (
            ('identity', 'keystone', 'http://controller:5000/v3/'), ('compute', 'nova', 'http://controller:8774/v2.1'),
            ('network', 'neutron', 'http://controller:9696'), ('image', 'glance', 'http://controller:9292'))]
        token_body = {'token': {'expires_at': expires, 'catalog': catalog,
                                'project': {'id': scope.get('id', 'p-cloud-admin'), 'name': scope.get('name', 'scoped')}}}
        return 201, token_body, {'X-Subject-Token': token}
