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

    def test_phase2_without_managed_switch_skips_fabric(self):
        """Fase 2: el switch del laboratorio ya transporta VLAN; sin 'switch' no hay fabric_add/fabric_delete."""
        self.app.close()
        self.cfg.pop('switch')
        self.backend = MemoryBackend(self.cfg)
        self.assertNotIn('ofs', self.backend.nodes)
        self.app = Application(self.cfg, self.temp.name, self.keys, backend=self.backend)
        self.store = self.app.store
        job = self.ready(); sid = job['slice_id']
        self.store.mutate(sid, 'profesor', True, 'delete-key-sw', 'delete')
        self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(sid)['status'], 'DELETED')
        actions = {a for _, a, _ in self.backend.calls}
        self.assertTrue({'prepare', 'gateway', 'delete'} <= actions)
        self.assertFalse(actions & {'fabric_add', 'fabric_delete'})
        self.assertFalse(self.backend.resources)

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

    def test_diag_datapath_builds_slice_encapsulation_and_always_cleans_up(self):
        agent = self.agent('worker'); commands = []
        def fake_run(*args, **kw):
            commands.append(' '.join(map(str, args)))
            if args[0] == 'ping':
                raise AgentError('fallo inyectado')
            return 0, ''
        with mock.patch('g5.agent.run', side_effect=fake_run), mock.patch('g5.agent.output', side_effect=lambda *a, **k: fake_run(*a, **k)[1]):
            with self.assertRaises(AgentError):
                agent.diag_datapath(mode='ping', svid=4001, cvid=112, index=2, peer='172.31.96.1')
        self.assertTrue(any('add-port br-int g5diag' in c and 'type=internal' in c and 'vlan_mode=dot1q-tunnel' in c
                            and 'tag=4001' in c and 'cvlans=112' in c and 'qinq-ethtype=802.1ad' in c for c in commands))
        self.assertTrue(any(c.endswith('type vlan id 112') for c in commands))
        self.assertIn('ip addr add 172.31.96.2/24 dev g5diag.112', commands)
        self.assertEqual(commands[-2:], ['ip link del g5diag.112', 'ovs-vsctl --if-exists del-port br-int g5diag'])

    def test_diag_datapath_rejects_slice_range_and_foreign_peer(self):
        agent = self.agent('worker')
        with mock.patch('g5.agent.run') as run_mock, mock.patch('g5.agent.output') as out_mock:
            for kwargs in ({'svid': 1500}, {'svid': 4000, 'mode': 'ping', 'peer': '10.0.10.1'},
                           {'svid': 4000, 'hold': 600}, {'svid': 4000, 'mode': 'rm -rf'}):
                with self.assertRaises(AgentError):
                    agent.diag_datapath(**kwargs)
            run_mock.assert_not_called(); out_mock.assert_not_called()

    def test_cirros_setup_stops_dhcpcd_and_udhcpc(self):
        """CirrOS 0.6.x usa dhcpcd: si queda vivo pelea con la IP fija (bucle de MLD y ARP sin respuesta en fase 2)."""
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        vm = next(v for v in plan['vms'] if v['worker'] == 'server1')
        vm['guest'] = {'os': 'cirros'}
        agent = self.agent('worker'); sent = []
        stat = ' '.join(['0'] * 30)
        with mock.patch.object(agent, 'load', return_value=plan), mock.patch.object(agent, 'process', return_value=4242),                 mock.patch('g5.agent.Path.read_text', return_value=stat), mock.patch('g5.agent.atomic'),                 mock.patch('g5.agent.serial_execute', side_effect=lambda path, cmd, *a, **k: sent.append(cmd) or (0, '')):
            agent.guest_setup(plan['id'], vm['name'])
        self.assertIn('killall udhcpc', sent[0])
        self.assertIn('killall dhcpcd', sent[0])
        self.assertLess(sent[0].index('dhcpcd'), sent[0].index('ip addr flush'))
        self.assertIn('disable_ipv6', sent[0])
        self.assertLess(sent[0].index('disable_ipv6'), sent[0].index('ip addr flush'))

    def test_vm_tap_is_rate_limited(self):
        agent = self.agent('worker')
        self.assertEqual(agent.police('g5tabc'), ('ovs-vsctl', 'set', 'Interface', 'g5tabc',
                                                   'ingress_policing_rate=10000', 'ingress_policing_burst=1000'))
        agent.cfg['vm_rate_kbps'] = 10 ** 9
        with self.assertRaises(AgentError):
            agent.police('g5tabc')
        source = (ROOT / 'g5/agent.py').read_text(encoding='utf-8')
        self.assertIn('output(*self.police(tap))', source[source.index('def vm_ensure'):source.index('def cloud_seed')])

    def test_cirros_gets_minimal_nocloud_seed(self):
        """Sin metadatos, CirrOS 0.6 reintenta EC2 por minutos y guest_setup agota su plazo (MS-14: 391 s)."""
        from g5.agent import cirros_documents
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        vm = dict(plan['vms'][0], guest={'os': 'cirros'})
        docs = cirros_documents(plan, vm)
        self.assertEqual(sorted(docs), ['meta-data', 'user-data'])
        meta = json.loads(docs['meta-data'])  # CirrOS 0.6 exige JSON (json2fstree)
        self.assertEqual(meta, {'instance-id': plan['id'] + '-' + vm['name'], 'local-hostname': vm['name']})
        source = (ROOT / 'g5/agent.py').read_text(encoding='utf-8')
        self.assertIn("in ('ubuntu', 'cirros') else None", source)
        self.assertIn('virtio-rng-pci', source, 'entropía para no esperar ~60 s en el arranque')
        self.assertIn("guest_boot_timeout', 420", source, 'un solo intento cubre el arranque completo')

    def test_guest_setup_call_outlasts_agent_boot_wait(self):
        backend = SSHBackend(self.cfg)
        self.assertGreater(backend.call_timeout('guest_setup'), 420)
        self.assertEqual(backend.call_timeout('doctor'), 300)

    def test_diag_console_returns_tail_of_vm_serial_log(self):
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        agent = self.agent('worker')
        vm = next(v for v in plan['vms'] if v['worker'] == 'server1')
        with mock.patch.object(agent, 'load', return_value=plan):
            with self.assertRaisesRegex(AgentError, 'Sin registro'):
                agent.diag_console(plan['id'], vm['name'])
            directory = agent.vm_dir(plan['id'], vm['name']); directory.mkdir(parents=True)
            (directory / 'console.log').write_bytes(b'\x1b[0mboot\r\n' + b'linea\n' * 50 + b'cirros login: ')
            out = agent.diag_console(plan['id'], vm['name'], lines=3)
            self.assertEqual(out['stdout'].splitlines(), ['linea', 'linea', 'cirros login: '])
            with self.assertRaises(AgentError):
                agent.diag_console(plan['id'], 'otra-vm')
        source = (ROOT / 'g5/agent.py').read_text(encoding='utf-8')
        self.assertIn("logfile=%s,logappend=on", source)

    def test_shell_ready_rejects_boot_line_that_looks_like_a_prompt(self):
        """Un "#" al final de una línea del arranque no es un shell: solo vale si responde G5RDY42."""
        import socket as socketmod
        from g5.agent import shell_ready

        class Console:
            def __init__(self, replies):
                self.replies, self.sent = list(replies), []
            def sendall(self, data):
                self.sent.append(data)
            def recv(self, n):
                if self.replies:
                    return self.replies.pop(0)
                raise socketmod.timeout()
        booting = Console([b'echo G5RDY$((6*7))\r\n'])          # eco del tecleo, sin resultado
        self.assertFalse(shell_ready(booting, wait=0.3))
        shell = Console([b'echo G5RDY$((6*7))\r\n', b'G5RDY42\r\n$ '])
        self.assertTrue(shell_ready(shell, wait=2))
        source = (ROOT / 'g5/agent.py').read_text(encoding='utf-8')
        self.assertIn("not action.startswith('diag_')", source, 'diagnósticos sin candado del slice')

    def test_console_link_is_relative_to_the_novnc_page(self):
        from urllib.parse import parse_qs, urlsplit
        from g5.console import console_link
        web = urlsplit(console_link('/lconsole', 'TOK'))
        self.assertEqual(web.path, '/lconsole/vnc.html')
        self.assertEqual(parse_qs(web.query)['path'], ['websockify?token=TOK'], 'relativo a la página: sin repetir prefijo')
        ex1 = urlsplit(console_link('http://127.0.0.1:6080', 'TOK'))   # EX1: sin prefijo, igual que antes
        self.assertEqual((ex1.netloc, ex1.path, parse_qs(ex1.query)['path']), ('127.0.0.1:6080', '/vnc.html', ['websockify?token=TOK']))

    def test_unaddressed_nic_is_raised_without_ip_and_gateway_skips_it(self):
        """Ex2 15b: la VM switch recibe sus puertos arriba y sin IP; la puerta del slice no se conecta a ese enlace."""
        job = self.create(); plan = self.store.get_slice(job['slice_id'])['plan']
        vm = next(v for v in plan['vms'] if v['worker'] == 'server1')
        vm['guest'] = {'os': 'cirros'}
        for net in plan['networks']:
            net.pop('cidr', None); net.pop('gateway', None); net['dhcp'] = False
        plan['publications'] = []  # publicar exige IP (lo rechaza el validador)
        for v in plan['vms']:
            v['internet'] = False
            for nic in v['nics']:
                nic.pop('ip', None)
        agent = self.agent('worker'); sent = []
        with mock.patch.object(agent, 'load', return_value=plan), mock.patch.object(agent, 'process', return_value=4242),                 mock.patch('g5.agent.Path.read_text', return_value=' '.join(['0'] * 30)), mock.patch('g5.agent.atomic'),                 mock.patch('g5.agent.serial_execute', side_effect=lambda path, cmd, *a, **k: sent.append(cmd) or (0, '')):
            agent.guest_setup(plan['id'], vm['name'])
        self.assertNotIn('ip addr add', sent[0])
        self.assertIn('mtu 1450 up', sent[0])
        gw = self.agent('gateway')
        gw.manifest_path(plan['id']).write_text(json.dumps(plan))
        commands = []
        with mock.patch('g5.agent.output', side_effect=lambda *a, **k: commands.append(' '.join(map(str, a))) or ''),                 mock.patch('g5.agent.run', return_value=(0, '')), mock.patch.object(gw, 'owned_ovs'),                 mock.patch.object(gw, 'ensure_veth'), mock.patch.object(gw, 'ipt'), mock.patch.object(gw, 'stop_process'):
            gw.gateway(plan['id'])
        self.assertFalse(any(' addr replace ' in c and 'lan' in c for c in commands), 'sin IP en enlaces L2')

    def test_diag_ovs_is_read_only(self):
        agent = self.agent('worker'); commands = []
        def fake_run(*args, **kw):
            commands.append(args); return 0, 'br-int' if args[:2] == ('ovs-vsctl', 'list-br') else ''
        with mock.patch('g5.agent.run', side_effect=fake_run), mock.patch('g5.agent.output', side_effect=lambda *a, **k: fake_run(*a, **k)[1]):
            result = agent.diag_ovs()
        self.assertIn('br-int', result['fdb'])
        self.assertEqual({c[:2] for c in commands}, {('ovs-vsctl', 'show'), ('ovs-vsctl', 'list-br'), ('ovs-appctl', 'fdb/show')})

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
