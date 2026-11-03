"""Reservas, estado y cola durables en transacciones SQLite cortas."""
import contextlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from .domain import provider_of
from .model import require, canonical, fingerprint


class Store:
    def __init__(self, directory, config, drivers=None):
        from .drivers import default_drivers
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = str(self.directory / 'cluster.db')
        self.config = config
        self.drivers = drivers or default_drivers(config)
        with self.tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS slices(id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT,
                spec TEXT NOT NULL, plan TEXT NOT NULL, status TEXT NOT NULL, reserved INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, slice_id TEXT NOT NULL, owner TEXT,
                action TEXT, status TEXT, attempts INTEGER DEFAULT 0, error TEXT, created REAL, updated REAL);
            CREATE TABLE IF NOT EXISTS keys(owner TEXT, key TEXT, hash TEXT, job TEXT,
                PRIMARY KEY(owner,key));
            CREATE TABLE IF NOT EXISTS leases(svid INTEGER PRIMARY KEY, slice_id TEXT UNIQUE, slot INTEGER UNIQUE);
            CREATE TABLE IF NOT EXISTS allocations(slice_id TEXT, vm TEXT, worker TEXT, cpu INTEGER,
                mem INTEGER, disk INTEGER, image TEXT, vnc INTEGER, PRIMARY KEY(slice_id,vm), UNIQUE(worker,vnc));
            CREATE TABLE IF NOT EXISTS ports(protocol TEXT, port INTEGER, slice_id TEXT, PRIMARY KEY(protocol,port));
            CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY, name TEXT, size INTEGER, virtual_size INTEGER, created REAL);
            CREATE TABLE IF NOT EXISTS nodes(id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, slice_id TEXT, job TEXT,
                timestamp REAL, event TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY, slice_id TEXT, vm TEXT, port INTEGER,
                expires REAL, revoked INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS resources(slice_id TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
                external_id TEXT, status TEXT NOT NULL, created REAL, updated REAL, PRIMARY KEY(slice_id,kind,name));
            ''')
            # Migración de bases EX1: los slices existentes pertenecen al driver Linux.
            if 'provider' not in {r['name'] for r in db.execute('PRAGMA table_info(slices)')}:
                db.execute("ALTER TABLE slices ADD COLUMN provider TEXT NOT NULL DEFAULT 'linux'")
            for node in config['workers']:
                db.execute('INSERT OR IGNORE INTO nodes(id) VALUES(?)', (node,))
            missing = [r[0] for r in db.execute('SELECT DISTINCT worker FROM allocations') if r[0] not in config['workers']]
            require(not missing, 'No retire workers con reservas: ' + ','.join(missing), 409)

    @contextlib.contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA foreign_keys=ON')
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, args=()):
        with self.tx() as db:
            return [dict(r) for r in db.execute(sql, args)]

    def event(self, sid, jid, event, detail=''):
        with self.tx() as db:
            db.execute('INSERT INTO events(slice_id,job,timestamp,event,detail) VALUES(?,?,?,?,?)',
                       (sid, jid, time.time(), event, str(detail)[:8000]))

    def _existing(self, db, owner, key, value):
        require(isinstance(key, str) and 8 <= len(key) <= 128, 'Idempotency-Key requerido (8..128 caracteres)')
        row = db.execute('SELECT * FROM keys WHERE owner=? AND key=?', (owner, key)).fetchone()
        if row:
            require(row['hash'] == fingerprint(value), 'Idempotency-Key reutilizada con otra petición', 409)
            return dict(db.execute('SELECT * FROM jobs WHERE id=?', (row['job'],)).fetchone())

    def _job(self, db, sid, owner, key, value, action):
        jid, now = uuid.uuid4().hex, time.time()
        db.execute('INSERT INTO jobs(id,slice_id,owner,action,status,created,updated) VALUES(?,?,?,?,?,?,?)',
                   (jid, sid, owner, action, 'PENDING', now, now))
        db.execute('INSERT INTO keys VALUES(?,?,?,?)', (owner, key, fingerprint(value), jid))
        return dict(db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone())

    def create(self, owner, key, spec):
        value = {'action': 'create', 'spec': spec}
        with self.tx() as db:
            existing = self._existing(db, owner, key, value)
            if existing:
                return existing
            sid = uuid.uuid4().hex
            plan = json.loads(canonical(spec))
            plan['id'] = sid
            # Cada proveedor reserva lo suyo dentro de esta misma transacción: todo o nada.
            provider = provider_of(spec)
            self.drivers[provider].reserve(db, sid, plan)
            db.execute('INSERT INTO slices(id,owner,name,spec,plan,status,reserved,provider) VALUES(?,?,?,?,?,?,1,?)',
                       (sid, owner, spec['name'], canonical(spec), canonical(plan), 'QUEUED', provider))
            return self._job(db, sid, owner, key, value, 'create')

    def mutate(self, sid, owner, admin, key, action):
        value = {'action': action, 'slice_id': sid}
        with self.tx() as db:
            existing = self._existing(db, owner, key, value)
            if existing:
                return existing
            row = db.execute('SELECT * FROM slices WHERE id=?', (sid,)).fetchone()
            require(row and (admin or row['owner'] == owner), 'Slice inexistente', 404)
            active = db.execute("SELECT 1 FROM jobs WHERE slice_id=? AND status IN ('PENDING','RUNNING')", (sid,)).fetchone()
            require(not active, 'El slice tiene una operación activa', 409)
            if action == 'reconcile':
                require(row['reserved'] and row['status'] in ('READY', 'ERROR'), 'Solo se reconcilian slices con reservas', 409)
            if action == 'stop':
                require(row['reserved'] and row['status'] == 'READY', 'Solo se detienen slices READY', 409)
            if action == 'start':
                require(row['reserved'] and row['status'] == 'STOPPED', 'Solo se arrancan slices STOPPED', 409)
            db.execute('UPDATE tokens SET revoked=1 WHERE slice_id=?', (sid,))
            db.execute('UPDATE slices SET status=? WHERE id=?', ({'delete': 'DELETING', 'reconcile': 'RECONCILING', 'stop': 'STOPPING', 'start': 'STARTING'}[action], sid))
            return self._job(db, sid, owner, key, value, action)

    def release(self, sid, status):
        with self.tx() as db:
            for table in ('allocations', 'leases', 'ports'):
                db.execute('DELETE FROM ' + table + ' WHERE slice_id=?', (sid,))
            db.execute('UPDATE tokens SET revoked=1 WHERE slice_id=?', (sid,))
            db.execute('UPDATE slices SET reserved=0,status=? WHERE id=?', (status, sid))

    def get_slice(self, sid, owner=None, admin=True):
        rows = self.rows('SELECT * FROM slices WHERE id=?', (sid,))
        require(rows and (admin or rows[0]['owner'] == owner), 'Slice inexistente', 404)
        row = rows[0]
        for key in ('plan', 'spec'):
            row[key] = json.loads(row[key])
        return row

    def claim(self):
        with self.tx() as db:
            row = db.execute("SELECT * FROM jobs WHERE status='PENDING' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='RUNNING',attempts=attempts+1,updated=? WHERE id=?", (time.time(), row['id']))
            return dict(row)

    def recover(self):
        with self.tx() as db:
            db.execute("UPDATE jobs SET status='PENDING' WHERE status='RUNNING'")
            db.execute('UPDATE tokens SET revoked=1')

    def finish(self, jid, status, error=None):
        with self.tx() as db:
            db.execute('UPDATE jobs SET status=?,error=?,updated=? WHERE id=?', (status, error, time.time(), jid))

    def status(self, sid, value):
        with self.tx() as db:
            db.execute('UPDATE slices SET status=? WHERE id=?', (value, sid))

    # Diario de recursos del proveedor (UUID de OpenStack, etc.). Se registra PENDING antes de
    # pedir la creación, para que un corte deje rastro de lo que pudo quedar creado.
    def resource_pending(self, sid, kind, name):
        now = time.time()
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO resources(slice_id,kind,name,status,created,updated) VALUES(?,?,?,'PENDING',?,?)",
                       (sid, kind, name, now, now))
            return dict(db.execute('SELECT * FROM resources WHERE slice_id=? AND kind=? AND name=?', (sid, kind, name)).fetchone())

    def resource_set(self, sid, kind, name, status, external_id=None):
        with self.tx() as db:
            cursor = db.execute('UPDATE resources SET status=?,external_id=COALESCE(?,external_id),updated=? WHERE slice_id=? AND kind=? AND name=?',
                                (status, external_id, time.time(), sid, kind, name))
            require(cursor.rowcount == 1, 'Recurso no registrado: %s/%s' % (kind, name), 500)

    def resources(self, sid):
        return self.rows('SELECT * FROM resources WHERE slice_id=? ORDER BY created', (sid,))
