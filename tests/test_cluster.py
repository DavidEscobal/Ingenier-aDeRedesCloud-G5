"""Pruebas ejecutables sin SSH/KVM; NO sustituyen la aceptación en el laboratorio."""
import concurrent.futures
import copy
import hashlib
import http.client
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
from g5.agent import Agent, AgentError
from g5.api import Application, Server
from g5.backend import MemoryBackend, RemoteError, SSHBackend
from g5.console import ExpiringToken
from g5.model import Fault, validate
from g5.store import Store

ROOT = Path(__file__).resolve().parents[1]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cfg = json.loads((ROOT / 'config/cluster.example.json').read_text())
        self.cfg['retry_delay'] = 0
        self.image = hashlib.sha256(b'fake-test-image').hexdigest()
        self.spec = json.loads((ROOT / 'tests/fixtures/two-vms.json').read_text())
        for vm in self.spec['vms']:
            vm['image'] = self.image
        self.backend = MemoryBackend(self.cfg)
        self.keys = [{'subject': 'profesor', 'role': 'admin', 'sha256': hashlib.sha256(b'admin-token').hexdigest()},
                     {'subject': 'alumno', 'role': 'user', 'sha256': hashlib.sha256(b'user-token').hexdigest()}]
        self.app = Application(self.cfg, self.temp.name, self.keys, backend=self.backend)
        self.store = self.app.store
        with self.store.tx() as db:
            db.execute('INSERT INTO images VALUES(?,?,?,?,?)', (self.image, 'test', 100, 1024**3, time.time()))
        (self.store.directory / 'images' / (self.image + '.qcow2')).write_bytes(b'fake-test-image')

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def create(self, spec=None, owner='profesor', key='create-key-0001'):
        return self.store.create(owner, key, validate(spec or self.spec, self.cfg))

    def ready(self):
        job = self.create()
        self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(job['slice_id'])['status'], 'READY')
        return job


