"""Real HTTP/process tests; upstream faults use an explicitly controlled stub.

Run: python -m unittest discover -s tests/app -v
No SSH, R2, VM provisioning or Docker required.
"""
import json
import os
from contextlib import contextmanager, ExitStack
from unittest.mock import patch
from iam_support import initialize
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[2]
HTTP = build_opener(ProxyHandler({}))


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url, method="GET", token=None, body=None, headers=None):
    try:
        data = json.dumps(body).encode() if body is not None else None
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        if token:
            request_headers["Authorization"] = "Bearer " + token
        response = HTTP.open(Request(url, data=data, headers=request_headers, method=method), timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


@contextmanager
def service(module, **settings):
    port = free_port()
    env = {**os.environ, **settings}
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", module + ":app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    healthy = request(base + "/healthz")[0] == 200
                except (OSError, ValueError):
                    healthy = False
                if healthy:
                    break
                time.sleep(0.05)
            else:
                healthy = False
            if process.poll() is not None or not healthy:
                output.seek(0)
                raise AssertionError("Service failed to start: " + output.read().decode(errors="replace"))
            yield base, process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


@contextmanager
def upstream(status=200, body=b"{}", delay=0):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

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


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        directory = cls.stack.enter_context(tempfile.TemporaryDirectory())
        settings, cls.password, _ = initialize(directory)
        cls.stack.enter_context(patch.dict(os.environ, settings))
        cls.iam, _ = cls.stack.enter_context(service("g5_iam.main", **settings))
        cls.stack.enter_context(patch.dict(os.environ, {"IAM_URL": cls.iam}))
        status, data = request(cls.iam + "/v1/auth/login", "POST", body={"username": "admin", "password": cls.password})
        assert status == 200
        cls.token = data["access_token"]

    def test_real_services_and_dependency_failure(self):
        with service("g5_slice_manager.main") as (manager, manager_process):
            with service("g5_gateway.main", SLICE_MANAGER_URL=manager) as (gateway, _):
                self.assertEqual(request(gateway + "/healthz")[0], 200)
                status, data = request(gateway + "/readyz")
                self.assertEqual(status, 200)
                self.assertEqual(data["dependencies"], {"slice-manager": "ok", "iam": "ok"})
                direct = request(manager + "/v1/capabilities", token=self.token)
                forwarded = request(gateway + "/v1/platform/capabilities", token=self.token)
                self.assertEqual(forwarded, direct)
                self.assertEqual(forwarded[0], 200)
                self.assertEqual(forwarded[1]["phase"], "bootstrap")
                self.assertTrue(forwarded[1]["features"]["iam"])
                self.assertFalse(any(v for k, v in forwarded[1]["features"].items() if k != "iam"))
                for base in (manager, gateway):
                    self.assertEqual(request(base + "/v1/slices", "POST")[0], 404)
                # Kill actual dependency after successful communication, same gateway process.
                manager_process.terminate()
                manager_process.wait(timeout=5)
                self.assertEqual(request(gateway + "/healthz")[0], 200)
                self.assertEqual(request(gateway + "/readyz"),
                                 (503, {"detail": "slice_manager_unavailable"}))
                self.assertEqual(request(gateway + "/v1/platform/capabilities", token=self.token)[0], 503)

    def test_gateway_login_and_direct_service_security(self):
        with service("g5_slice_manager.main") as (manager, _):
            with service("g5_gateway.main", SLICE_MANAGER_URL=manager) as (gateway, _):
                for base, route in ((gateway, "/v1/platform/capabilities"), (manager, "/v1/capabilities")):
                    self.assertEqual(request(base + route, headers={"X-Role": "admin", "X-User-Id": "admin"})[0], 401)
                    self.assertEqual(request(base + route, token="forged")[0], 401)
                status, session = request(gateway + "/v1/auth/login", "POST", body={"username": "admin", "password": self.password})
                self.assertEqual(status, 200)
                token = session["access_token"]
                self.assertEqual(request(gateway + "/v1/auth/me", token=token)[1]["role"], "admin")
                self.assertEqual(request(gateway + "/v1/platform/capabilities", token=token)[0], 200)
                self.assertEqual(request(gateway + "/v1/auth/logout", "POST", token=token)[0], 200)
                self.assertEqual(request(manager + "/v1/capabilities", token=token)[0], 401)

    def test_iam_outage_fails_closed(self):
        with upstream(503) as unavailable:
            with service("g5_slice_manager.main", IAM_URL=unavailable) as (manager, _):
                with service("g5_gateway.main", SLICE_MANAGER_URL=manager, IAM_URL=unavailable) as (gateway, _):
                    self.assertEqual(request(gateway + "/healthz")[0], 200)
                    self.assertEqual(request(gateway + "/v1/platform/capabilities", token=self.token)[0], 503)
                    self.assertEqual(request(manager + "/v1/capabilities", token=self.token)[0], 503)
                    self.assertEqual(request(gateway + "/readyz")[0], 503)

    def test_invalid_upstream_responses(self):
        for status, body in ((200, b"not-json"), (200, b'{}'),
                             (500, b'{"secret":"must-not-escape"}'), (302, b'{}')):
            with self.subTest(status=status, body=body):
                with upstream(status, body) as url:
                    with service("g5_gateway.main", SLICE_MANAGER_URL=url) as (gateway, _):
                        self.assertEqual(request(gateway + "/v1/platform/capabilities", token=self.token),
                                         (502, {"detail": "slice_manager_bad_response"}))

    def test_upstream_not_ready(self):
        with upstream(503) as url:
            with service("g5_gateway.main", SLICE_MANAGER_URL=url) as (gateway, _):
                self.assertEqual(request(gateway + "/readyz"),
                                 (503, {"detail": "slice_manager_unavailable"}))

    def test_timeout(self):
        with upstream(delay=0.4) as url:
            with service("g5_gateway.main", SLICE_MANAGER_URL=url,
                         UPSTREAM_TIMEOUT_SECONDS="0.05") as (gateway, _):
                self.assertEqual(request(gateway + "/v1/platform/capabilities", token=self.token),
                                 (504, {"detail": "slice_manager_timeout"}))

    def test_published_contracts_match_services(self):
        for name, module in (("gateway", "g5_gateway.main"),
                             ("slice-manager", "g5_slice_manager.main"), ("iam", "g5_iam.main")):
            with self.subTest(service=name):
                with service(module) as (base, _):
                    expected = json.loads((ROOT / "contracts" / "http" /
                                           f"{name}.openapi.json").read_text(encoding="utf-8"))
                    self.assertEqual(request(base + "/openapi.json"), (200, expected))


if __name__ == "__main__":
    unittest.main()
