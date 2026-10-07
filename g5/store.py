"""Reservas, estado y cola durables en transacciones SQLite cortas."""
import contextlib
import ipaddress
import json
import sqlite3
import time
import uuid
from pathlib import Path
from .model import Fault, require, canonical, fingerprint, disk_bytes


class Store:
    def __init__(self, directory, config):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = str(self.directory / 'cluster.db')
        self.config = config
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
            ''')
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
            used = {r[0] for r in db.execute('SELECT svid FROM leases')}
            svid = next((v for v in range(self.config['svid_range'][0], self.config['svid_range'][1] + 1) if v not in used), None)
            require(svid is not None, 'Pool de S-VLAN agotado', 409)
            used_slots = {r[0] for r in db.execute('SELECT slot FROM leases')}
            pool = ipaddress.ip_network(self.config['transit_pool'])
            slot = next((x for x in range(pool.num_addresses // 4) if x not in used_slots), None)
            require(slot is not None, 'Pool de tránsito agotado', 409)
            plan = json.loads(canonical(spec))
            plan.update(id=sid, svid=svid, transit=str(ipaddress.ip_network((int(pool.network_address) + slot * 4, 30))))
            for network in plan['networks']:
                network['gateway'] = str(ipaddress.ip_network(network['cidr']).network_address + 1)
            for vm in plan['vms']:
                worker = vm['worker']
                require(db.execute('SELECT enabled FROM nodes WHERE id=?', (worker,)).fetchone()[0], 'Worker en mantenimiento', 409)
                image = db.execute('SELECT * FROM images WHERE id=?', (vm['image'],)).fetchone()
                require(image is not None, 'Imagen no registrada: ' + vm['image'], 404)
                vm['disk_bytes'] = disk_bytes(vm['disk_gb'], self.config.get('disk_unit', 'GiB'))
                require(image['virtual_size'] <= vm['disk_bytes'], 'Disco menor que la imagen base', 409)
                vm['image_bytes'] = image['size']
                used_r = db.execute('SELECT COALESCE(SUM(cpu),0),COALESCE(SUM(mem),0),COALESCE(SUM(disk),0) FROM allocations WHERE worker=?', (worker,)).fetchone()
                capacity = self.config['workers'][worker]['capacity']
                require(all(used_r[i] + vm[k] <= capacity[k] for i, k in enumerate(('vcpus', 'memory_mb', 'disk_gb'))),
                        'Capacidad reservable insuficiente en ' + worker, 409)
                used_vnc = {r[0] for r in db.execute('SELECT vnc FROM allocations WHERE worker=?', (worker,))}
                vnc = next((p for p in range(5900, 6900) if p not in used_vnc), None)
                require(vnc is not None, 'Puertos VNC agotados', 409)
                vm['vnc'] = vnc
                for idx, nic in enumerate(vm['nics']):
                    h = fingerprint([sid, vm['name'], idx])
                    nic['mac'] = '02:' + ':'.join(h[i:i+2] for i in range(0, 10, 2))
                db.execute('INSERT INTO allocations VALUES(?,?,?,?,?,?,?,?)',
                           (sid, vm['name'], worker, vm['vcpus'], vm['memory_mb'], vm['disk_gb'], vm['image'], vnc))
            for pub in plan['publications']:
                require(not db.execute('SELECT 1 FROM ports WHERE protocol=? AND port=?', (pub['protocol'], pub['external_port'])).fetchone(),
                        'Puerto externo reservado', 409)
                db.execute('INSERT INTO ports VALUES(?,?,?)', (pub['protocol'], pub['external_port'], sid))
            db.execute('INSERT INTO leases VALUES(?,?,?)', (svid, sid, slot))
            db.execute('INSERT INTO slices VALUES(?,?,?,?,?,?,1)', (sid, owner, spec['name'], canonical(spec), canonical(plan), 'QUEUED'))
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
