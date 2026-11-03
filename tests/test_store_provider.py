"""Store multiproveedor: migración de bases EX1 y diario de recursos del proveedor."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from g5.model import Fault
from g5.store import Store

ROOT = Path(__file__).resolve().parents[1]


class StoreProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cfg = json.loads((ROOT / 'config/cluster.example.json').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def test_ex1_database_is_migrated_and_old_slices_are_linux(self):
        db = sqlite3.connect(str(Path(self.temp.name) / 'cluster.db'))
        db.execute('CREATE TABLE slices(id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT, spec TEXT NOT NULL, '
                   'plan TEXT NOT NULL, status TEXT NOT NULL, reserved INTEGER NOT NULL)')
        db.execute("INSERT INTO slices VALUES('a'||hex(randomblob(15)),'profesor','viejo','{}','{}','READY',1)")
        db.commit(); db.close()
        store = Store(self.temp.name, self.cfg)
        self.assertEqual([r['provider'] for r in store.rows('SELECT provider FROM slices')], ['linux'])
        Store(self.temp.name, self.cfg)  # reabrir no vuelve a migrar

    def test_resource_journal_lifecycle(self):
        store = Store(self.temp.name, self.cfg)
        sid = 'a' * 32
        first = store.resource_pending(sid, 'network', 'link1')
        again = store.resource_pending(sid, 'network', 'link1')
        self.assertEqual((first['status'], again['status']), ('PENDING', 'PENDING'))
        store.resource_set(sid, 'network', 'link1', 'CREATED', 'uuid-1')
        store.resource_set(sid, 'network', 'link1', 'DELETED')
        row = store.resources(sid)[0]
        self.assertEqual((row['status'], row['external_id']), ('DELETED', 'uuid-1'))

    def test_unknown_resource_cannot_be_updated(self):
        store = Store(self.temp.name, self.cfg)
        with self.assertRaises(Fault):
            store.resource_set('b' * 32, 'server', 'vm1', 'CREATED', 'x')


if __name__ == '__main__':
    unittest.main()
