"""Paso 5 (D-12): gateway → slice-manager → IAM + platform-manager (simulado), con procesos reales.

El platform-manager se simula con un servidor HTTP controlado que registra token e Idempotency-Key.
"""
import json
import os
import re
import secrets
import tempfile
import threading
import unittest
import uuid
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from iam_support import initialize
from test_bootstrap import request, service

SERVICE_TOKEN = secrets.token_urlsafe(32)
SPEC = {"name": "os-lineal-1g", "provider": "openstack", "networks": [{"name": "l1", "cidr": "10.60.1.0/24"}],
        "vms": [{"name": "vm1", "image": "cirros", "vcpus": 1, "memory_mb": 512, "disk_gb": 1, "nics": [{"network": "l1"}]}]}


class FakePlatform:
    def __init__(self):
        self.slices, self.calls = {}, []

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

            def handle_any(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length)) if length else None
                fake.calls.append({"method": self.command, "path": self.path, "body": body,
                                   "auth": self.headers.get("Authorization"),
                                   "key": self.headers.get("Idempotency-Key")})
                if self.headers.get("Authorization") != "Bearer " + SERVICE_TOKEN:
                    return self.reply(401, {"error": "Token inválido"})
                if self.command == "POST" and self.path == "/v1/slices":
                    if body.get("name") == "invalido":
                        return self.reply(400, {"error": "vms: se requiere al menos una VM"})
                    for sid, s in fake.slices.items():
                        if s["key"] == self.headers.get("Idempotency-Key"):
                            return self.reply(202, {"id": s["job"], "slice_id": sid, "status": "PENDING"})
                    sid, job = uuid.uuid4().hex, uuid.uuid4().hex
                    fake.slices[sid] = {"key": self.headers.get("Idempotency-Key"), "job": job, "status": "QUEUED",
                                        "name": body.get("name"), "spec": body}
                    return self.reply(202, {"id": job, "slice_id": sid, "status": "PENDING"})
                if self.command == "GET" and self.path == "/v1/slices":
                    return self.reply(200, [{"id": k, "status": v["status"], "owner": "slice-manager"} for k, v in fake.slices.items()])
                console = re.fullmatch(r"/v1/slices/([0-9a-f]{32})/vms/([a-z][a-z0-9-]*)/console", self.path)
                if console and self.command == "POST" and console.group(1) in fake.slices:
                    vms = [v["name"] for v in fake.slices[console.group(1)]["spec"].get("vms", [])]
                    if console.group(2) not in vms:
                        return self.reply(404, {"error": "VM inexistente"})
                    return self.reply(201, {"url": "/console/vnc_auto.html?path=%3Ftoken%3Dabc123", "provider": "openstack"})
                match = re.fullmatch(r"/v1/slices/([0-9a-f]{32})(/events)?", self.path)
                if match and match.group(1) in fake.slices:
                    sid = match.group(1)
                    if self.command == "GET" and match.group(2):
                        return self.reply(200, [{"seq": 2, "event": "READY", "detail": "ok", "timestamp": 2.0, "job": "x"},
                                                {"seq": 1, "event": "ACCEPTED", "detail": "slice-manager", "timestamp": 1.0, "job": "x"}])
                    if self.command == "GET":
                        return self.reply(200, {"id": sid, "status": fake.slices[sid]["status"], "plan": {},
                                                "spec": fake.slices[sid]["spec"]})
                    if self.command == "DELETE":
                        fake.slices[sid]["status"] = "DELETING"
                        return self.reply(202, {"id": uuid.uuid4().hex, "slice_id": sid, "status": "PENDING"})
                return self.reply(404, {"error": "Slice inexistente"})

            do_GET = do_POST = do_DELETE = handle_any

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


class SliceFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        directory = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        settings, password, _ = initialize(directory)
        iam_token = directory / "iam-service.token"
        iam_token.write_text(secrets.token_urlsafe(40), encoding="utf-8")
        settings["IAM_SERVICE_TOKEN_FILE"] = str(iam_token)
        cls.stack.enter_context(patch.dict(os.environ, settings))
        cls.iam, _ = cls.stack.enter_context(service("g5_iam.main", **settings))
        cls.platform = FakePlatform()
        platform_url = cls.stack.enter_context(cls.platform.run())
        token_file = directory / "platform.token"
        token_file.write_text(SERVICE_TOKEN + "\n", encoding="utf-8")
        cls.sm, _ = cls.stack.enter_context(service(
            "g5_slice_manager.main", IAM_URL=cls.iam, PLATFORM_MANAGER_URL=platform_url,
            PLATFORM_TOKEN_FILE=str(token_file), SLICE_DB_PATH=str(directory / "slices.db"),
            IAM_SERVICE_TOKEN_FILE=str(iam_token)))
        cls.gw, _ = cls.stack.enter_context(service("g5_gateway.main", IAM_URL=cls.iam, SLICE_MANAGER_URL=cls.sm))
        cls.admin = cls.login("admin", password)
        status, _ = request(cls.iam + "/v1/iam/courses", "POST", cls.admin, {"id": "TEL141", "name": "Cloud"})
        assert status == 201, status
        cls.prof, cls.prof_id = cls.user("prof1", "professor")
        cls.other, cls.other_id = cls.user("prof2", "professor")
        cls.student, cls.student_id = cls.user("alumno1", "student")

    @classmethod
    def login(cls, username, password):
        status, data = request(cls.iam + "/v1/auth/login", "POST", body={"username": username, "password": password})
        assert status == 200, (status, data)
        return data["access_token"]

    @classmethod
    def user(cls, username, role):
        password = secrets.token_urlsafe(18)
        status, data = request(cls.iam + "/v1/iam/users", "POST", cls.admin,
                               {"username": username, "password": password, "display_name": username, "role": role})
        assert status == 201, (status, data)
        status, _ = request(cls.iam + f"/v1/iam/courses/TEL141/members/{data['id']}", "PUT", cls.admin, {})
        assert status == 200, status
        return cls.login(username, password), data["id"]

    def create(self, token, spec=SPEC, course="TEL141", key=None, base=None):
        return request((base or self.gw) + "/v1/slices", "POST", token, {"course_id": course, "spec": spec},
                       headers={"Idempotency-Key": key or uuid.uuid4().hex})

    def test_professor_lifecycle_through_gateway(self):
        status, accepted = self.create(self.prof)
        self.assertEqual(status, 202, accepted)
        sid = accepted["slice_id"]
        call = self.platform.calls[-1]
        self.assertEqual(call["auth"], "Bearer " + SERVICE_TOKEN, "el platform-manager recibe el token de servicio")
        self.assertNotEqual(call["auth"], "Bearer " + self.prof, "nunca el token del usuario")
        self.assertEqual(call["body"], SPEC)
        status, rows = request(self.gw + "/v1/slices", token=self.prof)
        self.assertEqual(status, 200)
        mine = [r for r in rows if r["id"] == sid]
        self.assertEqual(len(mine), 1)
        self.assertEqual((mine[0]["status"], mine[0]["course_id"], mine[0]["owner"]), ("QUEUED", "TEL141", "prof1"))
        status, detail = request(self.gw + "/v1/slices/" + sid, token=self.prof)
        self.assertEqual(status, 200)
        self.assertEqual([e["event"] for e in detail["events"]], ["ACCEPTED", "READY"])
        status, deleted = request(self.gw + "/v1/slices/" + sid, "DELETE", self.prof,
                                  headers={"Idempotency-Key": uuid.uuid4().hex})
        self.assertEqual((status, deleted["slice_id"]), (202, sid))
        self.assertEqual(request(self.gw + "/v1/slices/" + sid, token=self.prof)[1]["status"], "DELETING")

    def test_isolation_between_users_and_admin_scope(self):
        status, accepted = self.create(self.prof)
        sid = accepted["slice_id"]
        self.assertNotIn(sid, [r["id"] for r in request(self.gw + "/v1/slices", token=self.other)[1]])
        self.assertEqual(request(self.gw + "/v1/slices/" + sid, token=self.other)[0], 404)
        self.assertEqual(request(self.gw + "/v1/slices/" + sid, "DELETE", self.other,
                                 headers={"Idempotency-Key": uuid.uuid4().hex})[0], 404)
        self.assertIn(sid, [r["id"] for r in request(self.gw + "/v1/slices", token=self.admin)[1]])
        self.assertEqual(request(self.gw + "/v1/slices/" + sid, token=self.admin)[0], 200)

    def test_iam_policy_denies_students_and_foreign_courses(self):
        before = len(self.platform.calls)
        self.assertEqual(self.create(self.student)[0], 403)
        self.assertEqual(self.create(self.prof, course="OTRO")[0], 403)
        self.assertEqual(self.create(None)[0], 401)
        self.assertEqual(request(self.gw + "/v1/slices", token="token-falso")[0], 401)
        self.assertEqual(len(self.platform.calls), before, "nada llega al platform-manager sin autorización")

    def test_idempotency_is_per_user_and_errors_are_explained(self):
        key = uuid.uuid4().hex
        first, second = self.create(self.prof, key=key), self.create(self.prof, key=key)
        self.assertEqual(first[1]["slice_id"], second[1]["slice_id"], "reintento con la misma clave: mismo slice")
        other = self.create(self.other, key=key)
        self.assertNotEqual(other[1]["slice_id"], first[1]["slice_id"], "otra persona con la misma clave: slice distinto")
        status, error = self.create(self.prof, spec=dict(SPEC, name="invalido"))
        self.assertEqual(status, 422)
        self.assertIn("se requiere al menos una VM", error["detail"])
        self.assertEqual(request(self.gw + "/v1/slices", "POST", self.prof, {"course_id": "TEL141", "spec": SPEC})[0], 422,
                         "Idempotency-Key obligatoria")

    def test_console_and_vm_list_only_for_owner_or_admin(self):
        status, accepted = self.create(self.prof)
        sid = accepted["slice_id"]
        status, detail = request(self.gw + "/v1/slices/" + sid, token=self.prof)
        self.assertEqual([(v["name"], v["networks"]) for v in detail["vms"]], [("vm1", ["l1"])])
        path = "/v1/slices/%s/vms/vm1/console" % sid
        status, console = request(self.gw + path, "POST", self.prof)
        self.assertEqual(status, 200, console)
        self.assertEqual((console["vm"], console["provider"]), ("vm1", "openstack"))
        self.assertTrue(console["url"].startswith("/console/"))
        self.assertEqual(request(self.gw + path, "POST", self.other)[0], 404, "otro profesor no obtiene la consola")
        self.assertEqual(request(self.gw + path, "POST", self.admin)[0], 200)
        self.assertEqual(request(self.gw + "/v1/slices/%s/vms/nada/console" % sid, "POST", self.prof)[0], 404)
        self.assertEqual(request(self.gw + path, "POST")[0], 401)

    def test_professor_assigns_slice_and_student_sees_it_and_its_consoles(self):
        status, accepted = self.create(self.prof)
        sid = accepted["slice_id"]
        base = self.gw + "/v1/slices/" + sid
        self.assertTrue(request(base, token=self.prof)[1]["assignable"], "slice de profesor registrado en IAM")
        # El profesor ve a los alumnos de su curso; el alumno no.
        status, students = request(self.gw + "/v1/iam/courses/TEL141/students", token=self.prof)
        self.assertEqual(status, 200)
        self.assertIn("alumno1", [s["username"] for s in students])
        self.assertEqual(request(self.gw + "/v1/iam/courses/TEL141/students", token=self.student)[0], 403)
        # Antes de asignar: el alumno no ve nada.
        self.assertNotIn(sid, [r["id"] for r in request(self.gw + "/v1/slices", token=self.student)[1]])
        self.assertEqual(request(base, token=self.student)[0], 404)
        self.assertEqual(request(base + "/vms/vm1/console", "POST", self.student)[0], 404)
        # Otro profesor no puede asignar; el dueño sí.
        self.assertEqual(request(base + "/assignments", "POST", self.other, {"user_id": self.student_id})[0], 404)
        status, assigned = request(base + "/assignments", "POST", self.prof, {"user_id": self.student_id})
        self.assertEqual((status, [a["username"] for a in assigned]), (200, ["alumno1"]))
        self.assertEqual(request(base + "/assignments", "POST", self.prof, {"user_id": self.other_id})[0], 409,
                         "solo se asigna a alumnos")
        # Después: el alumno lo ve, lo consulta y abre consolas, pero no lo gestiona.
        self.assertIn(sid, [r["id"] for r in request(self.gw + "/v1/slices", token=self.student)[1]])
        status, detail = request(base, token=self.student)
        self.assertEqual((status, detail["can_manage"], detail["assignable"]), (200, False, False))
        self.assertEqual(request(base + "/vms/vm1/console", "POST", self.student)[0], 200)
        self.assertEqual(request(base, "DELETE", self.student, headers={"Idempotency-Key": uuid.uuid4().hex})[0], 404)
        self.assertEqual(request(base + "/assignments", token=self.student)[0], 404)
        # Quitar la asignación revoca de inmediato.
        status, assigned = request(base + "/assignments/" + self.student_id, "DELETE", self.prof)
        self.assertEqual((status, assigned), (200, []))
        self.assertEqual(request(base, token=self.student)[0], 404)
        self.assertEqual(request(base + "/vms/vm1/console", "POST", self.student)[0], 404)

    def test_internal_registration_requires_the_service_token(self):
        body = {"id": "x" * 32, "course_id": "TEL141", "professor_id": self.prof_id, "vms": []}
        url = self.iam + "/v1/iam/internal/slices/" + "x" * 32
        for token in (None, self.admin, self.prof, "otro-token-cualquiera-de-servicio-xxxxxxxx"):
            self.assertEqual(request(url, "PUT", token, body)[0], 401)
        # Y el gateway no la expone.
        self.assertEqual(request(self.gw + "/v1/iam/internal/slices/" + "x" * 32, "PUT", self.admin, body)[0], 404)

    def test_admin_slices_are_not_assignable(self):
        status, accepted = self.create(self.admin)
        base = self.gw + "/v1/slices/" + accepted["slice_id"]
        self.assertFalse(request(base, token=self.admin)[1]["assignable"])
        status, body = request(base + "/assignments", "POST", self.admin, {"user_id": self.student_id})
        self.assertEqual(status, 409)
        self.assertIn("no admite asignaciones", body["detail"])

    def test_capabilities_report_lifecycle_when_platform_is_configured(self):
        status, caps = request(self.gw + "/v1/platform/capabilities", token=self.prof)
        self.assertEqual(status, 200)
        self.assertTrue(caps["features"]["slice_lifecycle"])
        self.assertFalse(caps["features"]["placement"])


if __name__ == "__main__":
    unittest.main()
