"""Tokens breves por VM y túneles VNC locales que se cierran al expirar."""
import hashlib
import secrets
import socket
import sqlite3
import threading
import time
from urllib.parse import urlencode
from .model import require


class ExpiringToken:
    """Interfaz token_plugin.lookup de websockify; la BD nunca almacena el token crudo."""
    def __init__(self, source):
        self.source = str(source)

    def lookup(self, token):
        if not isinstance(token, str) or len(token) > 128:
            return None
        h = hashlib.sha256(token.encode()).hexdigest()
        db = sqlite3.connect('file:' + self.source + '?mode=ro', uri=True, timeout=5)
        try:
            row = db.execute("SELECT t.port FROM tokens t JOIN slices s ON s.id=t.slice_id WHERE t.hash=? AND t.revoked=0 AND t.expires>? AND s.status='READY'", (h, time.time())).fetchone()
            return ['127.0.0.1', str(row[0])] if row else None
        finally:
            db.close()


class Consoles:
    def __init__(self, store, backend):
        self.store, self.backend = store, backend
        self.tunnels = {}
        self.guard = threading.RLock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.janitor, daemon=True)
        self.thread.start()

    def issue(self, sid, vm_name, owner, admin, ttl=120):
        require(type(ttl) is int and 30 <= ttl <= 600, 'TTL permitido: 30..600 s')
        require(not self.backend.simulated, 'La consola exige un backend SSH real', 409)
        with self.guard:
            row = self.store.get_slice(sid, owner, admin)
            require(row['status'] == 'READY', 'Slice no disponible', 409)
            vm = next((v for v in row['plan']['vms'] if v['name'] == vm_name), None)
            require(vm, 'VM inexistente', 404)
            report = self.backend.call(vm['worker'], 'inspect', sid=sid)
            require(report['vms'][vm_name]['running'], 'VM no está ejecutándose', 409)
            process = None
            for _ in range(5):
                with socket.socket() as s:
                    s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
                try:
                    process = self.backend.tunnel(vm['worker'], port, vm['vnc'], ttl)
                    break
                except Exception:
                    continue
            require(process is not None, 'No se pudo abrir el túnel VNC', 503)
            token = secrets.token_urlsafe(32)
            h = hashlib.sha256(token.encode()).hexdigest()
            expires = time.time() + ttl
            try:
                with self.store.tx() as db:
                    current = db.execute('SELECT status FROM slices WHERE id=?', (sid,)).fetchone()
                    require(current and current[0] == 'READY', 'Slice cambió de estado', 409)
                    db.execute('UPDATE tokens SET revoked=1 WHERE slice_id=? AND vm=?', (sid, vm_name))
                    db.execute('INSERT INTO tokens(hash,slice_id,vm,port,expires) VALUES(?,?,?,?,?)', (h, sid, vm_name, port, expires))
            except Exception:
                process.terminate(); process.wait(timeout=5)
                raise
            self.tunnels[h] = process
            self.store.event(sid, None, 'CONSOLE', owner + '/' + vm_name)
            return {'token': token, 'expires_at': expires,
                    'url': self.store.config['console_url'].rstrip('/') + '/vnc.html?' + urlencode({'autoconnect': 'true', 'path': 'websockify?token=' + token})}

    def janitor(self):
        while not self.stop.wait(1):
            with self.guard:
                for h, process in list(self.tunnels.items()):
                    rows = self.store.rows('SELECT revoked,expires FROM tokens WHERE hash=?', (h,))
                    if not rows or rows[0]['revoked'] or rows[0]['expires'] <= time.time() or process.poll() is not None:
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=2)
                            except Exception:
                                process.kill(); process.wait()
                        del self.tunnels[h]

    def close(self):
        self.stop.set(); self.thread.join(timeout=5)
        with self.guard:
            for process in self.tunnels.values():
                if process.poll() is None:
                    process.terminate()
            with self.store.tx() as db:
                db.execute('UPDATE tokens SET revoked=1')


def serve():
    import argparse
    from pathlib import Path
    from websockify import WebSocketProxy
    from websockify.websocketproxy import ProxyRequestHandler
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    parser.add_argument('--port', type=int, default=6080)
    parser.add_argument('--web', default='/usr/share/novnc')
    args = parser.parse_args()

    class PrivateHandler(ProxyRequestHandler):
        def log_message(self, fmt, *values):
            # No registrar URLs que contienen credenciales de consola.
            return
    proxy = WebSocketProxy(listen_host='127.0.0.1', listen_port=args.port,
                           web=args.web, token_plugin=ExpiringToken(Path(args.state) / 'cluster.db'),
                           RequestHandlerClass=PrivateHandler)
    proxy.start_server()


if __name__ == '__main__':
    serve()