class AdmissionTests(Fixture):
    def test_duplicate_request_returns_same_operation(self):
        first = self.create()
        self.assertEqual(first['id'], self.create()['id'])
        self.assertEqual(len(self.store.rows('SELECT * FROM allocations')), 2)

    def test_conflicting_idempotency_payload_is_rejected(self):
        self.create()
        spec = copy.deepcopy(self.spec); spec['name'] = 'other'
        with self.assertRaises(Fault):
            self.create(spec)

    def test_invalid_node(self):
        self.spec['vms'][0]['worker'] = 'server9'
        with self.assertRaises(Fault):
            self.create()

    def test_injection_names(self):
        self.spec['vms'][0]['name'] = 'vm;touch /tmp/pwned'
        with self.assertRaises(Fault):
            self.create()

    def test_unknown_fields(self):
        self.spec['command'] = 'id'
        with self.assertRaises(Fault):
            self.create()

    def test_duplicate_ip_rejected(self):
        self.spec['vms'][1]['nics'][0]['ip'] = self.spec['vms'][0]['nics'][0]['ip']
        with self.assertRaises(Fault):
            self.create()

    def test_management_and_transit_overlap_rejected(self):
        for cidr in ('10.0.10.0/24', '172.30.0.0/24'):
            spec = copy.deepcopy(self.spec); spec['networks'][0]['cidr'] = cidr
            with self.assertRaises(Fault):
                validate(spec, self.cfg)

    def test_bad_publication_rejected(self):
        self.spec['publications'][0]['external_port'] = 22
        with self.assertRaises(Fault):
            self.create()

    def test_no_bool_resource(self):
        self.spec['vms'][0]['vcpus'] = True
        with self.assertRaises(Fault):
            self.create()

    def test_missing_image_and_no_partial_reservations(self):
        self.spec['vms'][1]['image'] = 'a' * 64
        with self.assertRaises(Fault):
            self.create()
        self.assertEqual(self.store.rows('SELECT * FROM allocations'), [])
        self.assertEqual(self.store.rows('SELECT * FROM leases'), [])

    def test_capacity_failure_rolls_back_entire_request(self):
        self.spec['vms'][1]['memory_mb'] = 4096
        with self.assertRaises(Fault):
            self.create()
        self.assertEqual(self.store.rows('SELECT * FROM allocations'), [])

    def test_concurrent_admission_cannot_overcommit(self):
        spec = copy.deepcopy(self.spec); spec['publications'] = []
        def submit(i):
            try:
                return self.create(spec, key='parallel-%04d' % i)
            except Fault:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            jobs = list(pool.map(submit, range(12)))
        self.assertEqual(sum(x is not None for x in jobs), 2)
        usage = self.store.rows('SELECT worker,SUM(cpu) AS cpu FROM allocations GROUP BY worker')
        self.assertTrue(all(r['cpu'] == 2 for r in usage))

    def test_concurrent_same_idempotency_key(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            jobs = list(pool.map(lambda _: self.create(), range(12)))
        self.assertEqual(len({x['id'] for x in jobs}), 1)

    def test_reuse_inner_vlan_and_cidr_isolated_by_outer_vlan(self):
        self.spec['publications'] = []
        a = self.create(key='slice-key-1'); b = self.create(key='slice-key-2')
        pa = self.store.get_slice(a['slice_id'])['plan']; pb = self.store.get_slice(b['slice_id'])['plan']
        self.assertNotEqual(pa['svid'], pb['svid'])
        self.assertNotEqual(pa['transit'], pb['transit'])
        self.assertEqual(pa['networks'], pb['networks'])

    def test_duplicate_public_port_rejected_atomically(self):
        self.create()
        with self.assertRaises(Fault):
            self.create(key='slice-key-2')
        self.assertEqual(len(self.store.rows('SELECT * FROM allocations')), 2)

    def test_drain_worker_blocks_new_requests(self):
        self.app.route('PATCH', '/v1/nodes/server1', {'enabled': False}, 'profesor', True, '')
        with self.assertRaises(Fault):
            self.create()


class WorkflowTests(Fixture):
    def test_full_lifecycle_removes_unused_bases_and_own_resources(self):
        job = self.ready(); sid = job['slice_id']
        delete = self.store.mutate(sid, 'profesor', True, 'delete-key-1', 'delete')
        self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(sid)['status'], 'DELETED')
        self.assertEqual(self.store.rows('SELECT * FROM allocations'), [])
        self.assertFalse(self.backend.resources)
        self.assertFalse(self.backend.images)
        self.assertEqual(self.store.rows('SELECT status FROM jobs WHERE id=?', (delete['id'],))[0]['status'], 'SUCCEEDED')

    def test_temporary_failure_retries_successfully(self):
        self.backend.failures[('server1', 'network')] = 1
        self.ready()
        self.assertTrue(self.store.rows("SELECT * FROM events WHERE event='RETRY'"))

    def test_permanent_create_failure_compensates(self):
        self.backend.failures[('server2', 'vm_ensure')] = 10
        job = self.create(); self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(job['slice_id'])['status'], 'FAILED_CLEANED')
        self.assertFalse(self.backend.resources)
        self.assertEqual(self.store.rows('SELECT * FROM allocations'), [])

    def test_unknown_cleanup_holds_reservations_until_retry(self):
        self.backend.failures[('server2', 'vm_ensure')] = 10
        self.backend.failures[('server2', 'delete')] = 10
        job = self.create(); self.app.engine.process_one(); sid = job['slice_id']
        self.assertEqual(self.store.get_slice(sid)['status'], 'ERROR_CLEANUP')
        self.assertEqual(len(self.store.rows('SELECT * FROM allocations')), 2)
        self.backend.failures.clear()
        self.store.mutate(sid, 'profesor', True, 'retry-delete-key', 'delete')
        self.app.engine.process_one()
        self.assertEqual(self.store.rows('SELECT * FROM allocations'), [])

    def test_restart_replays_running_job_without_duplicate_vms(self):
        job = self.create(); claimed = self.store.claim()
        self.app.engine.deploy(self.store.get_slice(job['slice_id'])['plan'], claimed['id'])
        self.store.recover(); self.app.engine.process_one()
        vms = sum(len(x['vms']) for x in self.backend.resources.values())
        self.assertEqual(vms, 2)
        self.assertEqual(self.store.rows('SELECT status FROM jobs')[0]['status'], 'SUCCEEDED')

    def test_lost_response_after_vm_creation_is_idempotent(self):
        original = self.backend.call
        raised = [False]
        def lost(node, action, **params):
            result = original(node, action, **params)
            if action == 'vm_ensure' and not raised[0]:
                raised[0] = True; raise RemoteError('Respuesta perdida DESPUÉS del efecto')
            return result
        self.backend.call = lost
        self.ready()
        self.assertEqual(sum(len(x['vms']) for x in self.backend.resources.values()), 2)

    def test_delete_one_slice_preserves_other(self):
        self.spec['publications'] = []
        a = self.create(key='create-slice-a'); b = self.create(key='create-slice-b')
        self.app.engine.process_one(); self.app.engine.process_one()
        self.store.mutate(a['slice_id'], 'profesor', True, 'delete-slice-a', 'delete')
        self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(b['slice_id'])['status'], 'READY')
        self.assertEqual(len(self.store.rows('SELECT * FROM allocations')), 2)

    def test_simultaneous_delete_and_reconcile_are_exclusive(self):
        job = self.ready(); sid = job['slice_id']
        self.store.mutate(sid, 'profesor', True, 'delete-key-1', 'delete')
        with self.assertRaises(Fault):
            self.store.mutate(sid, 'profesor', True, 'reconcile-key', 'reconcile')

    def test_reconcile_failure_does_not_destroy_existing_disks(self):
        job = self.ready(); sid = job['slice_id']
        self.backend.failures[('server2', 'network')] = 10
        self.store.mutate(sid, 'profesor', True, 'reconcile-key', 'reconcile')
        self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(sid)['status'], 'ERROR')
        self.assertEqual(len(self.store.rows('SELECT * FROM allocations')), 2)
        self.assertTrue(self.backend.resources)

    def test_stop_start_keeps_disks_networks_and_reservations(self):
        job = self.ready(); sid = job['slice_id']
        self.store.mutate(sid, 'profesor', True, 'stop-key-0001', 'stop')
        self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(sid)['status'], 'STOPPED')
        self.assertEqual(len(self.store.rows('SELECT * FROM allocations')), 2)
        self.store.mutate(sid, 'profesor', True, 'start-key-001', 'start')
        self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(sid)['status'], 'READY')

    def test_smart_image_deletion_rejects_referenced_base(self):
        self.ready()
        with self.assertRaises(Fault):
            self.app.route('DELETE', '/v1/images/' + self.image, {}, 'profesor', True, '')

    def test_gc_preserves_pinned_image_then_removes_unused(self):
        job = self.ready()
        gc = self.backend.call('server1', 'cache_gc', all_unused=True)
        self.assertEqual(gc['removed'], [])
        self.store.mutate(job['slice_id'], 'profesor', True, 'delete-key-1', 'delete')
        self.app.engine.process_one()
        gc = self.backend.call('server1', 'cache_gc', all_unused=True)
        self.assertEqual(gc['removed'], [])
        self.assertNotIn(('server1', self.image), self.backend.images)

    def test_bad_image_hash_never_enters_catalog(self):
        with self.assertRaises(Fault):
            self.app.upload('b' * 64, 'mal', 3, io.BytesIO(b'bad'))
        self.assertFalse((self.store.directory / 'images' / ('b' * 64 + '.qcow2')).exists())

    def test_readding_store_cannot_remove_reserved_worker(self):
        self.create()
        cfg = copy.deepcopy(self.cfg); del cfg['workers']['server1']
        with self.assertRaises(Fault):
            Store(self.temp.name, cfg)


