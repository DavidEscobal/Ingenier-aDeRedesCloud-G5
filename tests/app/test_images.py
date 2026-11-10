"""D-15: Image Catalog — importar (solo admin) en streaming hasta el platform-manager y listar para todos."""
import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import unittest
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from iam_support import initialize
from test_bootstrap import HTTP, request, service

SERVICE_TOKEN = secrets.token_urlsafe(32)
QCOW2 = b"QFI\xfb" + os.urandom(300_000)


class FakePlatformImages:
    """Simula /v1/provider-images/openstack del platform-manager y registra lo recibido."""

    def __init__(self):
        self.images = [{"id": "img-cirros", "name": "cirros", "status": "active", "size": 12_000_000,
                        "disk_format": "qcow2", "visibility": "public", "created_at": "2026-10-01T00:00:00Z"},
                       {"id": "img-priv", "name": "privada", "status": "active", "size": 1, "disk_format": "raw",
                        "visibility": "private", "created_at": "2026-10-01T00:00:00Z"}]
        self.received = []

    @contextmanager
    def run(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def reply(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.headers.get("Authorization") != "Bearer " + SERVICE_TOKEN:
                    return self.reply(401, {"error": "Token inválido"})
                return self.reply(200, fake.images)

            def do_PUT(self):
                if self.headers.get("Authorization") != "Bearer " + SERVICE_TOKEN:
                    return self.reply(401, {"error": "Token inválido"})
                if self.headers.get("Transfer-Encoding"):
                    return self.reply(400, {"error": "Use Content-Length, no chunked"})
                length = int(self.headers["Content-Length"])
                data = self.rfile.read(length)
                name = re.fullmatch(r"/v1/provider-images/openstack/([^?]+)\?disk_format=(\w+)", self.path)
                fake.received.append({"name": name.group(1), "format": name.group(2), "data": data})
                if any(i["name"] == name.group(1) for i in fake.images):
                    return self.reply(409, {"error": "Ya existe una imagen con ese nombre en Glance"})
                if not data.startswith(b"QFI\xfb"):
                    return self.reply(400, {"error": "El archivo no es un qcow2 válido"})
                fake.images.append({"id": "img-new", "name": name.group(1), "status": "active", "size": len(data),
                                    "disk_format": name.group(2), "visibility": "public", "created_at": "x"})
                return self.reply(201, {"id": "img-new", "name": name.group(1), "size": len(data),
                                        "sha256": hashlib.sha256(data).hexdigest(), "status": "active"})

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


def upload(url, token, data, name, fmt="qcow2"):
    req = Request(f"{url}/v1/images?name={name}&disk_format={fmt}&description=prueba", data=data, method="POST",
                  headers={"Authorization": "Bearer " + token, "Content-Type": "application/octet-stream"})
    try:
        response = HTTP.open(req, timeout=30)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


class ImageCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        directory = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        settings, password, _ = initialize(directory)
        cls.stack.enter_context(patch.dict(os.environ, settings))
        cls.iam, _ = cls.stack.enter_context(service("g5_iam.main", **settings))
        cls.platform = FakePlatformImages()
        platform_url = cls.stack.enter_context(cls.platform.run())
        token_file = directory / "images.token"
        token_file.write_text(SERVICE_TOKEN, encoding="utf-8")
        cls.ic, _ = cls.stack.enter_context(service(
            "g5_images.main", IAM_URL=cls.iam, PLATFORM_MANAGER_URL=platform_url, PLATFORM_TOKEN_FILE=str(token_file),
            IMAGE_DB_PATH=str(directory / "catalog.db"), IMAGE_MAX_MB="1"))
        cls.gw, _ = cls.stack.enter_context(service("g5_gateway.main", IAM_URL=cls.iam, IMAGE_CATALOG_URL=cls.ic))
        status, data = request(cls.iam + "/v1/auth/login", "POST", body={"username": "admin", "password": password})
        cls.admin = data["access_token"]
        pw = secrets.token_urlsafe(18)
        request(cls.iam + "/v1/iam/users", "POST", cls.admin, {"username": "profi", "password": pw, "display_name": "p", "role": "professor"})
        cls.prof = request(cls.iam + "/v1/auth/login", "POST", body={"username": "profi", "password": pw})[1]["access_token"]

    def test_admin_imports_through_gateway_and_bytes_arrive_intact(self):
        status, image = upload(self.gw, self.admin, QCOW2, "ubuntu-mini")
        self.assertEqual(status, 201, image)
        self.assertEqual((image["name"], image["source"], image["uploaded_by"]), ("ubuntu-mini", "catalog", "admin"))
        self.assertEqual(image["sha256"], hashlib.sha256(QCOW2).hexdigest())
        self.assertEqual(self.platform.received[-1]["data"], QCOW2, "streaming sin alterar los bytes")
        status, images = request(self.gw + "/v1/images", token=self.prof)
        names = {i["name"]: i for i in images}
        self.assertEqual(names["ubuntu-mini"]["source"], "catalog")
        self.assertEqual(names["cirros"]["source"], "provider", "imágenes previas de Glance también aparecen")
        self.assertNotIn("privada", names, "solo imágenes públicas, usables por todos los proyectos")

    def test_only_admin_imports_and_errors_are_explained(self):
        before = len(self.platform.received)
        self.assertEqual(upload(self.gw, self.prof, QCOW2, "de-profesor")[0], 403)
        self.assertEqual(len(self.platform.received), before, "rechazo antes de transferir")
        self.assertEqual(upload(self.gw, self.admin, os.urandom(2 * 1024 * 1024), "enorme")[0], 413)
        status, body = upload(self.gw, self.admin, b"no es qcow2" * 100, "falsa")
        self.assertEqual(status, 422)
        self.assertIn("qcow2", body["detail"])
        status, body = upload(self.gw, self.admin, QCOW2, "cirros")
        self.assertEqual(status, 409)
        self.assertEqual(upload(self.gw, self.admin, QCOW2, "Nombre_Malo")[0], 422)
        self.assertEqual(request(self.gw + "/v1/images")[0], 401)


if __name__ == "__main__":
    unittest.main()
