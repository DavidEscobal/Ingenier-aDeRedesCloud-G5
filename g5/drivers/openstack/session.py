"""Cliente REST mínimo de OpenStack con la biblioteca estándar (decisión D-02).

- Token de Keystone v3 por contraseña, acotado al proyecto por defecto o a un project_id,
  en caché hasta 2 minutos antes de expirar.
- Las URL del catálogo (http://controller:<puerto>) se reescriben con `endpoint_map`
  para pasar por los túneles del app server (decisión D-06).
- Reintentos con espera creciente ante 5xx o fallos de conexión, solo en métodos
  idempotentes: un POST repetido podría duplicar recursos y lo decide el driver.
- Las credenciales se leen de OS_* del entorno y nunca aparecen en errores ni en repr().
"""
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from ...backend import RemoteError

IDEMPOTENT = ('GET', 'HEAD', 'PUT', 'DELETE')
CREDENTIALS = ('USERNAME', 'PASSWORD', 'USER_DOMAIN_NAME', 'PROJECT_NAME', 'PROJECT_DOMAIN_NAME')
RENEW_MARGIN = 120


class OpenStackError(RemoteError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def expires_epoch(value):
    for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    raise OpenStackError('Fecha de expiración de token no reconocida: %s' % value)


class Session:
    def __init__(self, cfg, environ=None):
        env = os.environ if environ is None else environ
        missing = ['OS_' + k for k in CREDENTIALS if not env.get('OS_' + k)]
        if missing:
            raise OpenStackError('Faltan variables de entorno: ' + ', '.join(missing))
        self._credentials = {k: env['OS_' + k] for k in CREDENTIALS}
        self.auth_url = cfg['auth_url'].rstrip('/')
        self.endpoint_map = dict(cfg.get('endpoint_map', {}))
        self.interface = cfg.get('interface', 'public')
        self.timeout = cfg.get('timeout', 30)
        self.retries = cfg.get('retries', 3)
        self.retry_delay = cfg.get('retry_delay', 1)
        self.sleep = time.sleep
        self._tokens = {}
        self._lock = threading.Lock()

    def __repr__(self):
        return '<Session %s user=%s>' % (self.auth_url, self._credentials['USERNAME'])

    def rewrite(self, url):
        for prefix, target in self.endpoint_map.items():
            if url.startswith(prefix):
                return target.rstrip('/') + url[len(prefix):]
        return url

    def _scope(self, project_id):
        if project_id:
            return {'project': {'id': project_id}}
        return {'project': {'name': self._credentials['PROJECT_NAME'],
                            'domain': {'name': self._credentials['PROJECT_DOMAIN_NAME']}}}

    def _authenticate(self, project_id):
        c = self._credentials
        body = {'auth': {'identity': {'methods': ['password'], 'password': {'user': {
            'name': c['USERNAME'], 'domain': {'name': c['USER_DOMAIN_NAME']}, 'password': c['PASSWORD']}}},
            'scope': self._scope(project_id)}}
        status, data, headers = self._send('POST', self.rewrite(self.auth_url + '/auth/tokens'), body, {}, retry=True)
        token = headers.get('X-Subject-Token')
        if status != 201 or not token:
            raise OpenStackError('Keystone no entregó token (HTTP %s)' % status, status)
        catalog = {}
        for service in data['token'].get('catalog', []):
            for endpoint in service['endpoints']:
                if endpoint['interface'] == self.interface:
                    catalog[service['type']] = self.rewrite(endpoint['url']).rstrip('/')
        return {'token': token, 'expires': expires_epoch(data['token']['expires_at']),
                'catalog': catalog, 'project': data['token'].get('project', {}),
                'user': data['token'].get('user', {})}

    def _auth(self, project_id=None, refresh=False):
        with self._lock:
            entry = self._tokens.get(project_id)
            if refresh or not entry or entry['expires'] - time.time() < RENEW_MARGIN:
                entry = self._tokens[project_id] = self._authenticate(project_id)
            return entry

    def token(self, project_id=None):
        return self._auth(project_id)['token']

    def project(self, project_id=None):
        return self._auth(project_id)['project']

    def user(self):
        return self._auth()['user']

    def endpoint(self, service, project_id=None):
        catalog = self._auth(project_id)['catalog']
        if service not in catalog:
            raise OpenStackError('Servicio ausente del catálogo: ' + service)
        return catalog[service]

    def request(self, method, service, path, body=None, project_id=None, headers=None):
        """Devuelve (status, json o None, headers). Eleva OpenStackError en HTTP >= 400."""
        reauthenticated = False
        while True:
            entry = self._auth(project_id)
            if service not in entry['catalog']:
                raise OpenStackError('Servicio ausente del catálogo: ' + service)
            extra = dict(headers or {}, **{'X-Auth-Token': entry['token']})
            try:
                return self._send(method, entry['catalog'][service] + path, body, extra, retry=method in IDEMPOTENT)
            except OpenStackError as exc:
                if exc.status == 401 and not reauthenticated:
                    self._auth(project_id, refresh=True)
                    reauthenticated = True
                    continue
                raise

    def _send(self, method, url, body, headers, retry):
        data = json.dumps(body).encode() if body is not None else None
        headers = dict(headers, Accept='application/json')
        if data is not None:
            headers['Content-Type'] = 'application/json'
        path = urllib.parse.urlsplit(url).path
        attempts = self.retries if retry else 1
        for attempt in range(attempts):
            request = urllib.request.Request(url, data, headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    return response.status, (json.loads(raw) if raw else None), response.headers
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors='replace')[:300]
                error = OpenStackError('%s %s -> HTTP %s: %s' % (method, path, exc.code, detail), exc.code)
                if exc.code < 500:
                    raise error
            except (urllib.error.URLError, socket.timeout, ConnectionError) as exc:
                error = OpenStackError('%s %s -> sin respuesta: %s' % (method, path, getattr(exc, 'reason', exc)))
            if attempt + 1 < attempts:
                self.sleep(min(2 ** attempt, 8) * self.retry_delay)
        raise error
