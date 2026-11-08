import json
from contextlib import closing
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from g5_iam.main import app
from iam_support import initialize


class IAMTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings, self.password, self.secret = initialize(self.directory.name)
        env = patch.dict(os.environ, self.settings)
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.admin_token = self.login("admin", self.password)
        self.admin = self.call("GET", "/v1/auth/me").json()

    def call(self, method, path, body=None, token=None):
        return self.client.request(method, path, json=body,
                                   headers={"Authorization": "Bearer " + (token or self.admin_token)})

    def login(self, username, password):
        response = self.client.post("/v1/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def user(self, name, role):
        response = self.call("POST", "/v1/iam/users", {"username": name, "display_name": name,
                              "password": self.password, "role": role})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json(), self.login(name, self.password)

    def course(self, course_id="TEL141", modify=True):
        self.assertEqual(self.call("POST", "/v1/iam/courses", {"id": course_id, "name": course_id,
                              "professor_can_modify": modify}).status_code, 201)

    def member(self, user, course_id="TEL141"):
        response = self.call("PUT", f"/v1/iam/courses/{course_id}/members/{user['id']}",
                             {"quotas": {"max_slices": 2, "max_vcpus": 4}})
        self.assertEqual(response.status_code, 200, response.text)

    def decide(self, token, action, resource=None, course=None):
        body = {"action": action}
        if resource:
            body["resource_id"] = resource
        if course:
            body["course_id"] = course
        response = self.call("POST", "/v1/iam/authorize", body, token)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["allowed"]

    def setup_resources(self, modify=True):
        professor, pt = self.user("professor", "professor")
        other_professor, opt = self.user("otherprof", "professor")
        student, st = self.user("student", "student")
        other_student, ost = self.user("otherstudent", "student")
        self.course(modify=modify)
        self.course("OTHER")
        for user in (professor, other_professor, student, other_student):
            self.member(user)
        for identity, kind, parent in (("slice-1", "slice", None), ("vm-1", "vm", "slice-1")):
            body = {"id": identity, "kind": kind, "course_id": "TEL141", "professor_id": professor["id"]}
            if parent:
                body["parent_slice_id"] = parent
            response = self.call("POST", "/v1/iam/resources", body)
            self.assertEqual(response.status_code, 201, response.text)
        return professor, pt, other_professor, opt, student, st, other_student, ost

    def test_roles_course_and_resource_isolation(self):
        professor, pt, _, opt, student, st, other_student, ost = self.setup_resources()
        self.assertTrue(self.decide(pt, "slice.create", course="TEL141"))
        self.assertFalse(self.decide(pt, "slice.create", course="OTHER"))
        self.assertFalse(self.decide(st, "slice.create", course="TEL141"))
        self.assertTrue(self.decide(pt, "slice.delete", "slice-1"))
        self.assertFalse(self.decide(opt, "slice.delete", "slice-1"))
        self.assertFalse(self.decide(pt, "slice.read", "slice-1", "OTHER"))
        self.assertFalse(self.decide(self.admin_token, "slice.read", "unknown"))
        self.assertFalse(self.decide(st, "slice.read", "slice-1"))
        self.assertEqual(self.call("PUT", f"/v1/iam/resources/slice-1/assignments/{student['id']}", token=st).status_code, 403)
        self.assertEqual(self.call("PUT", f"/v1/iam/resources/slice-1/assignments/{student['id']}", token=pt).status_code, 200)
        self.assertTrue(self.decide(st, "slice.read", "slice-1"))
        self.assertFalse(self.decide(ost, "slice.read", "slice-1"))
        self.assertFalse(self.decide(st, "slice.delete", "slice-1"))
        self.assertFalse(self.decide(st, "vm.console", "vm-1"))
        self.assertEqual(self.call("PUT", f"/v1/iam/resources/vm-1/assignments/{student['id']}", token=pt).status_code, 200)
        self.assertTrue(self.decide(st, "vm.console", "vm-1"))
        self.assertFalse(self.decide(ost, "vm.console", "vm-1"))
        self.assertFalse(self.decide(st, "slice.read", "vm-1"))
        self.assertEqual(len(self.call("GET", "/v1/iam/resources", token=st).json()), 2)
        self.assertEqual(self.call("GET", "/v1/iam/resources", token=ost).json(), [])
        # Immediate revocation, same unexpired JWT, plus removing child VM grants.
        self.assertEqual(self.call("DELETE", f"/v1/iam/resources/slice-1/assignments/{student['id']}", token=pt).status_code, 200)
        self.assertFalse(self.decide(st, "slice.read", "slice-1"))
        self.assertFalse(self.decide(st, "vm.console", "vm-1"))
        self.call("PUT", f"/v1/iam/resources/slice-1/assignments/{student['id']}", token=pt)
        self.assertFalse(self.decide(st, "vm.console", "vm-1"))
        self.call("DELETE", f"/v1/iam/courses/TEL141/members/{student['id']}")
        self.assertFalse(self.decide(st, "slice.read", "slice-1"))
        self.member(student)
        self.assertFalse(self.decide(st, "slice.read", "slice-1"))
        self.call("DELETE", f"/v1/iam/courses/TEL141/members/{professor['id']}")
        self.assertFalse(self.decide(pt, "slice.create", course="TEL141"))

    def test_course_policy_and_admin_scope(self):
        _, pt, _, _, _, st, _, _ = self.setup_resources(modify=False)
        self.assertFalse(self.decide(pt, "slice.delete", "slice-1"))
        self.assertTrue(self.decide(pt, "slice.read", "slice-1"))
        self.assertTrue(self.decide(self.admin_token, "slice.delete", "slice-1"))
        self.assertTrue(self.decide(self.admin_token, "image.manage"))
        self.assertFalse(self.decide(st, "image.manage"))
        self.assertEqual(self.call("GET", "/v1/iam/users", token=pt).status_code, 403)
        self.assertEqual(self.call("POST", "/v1/iam/courses", {"id": "X", "name": "X"}, st).status_code, 403)
        self.assertEqual(self.call("GET", "/v1/iam/audit", token=st).status_code, 403)

    def test_tokens_signature_expiry_audience_and_logout(self):
        self.assertEqual(self.client.get("/v1/auth/me").status_code, 401)
        self.assertEqual(self.call("GET", "/v1/auth/me", token="forged").status_code, 401)
        claims = jwt.decode(self.admin_token, self.secret, algorithms=["HS256"], audience="g5-app", issuer="g5-iam")
        for update in ({"exp": int(time.time()) - 1}, {"aud": "wrong"}, {"iss": "wrong"}, {"jti": "unknown"}):
            bad = jwt.encode({**claims, **update}, self.secret, algorithm="HS256")
            self.assertEqual(self.call("GET", "/v1/auth/me", token=bad).status_code, 401)
        forged = jwt.encode(claims, "x" * 64, algorithm="HS256")
        self.assertEqual(self.call("GET", "/v1/auth/me", token=forged).status_code, 401)
        unsigned = jwt.encode(claims, "", algorithm="none")
        self.assertEqual(self.call("GET", "/v1/auth/me", token=unsigned).status_code, 401)
        self.assertEqual(self.call("POST", "/v1/auth/logout").status_code, 200)
        self.assertEqual(self.call("GET", "/v1/auth/me").status_code, 401)

    def test_disable_role_reset_and_last_admin(self):
        student, token = self.user("student", "student")
        self.assertEqual(self.call("PATCH", f"/v1/iam/users/{self.admin['id']}", {"active": False}).status_code, 409)
        self.assertEqual(self.call("PATCH", f"/v1/iam/users/{student['id']}", {"role": "admin"}, token).status_code, 403)
        self.assertEqual(self.call("PATCH", f"/v1/iam/users/{student['id']}", {"active": False}).status_code, 200)
        self.assertEqual(self.call("GET", "/v1/auth/me", token=token).status_code, 401)
        self.assertEqual(self.client.post("/v1/auth/login", json={"username": "student", "password": self.password}).status_code, 401)
        self.call("PATCH", f"/v1/iam/users/{student['id']}", {"active": True})
        self.assertEqual(self.call("GET", "/v1/auth/me", token=token).status_code, 401)
        token = self.login("student", self.password)
        self.call("PATCH", f"/v1/iam/users/{student['id']}", {"role": "professor"})
        self.assertEqual(self.call("GET", "/v1/auth/me", token=token).status_code, 401)
        token = self.login("student", self.password)
        self.call("POST", f"/v1/iam/users/{student['id']}/password", {"password": self.password + "new"})
        self.assertEqual(self.call("GET", "/v1/auth/me", token=token).status_code, 401)

    def test_password_change_and_generic_login_failures(self):
        student, token = self.user("student", "student")
        wrong = self.client.post("/v1/auth/login", json={"username": "student", "password": "wrong"})
        unknown = self.client.post("/v1/auth/login", json={"username": "nobody", "password": "wrong"})
        self.assertEqual(wrong.status_code, unknown.status_code)
        self.assertEqual(wrong.json(), unknown.json())
        result = self.call("POST", "/v1/auth/password", {"current_password": self.password,
                           "password": self.password + "new"}, token)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.call("GET", "/v1/auth/me", token=token).status_code, 401)
        self.login("student", self.password + "new")

    def test_throttle_and_input_secrecy(self):
        for _ in range(5):
            result = self.client.post("/v1/auth/login", json={"username": "missing", "password": "wrong"})
            self.assertEqual(result.status_code, 401)
        result = self.client.post("/v1/auth/login", json={"username": "missing", "password": "wrong"})
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result.headers["Retry-After"], "60")
        response = self.call("POST", "/v1/iam/users", {"username": "baduser", "display_name": "Bad",
                              "password": "short-secret", "role": "student"})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("short-secret", response.text)
        response = self.call("POST", "/v1/iam/authorize", {"action": "platform.read", "role": "admin"})
        self.assertEqual(response.status_code, 422)
        response = self.call("POST", "/v1/iam/authorize", {"action": "unknown.action"})
        self.assertEqual(response.status_code, 422)

    def test_persistence_hashes_audit_and_restart(self):
        student, token = self.user("student", "student")
        self.course()
        self.member(student)
        membership = self.call("GET", f"/v1/iam/courses/TEL141/members/{student['id']}", token=token)
        self.assertEqual(membership.json()["quotas"]["max_slices"], 2)
        self.call("GET", "/v1/iam/users", token=token)
        events = self.call("GET", "/v1/iam/audit").json()
        self.assertTrue(any(e["outcome"] == "denied" for e in events))
        self.assertNotIn(self.password, json.dumps(events))
        self.assertNotIn(token, json.dumps(events))
        self.assertNotIn("password_hash", self.call("GET", "/v1/iam/users").text)
        with closing(sqlite3.connect(self.settings["IAM_DB_PATH"])) as db:
            value = db.execute("SELECT password_hash FROM users WHERE id=?", (student["id"],)).fetchone()[0]
            self.assertTrue(value.startswith("$argon2id$"))
            self.assertNotIn(self.password, value)
        # New lifespan + new Store against same persisted files.
        with TestClient(app) as restarted:
            response = restarted.get("/v1/auth/me", headers={"Authorization": "Bearer " + token})
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
