"""OpenStack falso en un hilo (Keystone + rutas configurables) para probar sin el clúster real."""
import json
import threading
import time
import urllib.parse
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
        self.routes, self.failures, self.token_project = {}, {}, {}
        self.handler = None
        self.lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def handle_any(self):
                length = int(self.headers.get('Content-Length', '0'))
                raw = self.rfile.read(length) if length else b''
                binary = self.headers.get('Content-Type') == 'application/octet-stream'
                body = raw if binary else (json.loads(raw) if raw else None)
                path = self.path.split('?')[0]
                status, payload, headers = fake.dispatch(self.command, path, self.path, body, self.headers)
                raw_out = isinstance(payload, bytes)
                data = payload if raw_out else (json.dumps(payload).encode() if payload is not None else b'')
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header('Content-Type', 'application/octet-stream' if raw_out else 'application/json')
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
        request = {'method': method, 'path': path, 'raw_path': raw_path, 'body': body, 'headers': headers,
                   'project': self.token_project.get(headers.get('X-Auth-Token'))}
        fn = self.routes.get((method, path))
        if fn:
            status, payload = fn(request)
            return status, payload, {}
        if self.handler:
            with self.lock:
                status, payload = self.handler(request)
            return status, payload, {}
        return 404, {'itemNotFound': {'message': 'ruta falsa inexistente'}}, {}

    def auth(self, body):
        user = body['auth']['identity']['password']['user']
        if (user['name'], user['password']) != (USER['OS_USERNAME'], USER['OS_PASSWORD']):
            return 401, {'error': 'credenciales'}, {}
        with self.lock:
            self.auth_bodies.append(body)
            token = 'tok-' + uuid.uuid4().hex
            self.tokens.append(token)
            scope = body['auth']['scope']['project']
            self.token_project[token] = scope.get('id', 'p-cloud-admin')
        expires = time.strftime('%Y-%m-%dT%H:%M:%S.000000Z', time.gmtime(time.time() + self.token_ttl))
        catalog = [{'type': t, 'name': n, 'endpoints': [{'interface': 'public', 'url': u}]} for t, n, u in (
            ('identity', 'keystone', 'http://controller:5000/v3/'), ('compute', 'nova', 'http://controller:8774/v2.1'),
            ('network', 'neutron', 'http://controller:9696'), ('image', 'glance', 'http://controller:9292'))]
        token_body = {'token': {'expires_at': expires, 'catalog': catalog,
                                'user': {'id': 'u-cloud-admin', 'name': USER['OS_USERNAME']},
                                'project': {'id': scope.get('id', 'p-cloud-admin'), 'name': scope.get('name', 'scoped')}}}
        return 201, token_body, {'X-Subject-Token': token}


