"""Driver OpenStack de punta a punta contra un OpenStack falso con estado."""
import copy
import hashlib
import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from g5.api import Application, Server
from g5.backend import MemoryBackend
from g5.drivers.openstack.session import Session, load_env_file
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


class OpenStackFixture(unittest.TestCase):
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


class OpenStackDriverTests(OpenStackFixture):
    def test_size_without_flavor_is_rejected_before_admission(self):
        """Sin create_flavors, un tamaño sin flavor se rechaza en el preflight: nada se crea en OpenStack."""
        self.driver.os_cfg['create_flavors'] = False
        spec = copy.deepcopy(LINEAL)
        spec['vms'][0].update(vcpus=2, memory_mb=2048, disk_gb=4)
        before = self.counts()
        with self.assertRaisesRegex(Fault, '2 vCPU · 2048 MB · 4 GB'):
            self.driver.preflight(spec)
        self.assertEqual(self.counts(), before)
        self.cloud.flavors.append({'id': 'f-x', 'name': 'g5-2c-2048m-4g', 'vcpus': 2, 'ram': 2048, 'disk': 4})
        self.cloud.flavors.append({'id': 'f-s', 'name': 'g5-1c-512m-1g', 'vcpus': 1, 'ram': 512, 'disk': 1})
        self.driver.preflight(spec)  # con los flavors presentes, se admite

    def test_unaddressed_network_creates_no_subnet_and_ports_without_ip(self):
        spec = copy.deepcopy(LINEAL)
        spec['networks'][0] = {'name': spec['networks'][0]['name']}
        for vm in spec['vms']:
            for nic in vm['nics']:
                if nic['network'] == spec['networks'][0]['name']:
                    nic.pop('ip', None)
        job = self.create(spec, key='os-l2-0001'); self.run_job(job)
        self.assertEqual(self.store.get_slice(job['slice_id'])['status'], 'READY')
        l2 = next(n for n in self.cloud.networks.values() if n['name'].endswith('-' + spec['networks'][0]['name']))
        self.assertFalse([sn for sn in self.cloud.subnets.values() if sn['network_id'] == l2['id']], 'sin subred')
        self.assertTrue(all(not p.get('fixed_ips') for p in self.cloud.ports.values() if p['network_id'] == l2['id']))

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


class OpenStackAPITests(OpenStackFixture):
    """Mismo flujo, ahora por la API HTTP real del orquestador (paso 7)."""
    def setUp(self):
        super().setUp()
        self.app.keys = [{'subject': 'profesor', 'role': 'admin', 'sha256': hashlib.sha256(b'admin-token').hexdigest()},
                         {'subject': 'alumno', 'role': 'user', 'sha256': hashlib.sha256(b'user-token').hexdigest()}]
        self.server = Server(('127.0.0.1', 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        super().tearDown()

    def call(self, method, path, body=None, token='admin-token', key='http-key-0001'):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1])
        c.request(method, path, json.dumps(body or {}), {'Authorization': 'Bearer ' + token, 'Idempotency-Key': key,
                                                          'Content-Type': 'application/json'})
        r = c.getresponse(); code, value = r.status, json.loads(r.read()); c.close()
        return code, value

    def test_template_lifecycle_over_http(self):
        spec = json.loads((ROOT / 'templates/os-lineal.json').read_text())
        code, job = self.call('POST', '/v1/slices', spec)
        self.assertEqual(code, 202)
        self.app.engine.process_one()
        sid = job['slice_id']
        listing = self.call('GET', '/v1/slices')[1]
        self.assertEqual([(x['provider'], x['status']) for x in listing], [('openstack', 'READY')])
        self.assertEqual(self.counts(), (2, 2, 2, 4, 3))
        self.assertEqual(len(self.cloud.flavors), 1)  # reutilizó el flavor de LAB5 (1 vCPU, 512 MB, 4 GB)
        diagnostics = self.call('GET', '/v1/slices/%s/diagnostics' % sid)[1]
        self.assertTrue(diagnostics['ok'])
        self.assertEqual(set(diagnostics['servers']), {'vm1', 'vm2', 'vm3'})
        code, console = self.call('POST', '/v1/slices/%s/vms/vm2/console' % sid)
        self.assertEqual(code, 201)
        self.assertTrue(console['url'].startswith('http://127.0.0.1:56080/'))
        self.assertEqual(self.call('GET', '/v1/slices/' + sid, token='user-token')[0], 404)
        self.assertEqual(self.call('POST', '/v1/slices/%s/vms/vm1/probe' % sid, {'kind': 'addresses'})[0], 409)
        self.assertIn('openstack', self.call('GET', '/v1/capabilities')[1]['providers'])
        code, delete = self.call('DELETE', '/v1/slices/' + sid, key='http-delete-1')
        self.assertEqual(code, 202)
        self.app.engine.process_one()
        self.assertEqual(self.call('GET', '/v1/operations/' + delete['id'])[1]['status'], 'SUCCEEDED')
        self.assertEqual(self.counts(), (1, 0, 0, 0, 0))

    def test_unknown_image_is_rejected_before_admission(self):
        spec = copy.deepcopy(LINEAL)
        spec['vms'][0]['image'] = 'ubuntu-que-no-existe'
        code, error = self.call('POST', '/v1/slices', spec)
        self.assertEqual(code, 409)
        self.assertIn('ubuntu-que-no-existe', error['error'])
        self.assertEqual(self.store.rows('SELECT * FROM slices'), [])

    def test_openrc_loader_keeps_only_os_variables(self):
        path = Path(self.temp.name) / 'openstack.env'
        path.write_text('# comentario\nexport OS_USERNAME=cloud_admin\nexport OS_PASSWORD="x y"\nexport PATH=/tmp\n')
        self.assertEqual(load_env_file(path), {'OS_USERNAME': 'cloud_admin', 'OS_PASSWORD': 'x y'})


if __name__ == '__main__':
    unittest.main()
