"""D-15: importar imágenes a Glance en streaming, con verificación de formato y compensación."""
import hashlib
import http.client
import io
import json
import unittest

from g5.model import Fault
from test_openstack_driver import OpenStackFixture

QCOW2 = b'QFI\xfb' + b'\x00\x00\x00\x03' + b'g5' * 50000   # cabecera qcow2 + relleno (~100 KB)


class GlanceImportTests(OpenStackFixture):
    def test_import_streams_to_glance_and_reports_checksum(self):
        result = self.driver.import_image('ubuntu-mini', 'qcow2', len(QCOW2), io.BytesIO(QCOW2))
        self.assertEqual((result['name'], result['status'], result['size']), ('ubuntu-mini', 'active', len(QCOW2)))
        self.assertEqual(result['sha256'], hashlib.sha256(QCOW2).hexdigest())
        stored = next(i for i in self.cloud.images if i['name'] == 'ubuntu-mini')
        self.assertEqual((stored['data'], stored['visibility'], stored['disk_format']), (QCOW2, 'public', 'qcow2'))
        self.assertIn('ubuntu-mini', [i['name'] for i in self.driver.list_images()])
        self.driver.image('ubuntu-mini')  # el despliegue ya puede resolverla por nombre

    def test_rejects_bad_input_without_leaving_images(self):
        before = len(self.cloud.images)
        cases = [('Nombre_Malo', 'qcow2', QCOW2), ('cirros', 'qcow2', QCOW2), ('otra', 'vmdk', QCOW2),
                 ('falsa', 'qcow2', b'esto no es qcow2' * 100)]
        for name, fmt, data in cases:
            with self.subTest(name=name):
                with self.assertRaises(Fault):
                    self.driver.import_image(name, fmt, len(data), io.BytesIO(data))
        self.assertEqual(len(self.cloud.images), before, 'compensación: nada a medias en Glance')

    def test_truncated_upload_and_glance_failure_are_compensated(self):
        before = len(self.cloud.images)
        with self.assertRaisesRegex(Fault, 'incompleta'):
            self.driver.import_image('corta', 'qcow2', len(QCOW2), io.BytesIO(QCOW2[:1000]))
        self.cloud.error_names.add('rota')
        with self.assertRaises(Exception):
            self.driver.import_image('rota', 'qcow2', len(QCOW2), io.BytesIO(QCOW2))
        self.assertEqual(len(self.cloud.images), before)


class LinuxMaterializationTests(OpenStackFixture):
    """Fase 2: la copia Linux de una imagen del catálogo se trae de Glance, se verifica y se reutiliza."""

    def test_pulls_once_from_glance_and_registers_by_sha(self):
        from unittest import mock
        self.driver.import_image('cirros-test', 'qcow2', len(QCOW2), io.BytesIO(QCOW2))
        with mock.patch('g5.api.inspect_image', return_value={'virtual-size': 117440512}) as inspect:
            first = self.app.linux_image('cirros-test')
            second = self.app.linux_image('cirros-test')
        self.assertEqual(first, hashlib.sha256(QCOW2).hexdigest())
        self.assertEqual(second, first)
        self.assertEqual(inspect.call_count, 1, 'la segunda vez se reutiliza la copia local')
        self.assertEqual((self.store.directory / 'images' / (first + '.qcow2')).read_bytes(), QCOW2)
        self.assertEqual(self.store.rows('SELECT name FROM images WHERE id=?', (first,))[0]['name'], 'cirros-test')

    def test_unknown_or_unsafe_image_leaves_nothing(self):
        from unittest import mock
        with self.assertRaises(Fault):
            self.app.linux_image('no-existe')
        self.driver.import_image('mala', 'qcow2', len(QCOW2), io.BytesIO(QCOW2))
        with mock.patch('g5.api.inspect_image', side_effect=Fault('Importar una base autónoma sin backing file')):
            with self.assertRaises(Fault):
                self.app.linux_image('mala')
        self.assertEqual(list((self.store.directory / 'images').iterdir()), [])
        self.assertEqual(self.store.rows('SELECT * FROM images'), [])


class ProviderImageAPITests(OpenStackFixture):
    """Rutas HTTP del platform-manager: PUT en streaming con Content-Length, solo admin/service."""

    def setUp(self):
        super().setUp()
        import hashlib as h
        import threading
        from g5.api import Server
        self.app.keys = [{'subject': 'svc', 'role': 'service', 'sha256': h.sha256(b'svc-token').hexdigest()},
                         {'subject': 'alumno', 'role': 'user', 'sha256': h.sha256(b'user-token').hexdigest()}]
        self.server = Server(('127.0.0.1', 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        super().tearDown()

    def http(self, method, path, token, body=b'', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        conn.request(method, path, body=body, headers=dict({'Authorization': 'Bearer ' + token}, **(headers or {})))
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, json.loads(data) if data else None

    def test_upload_list_and_permissions(self):
        status, body = self.http('PUT', '/v1/provider-images/openstack/debian-mini?disk_format=qcow2', 'svc-token', QCOW2)
        self.assertEqual(status, 201, body)
        self.assertEqual(body['sha256'], hashlib.sha256(QCOW2).hexdigest())
        status, images = self.http('GET', '/v1/provider-images/openstack', 'svc-token')
        self.assertIn('debian-mini', [i['name'] for i in images])
        self.assertEqual(self.http('PUT', '/v1/provider-images/openstack/otra', 'user-token', QCOW2)[0], 403)
        self.assertEqual(self.http('PUT', '/v1/provider-images/openstack/otra', 'nada', QCOW2)[0], 401)


if __name__ == '__main__':
    unittest.main()
