"""Empaquetado del platform-manager: regla de escucha y artefactos Docker sin secretos."""
import re
import unittest
from pathlib import Path

from g5.api import bind_allowed

ROOT = Path(__file__).resolve().parent.parent


def compose_service(name):
    """Bloque de texto de un servicio en deploy/compose.yaml (sin depender de PyYAML)."""
    text = (ROOT / 'deploy' / 'compose.yaml').read_text(encoding='utf-8')
    match = re.search(r'^  %s:\n(.*?)(?=^  \S|^\S)' % re.escape(name), text, re.S | re.M)
    if not match:
        raise AssertionError('servicio %s ausente en compose.yaml' % name)
    return match.group(1)


class BindRuleTests(unittest.TestCase):
    def test_loopback_always_allowed(self):
        for host in ('127.0.0.1', '::1', 'localhost'):
            self.assertTrue(bind_allowed(host))

    def test_network_bind_requires_tls_or_internal_flag(self):
        self.assertFalse(bind_allowed('0.0.0.0'))
        self.assertFalse(bind_allowed('0.0.0.0', cert='c.pem'))  # falta la clave
        self.assertTrue(bind_allowed('0.0.0.0', cert='c.pem', key='k.pem'))
        self.assertTrue(bind_allowed('0.0.0.0', internal_network=True))


class ContainerArtifactTests(unittest.TestCase):
    def test_dockerfile_copies_only_core_and_listens_on_internal_network(self):
        text = (ROOT / 'services' / 'platform-manager' / 'Dockerfile').read_text(encoding='utf-8')
        copies = re.findall(r'^COPY\s+(\S+)', text, re.M)
        self.assertEqual(copies, ['g5', 'api', 'templates'])
        self.assertIn('--internal-network', text)
        self.assertRegex(text, r'(?m)^USER appuser$', 'no debe correr como root')

    def test_dockerignore_is_a_whitelist_without_secrets(self):
        lines = [l.strip() for l in (ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()
                 if l.strip() and not l.startswith('#')]
        self.assertEqual(lines[0], '*')
        allowed = {l[1:].rstrip('/') for l in lines if l.startswith('!')}
        self.assertEqual(allowed, {'g5', 'api', 'templates'})

    def test_compose_keeps_platform_manager_private_and_secrets_read_only(self):
        block = compose_service('platform-manager')
        self.assertNotIn('ports:', block, 'no debe publicar puertos en el host')
        self.assertIn('networks: [control]', block)
        for target in ('/run/g5/cluster.json', '/run/g5/keys.json', '/run/g5/openstack.env', '/home/appuser/.ssh'):
            self.assertRegex(block, re.escape(target) + r':ro\b', target + ' debe montarse solo lectura')

    def test_only_gateway_publishes_ports(self):
        text = (ROOT / 'deploy' / 'compose.yaml').read_text(encoding='utf-8')
        section = re.search(r'^services:\n(.*?)(?=^\S)', text, re.S | re.M).group(1)
        services = re.findall(r'^  ([a-z][a-z-]*):\n', section, re.M)
        self.assertIn('platform-manager', services)
        published = [s for s in services if 'ports:' in compose_service(s)]
        self.assertEqual(published, ['gateway'])


if __name__ == '__main__':
    unittest.main()
