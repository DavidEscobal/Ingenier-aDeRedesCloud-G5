"""Fase 2: topología neutral del editor -> especificación del driver Linux."""
import copy
import json
import unittest
from pathlib import Path

from g5.drivers.linux import validate_spec
from g5.drivers.linux_adapter import adapt, needs_adapter
from g5.model import Fault

ROOT = Path(__file__).resolve().parents[1]
SHA = 'a' * 64


def neutral(n=4, image='cirros-062'):
    nets = [{'name': 's%d' % k, 'cidr': '192.168.%d.0/24' % k, 'dhcp': True} for k in range(1, n)]
    vms = []
    for i in range(1, n + 1):
        nics = [{'network': 's%d' % k, 'ip': '192.168.%d.%d' % (k, 10 + i)} for k in (i - 1, i) if 1 <= k < n]
        vms.append({'name': 'n%d' % i, 'image': image, 'vcpus': 1, 'memory_mb': 512, 'disk_gb': 1, 'nics': nics})
    return {'name': 'lineal', 'provider': 'linux', 'networks': nets, 'vms': vms}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / 'config/cluster.example.json').read_text())
        self.calls = []

    def resolve(self, name):
        self.calls.append(name); return SHA

    def test_completes_workers_cvlans_image_and_passes_driver_validation(self):
        spec = neutral()
        self.assertTrue(needs_adapter(spec))
        out = adapt(spec, ['server1', 'server2', 'server3'], self.resolve)
        self.assertEqual([v['worker'] for v in out['vms']], ['server1', 'server2', 'server3', 'server1'])
        self.assertEqual([n['cvid'] for n in out['networks']], [100, 101, 102])
        self.assertTrue(all(n['dhcp'] is False for n in out['networks']))
        self.assertTrue(all(v['image'] == SHA and v['guest'] == {'os': 'cirros'} for v in out['vms']))
        self.assertEqual(self.calls, ['cirros-062'], 'una sola resolución por imagen')
        self.assertFalse(needs_adapter(out))
        validate_spec(out, self.cfg)  # el driver Linux la acepta tal cual
        self.assertNotIn('worker', spec['vms'][0], 'no modifica la entrada')

    def test_internet_vm_gets_its_own_access_network_first(self):
        spec = neutral(3)
        spec['vms'][1]['internet'] = True
        out = adapt(spec, ['server1', 'server2', 'server3'], self.resolve)
        n2 = out['vms'][1]
        self.assertEqual(n2['nics'][0], {'name': 'inet0', 'network': 'inet2', 'ip': '10.200.2.10'})
        self.assertEqual(len(n2['nics']), 3, 'acceso + sus dos enlaces')
        access = next(n for n in out['networks'] if n['name'] == 'inet2')
        self.assertEqual(access['cidr'], '10.200.2.0/27')
        self.assertEqual(len({n['cvid'] for n in out['networks']}), len(out['networks']), 'C-VLAN únicas')
        self.assertFalse(out['vms'][0].get('internet'))
        self.assertTrue(all(n['nics'][0]['name'] != 'inet0' for n in out['vms'] if not n.get('internet')))
        validate_spec(out, self.cfg)

    def test_display_name_allows_exam_names_but_not_unsafe_ones(self):
        from g5.drivers.openstack.driver import validate_spec as validate_os
        cfg = dict(self.cfg, openstack={})
        out = adapt(neutral(), ['server1', 'server2', 'server3'], self.resolve)
        out['name'] = 'Ex2_G5_test_2'
        validate_spec(out, self.cfg)
        os_spec = {'name': 'Ex2_G5_test', 'provider': 'openstack',
                   'networks': [{'name': 'l1', 'cidr': '192.168.1.0/24'}],
                   'vms': [{'name': 'vm1', 'image': 'cirros', 'vcpus': 1, 'memory_mb': 512, 'disk_gb': 1,
                            'nics': [{'network': 'l1', 'ip': '192.168.1.11'}]}]}
        validate_os(os_spec, cfg)
        for bad in ('1abc', 'a b', 'a/b', 'x' * 65):
            with self.assertRaises(Fault):
                validate_os(dict(os_spec, name=bad), cfg)

    def test_pinned_hosts_are_respected_and_others_rotate(self):
        spec = neutral(4)
        spec['vms'][0]['host'] = 'server2'
        spec['vms'][1]['host'] = 'server2'
        out = adapt(spec, ['server1', 'server2', 'server3'], self.resolve)
        self.assertEqual([v['worker'] for v in out['vms']], ['server2', 'server2', 'server1', 'server2'])
        self.assertTrue(all('host' not in v for v in out['vms']))
        validate_spec(out, self.cfg)
        spec['vms'][0]['host'] = 'worker1'
        with self.assertRaisesRegex(Fault, 'no es un worker Linux'):
            adapt(spec, ['server1', 'server2', 'server3'], self.resolve)

    def test_unaddressed_link_has_no_ip_and_still_validates(self):
        spec = neutral(3)
        spec['networks'][0] = {'name': 's1', 'dhcp': False}
        for vm in spec['vms']:
            for nic in vm['nics']:
                if nic['network'] == 's1':
                    nic.pop('ip')
        out = adapt(spec, ['server1', 'server2', 'server3'], self.resolve)
        validate_spec(out, self.cfg)
        bad = copy.deepcopy(out); bad['vms'][0]['nics'][0]['ip'] = '192.168.1.11'
        with self.assertRaisesRegex(Fault, 'sin CIDR'):
            validate_spec(bad, self.cfg)
        net = copy.deepcopy(out); net['networks'][0]['dhcp'] = True
        with self.assertRaisesRegex(Fault, 'DHCP'):
            validate_spec(net, self.cfg)

    def test_rejects_non_cirros_and_no_workers(self):
        with self.assertRaisesRegex(Fault, 'CirrOS'):
            adapt(neutral(image='ubuntu-22'), ['server1'], self.resolve)
        with self.assertRaisesRegex(Fault, 'workers'):
            adapt(neutral(), [], self.resolve)
        self.assertFalse(needs_adapter({'provider': 'openstack', 'vms': [{'name': 'a'}]}))


if __name__ == '__main__':
    unittest.main()
