"""Driver OpenStack de punta a punta contra un OpenStack falso con estado."""
import copy
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from g5.api import Application
from g5.backend import MemoryBackend
from g5.drivers.openstack.session import Session
from g5.model import Fault, validate
from openstack_fake import FakeCloud, FakeOpenStack, USER

ROOT = Path(__file__).resolve().parents[1]
LINEAL = {'name': 'lineal-os', 'provider': 'openstack',
          'networks': [{'name': 'link1', 'cidr': '192.168.11.0/28'}, {'name': 'link2', 'cidr': '192.168.12.0/28'}],
          'vms': [{'name': 'vm1', 'image': 'cirros', 'vcpus': 1, 'memory_mb': 512, 'disk_gb': 1, 'nics': [{'network': 'link1'}]},
                  {'name': 'vm2', 'image': 'cirros', 'vcpus': 1, 'memory_mb': 512, 'disk_gb': 1,
                   'nics': [{'network': 'link1'}, {'network': 'link2'}]},
                  {'name': 'vm3', 'image': 'cirros', 'vcpus': 1, 'memory_mb': 512, 'disk_gb': 1,
                   'nics': [{'network': 'link2', 'ip': '192.168.12.5'}]}]}


class OpenStackDriverTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOpenStack()
        self.cloud = FakeCloud(self.fake)
        self.temp = tempfile.TemporaryDirectory()
        self.cfg = json.loads((ROOT / 'config/cluster.example.json').read_text())
        self.cfg['retry_delay'] = 0
        self.cfg['openstack'] = self.fake.config(poll_interval=0, server_timeout=5, create_flavors=True,
                                                 console_map={'http://controller:6080': 'http://127.0.0.1:56080'})
        self.app = Application(self.cfg, self.temp.name, [], backend=MemoryBackend(self.cfg))
        self.store = self.app.store
        self.driver = self.store.drivers['openstack']
        self.driver._session = Session(self.cfg['openstack'], environ=USER)

    def tearDown(self):
        self.app.close(); self.temp.cleanup(); self.fake.close()

    def create(self, spec=None, key='os-create-0001'):
        return self.store.create('profesor', key, validate(spec or LINEAL, self.cfg))

    def run_job(self, job):
        self.app.engine.process_one()
        return self.store.get_slice(job['slice_id'])

    def counts(self):
        c = self.cloud
        return (len(c.projects), len(c.networks), len(c.subnets), len(c.ports), len(c.servers))

    def test_validation_is_provider_specific(self):
        spec = validate(LINEAL, self.cfg)
        self.assertEqual(spec['networks'][0]['dhcp'], False)
        for mutate in (lambda s: s['vms'][0].update(worker='server1'), lambda s: s.update(publications=[]),
                       lambda s: s['vms'][2]['nics'][0].update(ip='192.168.12.15'), lambda s: s['networks'][1].update(cidr='192.168.11.8/29')):
            bad = copy.deepcopy(LINEAL); mutate(bad)
            with self.assertRaises(Fault):
                validate(bad, self.cfg)
        cfg = dict(self.cfg); del cfg['openstack']
        with self.assertRaises(Fault):
            validate(LINEAL, cfg)

    def test_create_and_delete_without_leftovers(self):
        job = self.create()
        row = self.run_job(job)
        self.assertEqual((row['status'], row['provider']), ('READY', 'openstack'))
        self.assertEqual(self.counts(), (2, 2, 2, 4, 3))
        project = next(p for p in self.cloud.projects.values() if p['name'] == 'g5-' + job['slice_id'])
        self.assertTrue(all(s['project_id'] == project['id'] and s['status'] == 'ACTIVE' for s in self.cloud.servers.values()))
        self.assertIn((project['id'], 'u-cloud-admin', 'r-admin'), self.cloud.assignments)
        self.assertTrue(all(n['port_security_enabled'] is False for n in self.cloud.networks.values()))
        fixed = [p for p in self.cloud.ports.values() if p['fixed_ips'][0]['ip_address'] == '192.168.12.5']
        self.assertEqual(len(fixed), 1)
        journal = self.store.resources(job['slice_id'])
        self.assertEqual(len(journal), 1 + 2 + 2 + 4 + 3)
        self.assertTrue(all(r['external_id'] and r['status'] in ('CREATED', 'ACTIVE') for r in journal))
        placed = self.store.rows("SELECT detail FROM events WHERE event='OS_PLACED'")[0]['detail']
        self.assertIn('vm1@worker', placed)
        self.store.mutate(job['slice_id'], 'profesor', True, 'os-delete-0001', 'delete')
        self.assertEqual(self.run_job(job)['status'], 'DELETED')
        self.assertEqual(self.counts(), (1, 0, 0, 0, 0))
        self.assertIn('p-cloud-admin', self.cloud.projects)
        self.assertTrue(all(r['status'] == 'DELETED' for r in self.store.resources(job['slice_id'])))

    def test_replayed_deploy_does_not_duplicate_resources(self):
        job = self.create()
        self.run_job(job)
        before = self.counts()
        plan = self.store.get_slice(job['slice_id'])['plan']
        self.app.engine.deploy(plan, job['id'])
        self.assertEqual(self.counts(), before)

    def test_nova_error_is_compensated(self):
        self.cloud.error_names.add('-vm2')
        job = self.create()
        self.assertEqual(self.run_job(job)['status'], 'FAILED_CLEANED')
        self.assertEqual(self.counts(), (1, 0, 0, 0, 0))
        failed = self.store.rows("SELECT detail FROM events WHERE event='FAILED'")[0]['detail']
        self.assertIn('No valid host', failed)

    def test_missing_flavor_without_permission_fails_cleanly(self):
        self.driver.os_cfg['create_flavors'] = False
        job = self.create()
        self.assertEqual(self.run_job(job)['status'], 'FAILED_CLEANED')
        self.assertIn('create_flavors', self.store.rows("SELECT error FROM jobs")[0]['error'])
        self.assertEqual(self.counts(), (1, 0, 0, 0, 0))

    def test_stop_and_start_keep_resources(self):
        job = self.create(); self.run_job(job); before = self.counts()
        self.store.mutate(job['slice_id'], 'profesor', True, 'os-stop-00001', 'stop')
        self.assertEqual(self.run_job(job)['status'], 'STOPPED')
        self.assertTrue(all(s['status'] == 'SHUTOFF' for s in self.cloud.servers.values()))
        self.store.mutate(job['slice_id'], 'profesor', True, 'os-start-0001', 'start')
        self.assertEqual(self.run_job(job)['status'], 'READY')
        self.assertTrue(all(s['status'] == 'ACTIVE' for s in self.cloud.servers.values()))
        self.assertEqual(self.counts(), before)

    def test_cleanup_finds_resources_missing_from_journal(self):
        job = self.create(); self.run_job(job)
        with self.store.tx() as db:
            db.execute("UPDATE resources SET external_id=NULL, status='PENDING' WHERE kind IN ('network','port')")
        self.store.mutate(job['slice_id'], 'profesor', True, 'os-delete-0002', 'delete')
        self.assertEqual(self.run_job(job)['status'], 'DELETED')
        self.assertEqual(self.counts(), (1, 0, 0, 0, 0))

    def test_console_url_goes_through_tunnel(self):
        job = self.create(); self.run_job(job)
        console = self.driver.console(self.store, job['slice_id'], 'vm1')
        self.assertTrue(console['url'].startswith('http://127.0.0.1:56080/vnc_auto.html'))

    def test_linux_and_openstack_slices_share_the_same_core(self):
        image = hashlib.sha256(b'img').hexdigest()
        with self.store.tx() as db:
            db.execute('INSERT INTO images VALUES(?,?,?,?,?)', (image, 'test', 100, 1024**3, time.time()))
        (self.store.directory / 'images' / (image + '.qcow2')).write_bytes(b'img')
        linux = json.loads((ROOT / 'tests/fixtures/two-vms.json').read_text())
        for vm in linux['vms']:
            vm['image'] = image
        jobs = [self.create(linux, 'linux-create-1'), self.create(key='os-create-0002')]
        self.app.engine.process_one(); self.app.engine.process_one()
        rows = [self.store.get_slice(j['slice_id']) for j in jobs]
        self.assertEqual([(r['provider'], r['status']) for r in rows], [('linux', 'READY'), ('openstack', 'READY')])


if __name__ == '__main__':
    unittest.main()
