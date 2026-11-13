"""Fase 2: topología neutral del editor -> especificación del driver Linux."""
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

    def test_rejects_non_cirros_and_no_workers(self):
        with self.assertRaisesRegex(Fault, 'CirrOS'):
            adapt(neutral(image='ubuntu-22'), ['server1'], self.resolve)
        with self.assertRaisesRegex(Fault, 'workers'):
            adapt(neutral(), [], self.resolve)
        self.assertFalse(needs_adapter({'provider': 'openstack', 'vms': [{'name': 'a'}]}))


if __name__ == '__main__':
    unittest.main()
