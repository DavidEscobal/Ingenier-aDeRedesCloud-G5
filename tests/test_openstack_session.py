"""Cliente REST de OpenStack contra un servidor falso: tokens, reescritura, reintentos y errores."""
import socket
import unittest
from g5.drivers.openstack.session import OpenStackError, Session
from openstack_fake import FakeOpenStack, USER


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeOpenStack()
        self.fake.route('GET', '/v2.1/servers', lambda r: (200, {'servers': []}))
        self.fake.route('POST', '/v2.0/networks', lambda r: (201, {'network': {'id': 'net-1'}}))

    def tearDown(self):
        self.fake.close()

    def session(self, **cfg):
        return Session(self.fake.config(**cfg), environ=USER)

    def test_token_catalog_rewrite_and_header(self):
        s = self.session()
        status, data, _ = s.request('GET', 'compute', '/servers')
        self.assertEqual((status, data), (200, {'servers': []}))
        self.assertEqual(s.endpoint('compute'), self.fake.base + '/v2.1')
        self.assertEqual(self.fake.requests[-1][2], self.fake.tokens[0])
        scope = self.fake.auth_bodies[0]['auth']['scope']['project']
        self.assertEqual((scope['name'], scope['domain']['name']), ('cloud_admin', 'Cloud'))

    def test_token_is_reused_until_close_to_expiry(self):
        s = self.session()
        s.request('GET', 'compute', '/servers'); s.request('GET', 'compute', '/servers')
        self.assertEqual(len(self.fake.tokens), 1)
        self.fake.token_ttl = 60  # menos que el margen de renovación
        s.token(project_id='p1'); s.token(project_id='p1')
        self.assertEqual(len(self.fake.tokens), 3)

    def test_project_scoped_tokens_are_cached_separately(self):
        s = self.session()
        self.assertNotEqual(s.token(), s.token(project_id='p-slice'))
        self.assertEqual(self.fake.auth_bodies[-1]['auth']['scope'], {'project': {'id': 'p-slice'}})

    def test_expired_token_401_reauthenticates_once(self):
        s = self.session()
        s.token()
        self.fake.tokens.clear()  # Keystone invalidó el token
        self.assertEqual(s.request('GET', 'compute', '/servers')[0], 200)
        self.fake.fail('GET', '/v2.1/servers', 401, 401)
        with self.assertRaises(OpenStackError) as error:
            s.request('GET', 'compute', '/servers')
        self.assertEqual(error.exception.status, 401)

    def test_get_retries_5xx_but_post_does_not(self):
        s = self.session()
        self.fake.fail('GET', '/v2.1/servers', 503)
        self.assertEqual(s.request('GET', 'compute', '/servers')[0], 200)
        self.fake.fail('POST', '/v2.0/networks', 503)
        with self.assertRaises(OpenStackError) as error:
            s.request('POST', 'network', '/v2.0/networks', {'network': {'name': 'x'}})
        self.assertEqual(error.exception.status, 503)
        posts = [r for r in self.fake.requests if r[:2] == ('POST', '/v2.0/networks')]
        self.assertEqual(len(posts), 1)

    def test_errors_are_explicit_and_never_include_secrets(self):
        s = self.session()
        with self.assertRaises(OpenStackError) as error:
            s.request('GET', 'compute', '/servers/00000000-0000-0000-0000-000000000000')
        message = str(error.exception)
        self.assertEqual(error.exception.status, 404)
        self.assertIn('/v2.1/servers/00000000', message)
        for secret in [USER['OS_PASSWORD']] + self.fake.tokens:
            self.assertNotIn(secret, message)
            self.assertNotIn(secret, repr(s))

    def test_missing_credentials_lists_names_only(self):
        env = dict(USER); del env['OS_PASSWORD']
        with self.assertRaises(OpenStackError) as error:
            Session(self.fake.config(), environ=env)
        self.assertIn('OS_PASSWORD', str(error.exception))
        self.assertNotIn(USER['OS_USERNAME'], str(error.exception))

    def test_unreachable_endpoint_retries_then_fails(self):
        probe = socket.socket(); probe.bind(('127.0.0.1', 0)); closed = probe.getsockname()[1]; probe.close()
        cfg = self.fake.config(timeout=2)
        cfg['endpoint_map']['http://controller:8774'] = 'http://127.0.0.1:%d' % closed
        s = Session(cfg, environ=USER)
        sleeps = []
        s.sleep = sleeps.append
        with self.assertRaises(OpenStackError) as error:
            s.request('GET', 'compute', '/servers')
        self.assertIsNone(error.exception.status)
        self.assertEqual(len(sleeps), 2)


if __name__ == '__main__':
    unittest.main()