class FakeCloud:
    """Estado mínimo de Keystone/Neutron/Nova/Glance para probar el driver de punta a punta."""
    def __init__(self, fake, build_polls=1):
        self.build_polls = build_polls
        self.domains = [{'id': 'd-cloud', 'name': 'Cloud'}]
        self.roles = [{'id': 'r-admin', 'name': 'admin'}]
        self.projects = {'p-cloud-admin': {'id': 'p-cloud-admin', 'name': 'cloud_admin', 'domain_id': 'd-cloud'}}
        self.assignments = set()
        self.networks, self.subnets, self.ports, self.servers = {}, {}, {}, {}
        self.flavors = [{'id': 'f-lab5', 'name': '512MBRAM_1VCPUs_4GBRoot', 'vcpus': 1, 'ram': 512, 'disk': 4}]
        self.images = [{'id': 'img-cirros', 'name': 'cirros', 'status': 'active'}]
        self.error_names, self.hosts, self.log = set(), ['worker1', 'worker2', 'worker3'], []
        fake.handler = self.handle

    @staticmethod
    def new(prefix):
        return prefix + '-' + uuid.uuid4().hex[:12]

    def handle(self, r):
        method, parts = r['method'], [p for p in r['path'].split('/') if p]
        query = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(r['raw_path']).query).items()}
        body, project = r['body'] or {}, r['project']
        self.log.append((method, r['path']))
        root, rest = parts[0], parts[1:]
        if root == 'v3':
            return self.keystone(method, rest, query, body)
        if root == 'v2.0':
            return self.neutron(method, rest, query, body, project)
        if root == 'v2.1':
            return self.nova(method, rest, query, body, project)
        if root == 'v2' and rest == ['images']:
            if method == 'POST':
                image = dict(body, id=self.new('img'), status='queued', size=None)
                self.images.append(image)
                return 201, image
            return 200, {'images': [{k: v for k, v in i.items() if k != 'data'} for i in self.images
                                    if query.get('name') in (None, i['name'])]}
        if root == 'v2' and len(rest) >= 2 and rest[0] == 'images':
            image = next((i for i in self.images if i['id'] == rest[1]), None)
            if image is None:
                return 404, {'error': 'imagen'}
            if method == 'PUT' and rest[2:] == ['file']:
                if image['name'] in self.error_names:
                    return 500, {'error': 'falla inyectada en Glance'}
                image.update(status='active', size=len(body), data=body)
                return 204, None
            if method == 'GET' and rest[2:] == ['file']:
                return 200, image.get('data', b'')
            if method == 'GET':
                return 200, {k: v for k, v in image.items() if k != 'data'}
            if method == 'DELETE':
                self.images.remove(image)
                return 204, None
        return 404, {'error': 'ruta'}

    @staticmethod
    def match(items, query, keys):
        return [x for x in items if all(query.get(k) in (None, x.get(k)) for k in keys)]

    def keystone(self, method, rest, query, body):
        if rest == ['domains']:
            return 200, {'domains': self.match(self.domains, query, ('name',))}
        if rest == ['roles']:
            return 200, {'roles': self.match(self.roles, query, ('name',))}
        if rest == ['projects'] and method == 'GET':
            return 200, {'projects': self.match(list(self.projects.values()), query, ('name', 'domain_id'))}
        if rest == ['projects'] and method == 'POST':
            p = dict(body['project'], id=self.new('p'))
            self.projects[p['id']] = p
            return 201, {'project': p}
        if len(rest) == 2 and method == 'DELETE':
            return (204, None) if self.projects.pop(rest[1], None) else (404, {'error': 'proyecto'})
        if len(rest) == 6 and method == 'PUT':
            self.assignments.add((rest[1], rest[3], rest[5]))
            return 204, None
        return 404, {'error': 'keystone'}

    def neutron(self, method, rest, query, body, project):
        tables = {'networks': self.networks, 'subnets': self.subnets, 'ports': self.ports}
        table = tables[rest[0]]
        kind = rest[0][:-1]
        if method == 'GET' and len(rest) == 1:
            return 200, {rest[0]: self.match(list(table.values()), query, ('name', 'project_id', 'network_id'))}
        if method == 'POST':
            item = dict(body[kind], id=self.new(kind[:3]), project_id=project, status='ACTIVE')
            if kind == 'port':
                if item.get('fixed_ips'):
                    ip = item['fixed_ips'][0]['ip_address']
                    if any(f['ip_address'] == ip for p in self.ports.values() if p['network_id'] == item['network_id'] for f in p['fixed_ips']):
                        return 409, {'NeutronError': {'message': 'IP en uso'}}
                elif any(sn['network_id'] == item['network_id'] for sn in self.subnets.values()):
                    item['fixed_ips'] = [{'ip_address': 'auto'}]   # IPAM de Neutron: solo si la red tiene subred
                else:
                    item['fixed_ips'] = []
                item['device_id'] = ''
            table[item['id']] = item
            return 201, {kind: item}
        if method == 'DELETE':
            rid = rest[1]
            if rid not in table:
                return 404, {'NeutronError': {'message': 'no existe'}}
            if kind == 'network' and any(p['network_id'] == rid for p in self.ports.values()):
                return 409, {'NeutronError': {'message': 'red con puertos'}}
            if kind == 'network':
                for sid in [s for s, v in self.subnets.items() if v['network_id'] == rid]:
                    del self.subnets[sid]
            del table[rid]
            return 204, None
        return 404, {'error': 'neutron'}

    def nova(self, method, rest, query, body, project):
        if rest == ['flavors', 'detail']:
            return 200, {'flavors': self.flavors}
        if rest == ['flavors'] and method == 'POST':
            f = dict(body['flavor'], id=self.new('f'))
            self.flavors.append(f)
            return 200, {'flavor': f}
        if rest == ['servers'] and method == 'GET':
            name = query.get('name', '').strip('^$')
            scope = query.get('project_id') if query.get('all_tenants') else project
            items = [s for s in self.servers.values() if s['project_id'] == scope and name in ('', s['name'])]
            return 200, {'servers': [{'id': s['id'], 'name': s['name']} for s in items]}
        if rest == ['servers'] and method == 'POST':
            b = body['server']
            if not any(f['id'] == b['flavorRef'] for f in self.flavors) or not any(i['id'] == b['imageRef'] for i in self.images):
                return 400, {'badRequest': {'message': 'flavor o imagen'}}
            for p in b['networks']:
                if p['port'] not in self.ports:
                    return 400, {'badRequest': {'message': 'puerto'}}
            s = {'id': self.new('srv'), 'name': b['name'], 'project_id': project, 'status': 'BUILD', 'polls': 0,
                 'ports': [p['port'] for p in b['networks']], 'host': self.hosts[len(self.servers) % len(self.hosts)]}
            for p in s['ports']:
                self.ports[p]['device_id'] = s['id']
            self.servers[s['id']] = s
            return 202, {'server': {'id': s['id']}}
        if len(rest) >= 2 and rest[0] == 'servers':
            s = self.servers.get(rest[1])
            if not s:
                return 404, {'itemNotFound': {'message': 'servidor'}}
            if method == 'GET' and len(rest) == 2:
                if s['status'] == 'BUILD':
                    s['polls'] += 1
                    if s['polls'] > self.build_polls:
                        s['status'] = 'ERROR' if any(s['name'].endswith(x) for x in self.error_names) else 'ACTIVE'
                view = {'id': s['id'], 'name': s['name'], 'status': s['status'], 'OS-EXT-SRV-ATTR:host': s['host']}
                if s['status'] == 'ERROR':
                    view['fault'] = {'message': 'No valid host was found'}
                return 200, {'server': view}
            if method == 'DELETE':
                for p in s['ports']:
                    if p in self.ports:
                        self.ports[p]['device_id'] = ''
                del self.servers[rest[1]]
                return 204, None
            if rest[2:] == ['action']:
                s['status'] = 'SHUTOFF' if 'os-stop' in body else 'ACTIVE'
                return 202, None
            if rest[2:] == ['remote-consoles']:
                return 200, {'remote_console': {'type': 'novnc', 'url': 'http://controller:6080/vnc_auto.html?path=%3Ftoken%3Dabc'}}
        return 404, {'error': 'nova'}