class SecurityAndHTTPTests(Fixture):
    def test_user_cannot_read_another_slice(self):
        job = self.ready()
        with self.assertRaises(Fault) as error:
            self.app.route('GET', '/v1/slices/' + job['slice_id'], {}, 'alumno', False, '')
        self.assertEqual(error.exception.status, 404)

    def test_user_cannot_administer_nodes(self):
        with self.assertRaises(Fault) as error:
            self.app.route('PATCH', '/v1/nodes/server1', {'enabled': False}, 'alumno', False, '')
        self.assertEqual(error.exception.status, 403)

    def test_console_token_expiration_revocation_and_slice_state(self):
        job = self.ready(); sid = job['slice_id']; token = 'secret-console-test'
        h = hashlib.sha256(token.encode()).hexdigest()
        with self.store.tx() as db:
            db.execute('INSERT INTO tokens(hash,slice_id,vm,port,expires) VALUES(?,?,?,?,?)', (h, sid, 'vm1', 61234, time.time() + 60))
        resolver = ExpiringToken(self.store.path)
        self.assertEqual(resolver.lookup(token), ['127.0.0.1', '61234'])
        self.assertIsNone(resolver.lookup('not-the-token'))
        with self.store.tx() as db:
            db.execute('UPDATE tokens SET expires=?', (time.time()-1,))
        self.assertIsNone(resolver.lookup(token))
        with self.store.tx() as db:
            db.execute('UPDATE tokens SET expires=?,revoked=1', (time.time()+60,))
        self.assertIsNone(resolver.lookup(token))

    def test_token_never_stored_in_plaintext(self):
        self.assertNotIn('admin-token', json.dumps(self.keys))
        with self.assertRaises(Fault):
            self.app.identity('Bearer invalid')

    def test_real_http_auth_create_poll_and_diagnostics(self):
        server = Server(('127.0.0.1', 0), self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        port = server.server_address[1]
        def call(method, path, body=None, token='admin-token'):
            c = http.client.HTTPConnection('127.0.0.1', port)
            c.request(method, path, json.dumps(body or {}), {'Authorization': 'Bearer ' + token, 'Idempotency-Key': 'http-create-key', 'Content-Type': 'application/json'})
            r = c.getresponse(); code, value = r.status, json.loads(r.read()); c.close()
            return code, value
        try:
            self.assertEqual(call('GET', '/v1/slices', token='bad')[0], 401)
            code, job = call('POST', '/v1/slices', self.spec)
            self.assertEqual(code, 202)
            self.app.engine.process_one()
            self.assertEqual(call('GET', '/v1/operations/' + job['id'])[1]['status'], 'SUCCEEDED')
            self.assertEqual(call('GET', '/v1/slices/' + job['slice_id'] + '/diagnostics')[0], 200)
            self.assertEqual(call('GET', '/v1/capabilities')[1]['simulated'], True)
        finally:
            server.shutdown(); server.server_close(); thread.join()


class AgentTests(Fixture):
    def agent(self, role='gateway'):
        cfg = dict(self.cfg['common'], **(self.cfg['gateway'] if role == 'gateway' else self.cfg['workers']['server1']))
        cfg['state_dir'] = self.temp.name + '/node'
        return Agent(cfg)

    def test_real_qinq_command_builder(self):
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        agent = self.agent('worker'); agent.manifest_path(plan['id']).write_text(json.dumps(plan))
        commands = []
        def fake(*args, **kw):
            commands.append(args); return ''
        with mock.patch.object(agent, 'fabric_add'), mock.patch.object(agent, 'owned_ovs'), mock.patch('g5.agent.output', side_effect=fake):
            agent.network(plan['id'])
        flattened = [' '.join(map(str, c)) for c in commands]
        self.assertTrue(any('vlan_mode=dot1q-tunnel' in c and 'tag=1000' in c and 'cvlans=100' in c and 'qinq-ethtype=802.1ad' in c for c in flattened))
        self.assertTrue(any('vlan_mode=trunk trunks=100' in c for c in flattened))
        self.assertFalse(any('del-br br-int' in c for c in flattened))

    def test_firewall_targets_exact_public_port_and_source(self):
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        agent = self.agent()
        _, wan, _, hooks, rules = agent.firewall_plan(plan)
        dnat = rules['nat'][0]
        self.assertIn('10.0.10.4/32', dnat)
        self.assertIn('22022', dnat)
        self.assertIn(wan + ':22022', dnat)
        self.assertEqual(rules['filter'][-1], ['-j', 'DROP'])
        self.assertTrue(any('-i' in rule and 'DROP' in rule for table, chain, rule in hooks if chain == 'INPUT'))

    def test_cache_real_files_only_unused_removed(self):
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        agent = self.agent('worker')
        agent.manifest_path(plan['id']).write_text(json.dumps(plan))
        pinned = agent.root / 'images' / (self.image + '.qcow2'); pinned.write_bytes(b'base')
        unused = agent.root / 'images' / ('a' * 64 + '.qcow2'); unused.write_bytes(b'unused')
        result = agent.cache_gc(all_unused=True)
        self.assertTrue(pinned.exists()); self.assertFalse(unused.exists())
        self.assertEqual(result['removed'], ['a' * 64])

    def test_cache_protects_orphan_overlay_backing_file(self):
        agent = self.agent('worker')
        base = agent.root / 'images' / ('a' * 64 + '.qcow2'); base.write_bytes(b'base')
        vm = agent.root / 'vms' / 'orphan'; vm.mkdir(); (vm / 'disk.qcow2').write_bytes(b'overlay')
        with mock.patch('g5.agent.output', return_value=json.dumps({'full-backing-filename': str(base)})):
            agent.cache_gc(all_unused=True)
        self.assertTrue(base.exists())

    def test_ssh_checks_host_key_and_never_uses_shell_flag(self):
        argv = SSHBackend(self.cfg).ssh('server1')
        self.assertIn('StrictHostKeyChecking=yes', argv)
        self.assertIn('BatchMode=yes', argv)
        self.assertEqual(argv[-1], 'ubuntu@10.0.10.1')

    def test_path_traversal_rejected_by_privileged_agent(self):
        agent = self.agent()
        with self.assertRaises(AgentError):
            agent.manifest_path('../../etc/shadow')

    def test_existing_unmarked_ovs_resource_is_not_adopted(self):
        agent = self.agent()
        with mock.patch('g5.agent.run', side_effect=[(0, 'existing-row'), (1, '')]):
            with self.assertRaises(AgentError):
                agent.owned_ovs('Bridge', 'g5bexample', 'a' * 32)

    def test_tombstone_blocks_late_work_after_delete(self):
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        agent = self.agent('worker')
        agent.manifest_path(plan['id']).write_text(json.dumps(plan))
        (agent.root / 'tombstones' / (plan['id'] + '.json')).write_text('{}')
        with self.assertRaises(AgentError):
            agent.prepare(plan)
        with self.assertRaises(AgentError):
            agent.network(plan['id'])
        self.assertEqual(agent.load(plan['id'], allow_deleted=True)['id'], plan['id'])

    def test_remote_corrupt_image_not_published(self):
        agent = self.agent('worker')
        with self.assertRaises(AgentError):
            agent.image_receive(self.image, 3, stream=io.BytesIO(b'bad'))
        self.assertEqual(list((agent.root / 'images').iterdir()), [])

    def test_openapi_routes_available_over_authenticated_api(self):
        schema = json.loads((ROOT / 'api/openapi.json').read_text())
        self.assertEqual(schema['openapi'], '3.0.3')
        for action in ('start', 'stop', 'reconcile'):
            self.assertIn('/v1/slices/{slice_id}/' + action, schema['paths'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
