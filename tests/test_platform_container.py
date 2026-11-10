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

    def test_os_tunnel_is_private_and_platform_manager_waits_for_it(self):
        block = compose_service('os-tunnel')
        self.assertNotIn('ports:', block, 'los túneles no deben publicarse en el host')
        self.assertIn('networks: [control]', block)
        self.assertRegex(block, r'/home/tunnel/\.ssh:ro\b', 'la clave SSH debe montarse solo lectura')
        self.assertIn('profiles: [platform]', block)
        self.assertRegex(compose_service('platform-manager'),
                         r'depends_on:\s*\n\s*os-tunnel:\s*\n\s*condition: service_healthy')

    def test_os_tunnel_image_has_no_secrets_and_runs_unprivileged(self):
        folder = ROOT / 'services' / 'os-tunnel'
        docker = (folder / 'Dockerfile').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'^COPY\s+(?:--\S+\s+)*(\S+)', docker, re.M), ['entrypoint.sh'])
        self.assertRegex(docker, r'(?m)^USER tunnel$')
        script = (folder / 'entrypoint.sh').read_bytes()
        self.assertNotIn(b'\r\n', script, 'el entrypoint debe tener finales de línea LF')
        self.assertIn(b'StrictHostKeyChecking=yes', script)
        self.assertIn(b'ExitOnForwardFailure=yes', script)

    def test_slice_manager_reaches_platform_with_read_only_service_token(self):
        block = compose_service('slice-manager')
        self.assertIn('PLATFORM_MANAGER_URL: http://platform-manager:8000', block)
        self.assertRegex(block, r'slice-manager\.token:/run/g5/platform\.token:ro\b')
        self.assertIn('slice-data:/app/state/slice', block)
        self.assertNotIn('ports:', block)

    def test_only_gateway_and_web_publish_ports_and_only_on_loopback(self):
        text = (ROOT / 'deploy' / 'compose.yaml').read_text(encoding='utf-8')
        section = re.search(r'^services:\n(.*?)(?=^\S)', text, re.S | re.M).group(1)
        services = re.findall(r'^  ([a-z][a-z-]*):\n', section, re.M)
        self.assertIn('platform-manager', services)
        published = [s for s in services if 'ports:' in compose_service(s)]
        self.assertEqual(published, ['gateway', 'web'])
        for name in published:
            mappings = re.findall(r'^\s+- "([^"]+)"', compose_service(name).split('ports:')[1], re.M)
            self.assertTrue(mappings, name)
            for mapping in mappings:
                self.assertTrue(mapping.startswith('127.0.0.1:'), '%s publica %s fuera de loopback' % (name, mapping))

    def test_web_talks_only_to_gateway_and_novnc_and_runs_unprivileged(self):
        folder = ROOT / 'services' / 'web'
        nginx = (folder / 'nginx.conf').read_text(encoding='utf-8')
        # Solo dos destinos: la API (gateway) y la consola noVNC de Nova a través de os-tunnel.
        self.assertEqual(re.findall(r'proxy_pass\s+(\S+);', nginx),
                         ['http://gateway:8000/v1/images', 'http://gateway:8000/', 'http://os-tunnel:6080/'])
        console = nginx.split('location /console/')[1].split('location ')[0]
        self.assertIn('Upgrade $http_upgrade', console, 'la consola necesita WebSocket')
        self.assertIn("frame-ancestors 'none'", nginx)
        self.assertIn('nginx-unprivileged', (folder / 'Dockerfile').read_text(encoding='utf-8'))
        api = (folder / 'src' / 'api.js').read_text(encoding='utf-8')
        self.assertIn("fetch('/api' + path", api, 'la web llama solo a /api (mismo origen)')


if __name__ == '__main__':
    unittest.main()
