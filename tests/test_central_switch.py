"""Contrato del agente central con OVSDB. Las pruebas de tráfico necesitan el cableado real."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from g5.agent import Agent, AgentError, mapped_interface
from scripts.plan_fase2_fabric import plan


class CentralSwitchTests(unittest.TestCase):
    def test_documented_links_and_real_interface_resolution(self):
        linux = plan('linux', 701, 2, [501, 510])
        cfg = linux['central_fabric']['linux']
        self.assertEqual((cfg['circuits'][0]['host'], cfg['circuits'][0]['uplink']), ('server1', 'fa:16:3e:6f:9f:c4'))
        self.assertEqual(linux['gateway']['data_mac'], 'fa:16:3e:d8:d5:ea')
        os_cfg = plan('openstack', 701, 2, [501, 510], ('g5ext', 600), 800)['central_fabric']['openstack']
        self.assertEqual(os_cfg['external_circuit']['uplink'], 'fa:16:3e:f3:ab:ae')
        self.assertEqual(os_cfg['circuits'][-1]['uplink'], 'fa:16:3e:0f:0a:9a')
        self.assertEqual(os_cfg['physnet'], 'physnet1')
        with self.assertRaises(ValueError):
            plan('openstack', 701, 2, [501, 510], ('g5ext', 600), 702)
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('ovs-local', 'ens42'):
                nic = Path(tmp, name)
                nic.mkdir()
                (nic/'address').write_text(os_cfg['circuits'][0]['uplink'])
            (nic/'device').mkdir()
            self.assertEqual(mapped_interface(os_cfg['circuits'][0]['uplink'], Path(tmp)), 'ens42')
            with self.assertRaises(AgentError):
                mapped_interface('fa:16:3e:00:00:00', Path(tmp))

    def test_shared_trunk_provision_preserves_existing_tenant_vlans(self):
        cfg = dict(role='switch', name='ovs1', bridge='g5-l2', segment_range=[301, 310],
                   circuits=[dict(host='server1', uplink='eth1', port='g5c101', vlan=101),
                             dict(host='server2', uplink='eth2', port='g5c102', vlan=102)])
        rules = {p: ('trunk', set(), {44, 101, 102}) for p in ('eth1', 'eth2', 'shared', 'control')}
        def read(cmd, *args):
            if args[0] == 'port-to-br':
                return 'shared'
            if args[0] == 'get-controller':
                return ''
            if args[0] == 'dump-flows':
                return 'priority=0 actions=NORMAL'
            self.assertEqual(args[0], 'list-ports')
            return 'eth1\neth2\ncontrol'
        with tempfile.TemporaryDirectory() as tmp, patch('g5.agent.port_vlans', return_value=rules), \
                patch('g5.agent.output', side_effect=read):
            agent = Agent(dict(cfg, state_dir=tmp))
            commands, changes = agent.circuit_setup()
            removed = {c['port']: c['remove'] for c in changes if 'remove' in c}
            self.assertEqual(removed, dict(eth1=[102], eth2=[101], shared=[101,102], control=[101,102]))
            self.assertNotIn('del-port', commands)
            self.assertEqual({c['create_port'] for c in changes if 'create_port' in c}, {'g5c101','g5t101','g5c102','g5t102'})
            rules['control'] = ('access', {102}, set())
            with self.assertRaisesRegex(AgentError, 'acceso'):
                agent.circuit_setup()

    def test_connect_replay_and_release_two_circuits_on_one_host(self):
        sid = 'a' * 32
        slots = [dict(host='worker1', port=p, vlan=v, uplink='uplink') for p, v in [('p1', 101), ('p2', 102)]]
        cfg = dict(role='switch', bridge='join', circuits=slots, segment_range=[300, 399])
        endpoints = [dict(host=s['host'], port=s['port'], vlan=s['vlan'], segment=301) for s in slots]
        tags = {'p1': 101, 'p2': 102, 't1': 101, 't2': 102}
        owners, writes = {}, []

        def ovs(command, *args, **kwargs):
            if command == 'ovs-ofctl':
                return 'priority=0 actions=NORMAL'
            self.assertEqual(command, 'ovs-vsctl')
            if args[0] == '--timeout=8':
                writes.append(args)
                for i, arg in enumerate(args):
                    if arg == 'set':
                        port = args[i+2]
                        tags[port] = int(args[i+3].split('=')[1])
                        if args[i+4].startswith('external_ids:'):
                            owners[port] = args[i+4].split('=')[1]
                    elif arg == 'remove':
                        owners.pop(args[i+2])
                return ''
            if args[0] == 'list-ports':
                return 'p1\np2' if args[1] == 'join' else 'uplink\nt1\nt2'
            if args[0] == 'get-controller':
                return ''
            if args[0] == 'port-to-br':
                return 'join' if args[1].startswith('p') else 'transport'
            if args[0] == '--if-exists':
                args = args[1:]
            self.assertEqual(args[0], 'get')
            port, field = args[-2:]
            if field == 'type':
                return 'patch'
            if field == 'options:peer':
                return ('t' if port.startswith('p') else 'p') + port[1:]
            if field == 'vlan_mode':
                return 'trunk' if port == 'uplink' else 'access'
            if field == 'trunks':
                return '[101,102]'
            if field == 'tag':
                return str(tags[port])
            if field == 'external_ids':
                return json.dumps({'g5_slice': owners[port]} if port in owners else {})
            self.assertEqual(field, 'external_ids:g5_slice')
            return owners.get(port, '')

        rules = {'uplink': ('trunk', set(), {101, 102}), 'transport': ('access', {0}, set()),
                 't1': ('access', {101}, set()), 't2': ('access', {102}, set())}
        with tempfile.TemporaryDirectory() as tmp, patch('g5.agent.output', side_effect=ovs), \
                patch('g5.agent.port_vlans', return_value=rules), \
                patch('g5.agent.atomic', side_effect=lambda path, obj: path.write_text(json.dumps(obj))):
            agent = Agent(dict(cfg, state_dir=tmp))
            with self.assertRaises(AgentError):
                agent.circuit_connect(sid, [dict(endpoints[0], host='worker2')])
            agent.circuit_connect(sid, endpoints)
            self.assertEqual((tags['p1'], tags['p2']), (301, 301))
            self.assertEqual((tags['t1'], tags['t2']), (101, 102))
            agent.circuit_connect(sid, endpoints)
            self.assertEqual(len(writes), 1)
            with self.assertRaises(AgentError):
                agent.circuit_connect('b' * 32, endpoints)
            agent.circuit_disconnect(sid)
            agent.circuit_disconnect(sid)
            self.assertEqual((tags['p1'], tags['p2'], owners), (101, 102, {}))
            with self.assertRaises(AgentError):
                agent.circuit_connect(sid, endpoints)
