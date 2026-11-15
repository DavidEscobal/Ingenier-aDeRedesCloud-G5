"""D-13: Monitoring — normalización de la muestra del platform-manager, estado actual, historial y permisos."""
import asyncio
import os
import secrets
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from g5_monitoring import main
from g5_monitoring.normalize import hosts_from_sample

SERVICE = secrets.token_urlsafe(32)
USERS = {"tok-admin": {"active": True, "role": "admin"}, "tok-alumno": {"active": True, "role": "student"}}


def sample(ts, cpu=120):
    return {"timestamp": ts, "linux": [
        {"node": "server1", "zone": "linux", "enabled": True,
         "capacity": {"vcpus": 4, "memory_mb": 3840, "disk_gb": 6},
         "allocated": {"vms": 2, "vcpus": 2, "memory_mb": 1024, "disk_gb": 2},
         "metrics": {"timestamp": ts, "cpu_cores": 4, "cpu_real_cent": cpu, "memory_total_mb": 3936,
                     "memory_available_mb": 2500, "disk_free_mb": 9000, "load": [0.2, 0.1, 0.1],
                     "vms": [{"sid": "a" * 32, "vm": "vm1", "pid": 1, "rss_mb": 200, "cpu_cent": 7}]}},
        {"node": "server2", "zone": "linux", "enabled": True,
         "capacity": {"vcpus": 4, "memory_mb": 3840, "disk_gb": 6},
         "allocated": {"vms": 0, "vcpus": 0, "memory_mb": 0, "disk_gb": 0}, "error": "server2/metrics: timeout"},
        {"node": "server3", "zone": "linux", "enabled": False,
         "capacity": {"vcpus": 4, "memory_mb": 3840, "disk_gb": 6},
         "allocated": {"vms": 0, "vcpus": 0, "memory_mb": 0, "disk_gb": 0},
         "metrics": {"timestamp": ts, "cpu_cores": 4, "cpu_real_cent": 5, "vms": []}}],
        "openstack": {"hosts": [
            {"node": "worker1", "zone": "zona-a", "state": "up", "status": "enabled", "vcpus": 4, "vcpus_used": 2,
             "memory_mb": 3936, "memory_mb_used": 1536, "local_gb": 9, "local_gb_used": 2,
             "disk_available_least": 1, "running_vms": 2},
            {"node": "worker2", "zone": "nova", "state": "down", "status": "enabled", "vcpus": 4, "vcpus_used": 0,
             "memory_mb": 3936, "memory_mb_used": 512, "local_gb": 9, "local_gb_used": 0,
             "disk_available_least": None, "running_vms": 0}]}}


class Normalize(unittest.TestCase):
    def test_linux_y_openstack(self):
        now = time.time()
        data = hosts_from_sample(sample(now - 4), now)
        s1, s2, s3 = data["linux"]
        self.assertEqual((s1["cpu_cores"], s1["vcpus_max"], s1["vcpus_used"], s1["ram_used_mb"], s1["disk_mb"]),
                         (4, 4, 2, 1024, 6144))
        self.assertTrue(s1["healthy"] and s1["occupied"])
        self.assertAlmostEqual(s1["age_s"], 4, delta=0.5)
        self.assertFalse(s2["healthy"]); self.assertIsNone(s2["cpu_real_cent"]); self.assertIn("timeout", s2["error"])
        self.assertFalse(s3["healthy"]); self.assertEqual(s3["error"], "en mantenimiento")
        w1, w2 = data["openstack"]
        self.assertEqual(w1["zone"], "zona-a")
        self.assertEqual(w1["disk_used_mb"], 2 * 1024)       # manda lo comprometido en Nova (local_gb_used)
        self.assertEqual(w1["disk_free_mb"], 1024)           # disk_available_least solo se informa
        self.assertIsNone(w1["cpu_real_cent"])
        self.assertFalse(w2["healthy"])


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        (d / "svc").write_text(SERVICE + "\n", encoding="utf-8")
        (d / "plat").write_text(secrets.token_urlsafe(24), encoding="utf-8")
        cls.env = {"MONITORING_TOKEN_FILE": str(d / "svc"), "PLATFORM_TOKEN_FILE": str(d / "plat"),
                   "MONITORING_DB_PATH": str(d / "m.db"), "MONITORING_INTERVAL_S": "0"}
        os.environ.update(cls.env)
        cls.ctx = TestClient(main.app)
        cls.client = cls.ctx.__enter__()

        def iam(request):
            user = USERS.get(request.headers.get("Authorization", "")[7:])
            return httpx.Response(200, json=user) if user else httpx.Response(401, json={})
        main.app.state.iam = httpx.AsyncClient(base_url="http://iam", transport=httpx.MockTransport(iam))

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)
        for k in cls.env:
            os.environ.pop(k, None)
        cls.tmp.cleanup()

    def get(self, path, token):
        return self.client.get(path, headers={"Authorization": "Bearer " + token})

    def test_estado_historial_y_permisos(self):
        self.assertEqual(self.client.get("/v1/monitoring/state").status_code, 401)
        self.assertEqual(self.get("/v1/monitoring/state", "otro").status_code, 401)
        now = time.time()
        for n, cpu in enumerate((100, 150, 200)):
            main.app.state.samples.add(sample(now - 30 + 10 * n, cpu))
        r = self.get("/v1/monitoring/state?provider=linux", SERVICE)
        self.assertEqual(r.status_code, 200, r.text)
        hosts = r.json()["hosts"]
        self.assertEqual([h["id"] for h in hosts], ["server1", "server2", "server3"])
        self.assertEqual(hosts[0]["cpu_real_cent"], 200)
        self.assertTrue(hosts[0]["vm_usage"])
        alumno = self.get("/v1/monitoring/state", "tok-alumno").json()["hosts"]
        self.assertEqual(len(alumno), 5)
        self.assertFalse(any(h["vm_usage"] for h in alumno))          # el detalle por VM es solo de admin
        self.assertTrue(self.get("/v1/monitoring/state", "tok-admin").json()["hosts"][0]["vm_usage"])
        h = self.get("/v1/monitoring/history?host=server1&minutes=5", "tok-alumno").json()
        self.assertEqual([p["cpu_real_cent"] for p in h["points"]], [100, 150, 200])
        self.assertEqual(self.get("/v1/monitoring/history?host=serverX", SERVICE).status_code, 404)


class Collector(unittest.TestCase):
    def test_collect_once(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        seen = []

        def platform(request):
            seen.append(request.headers["Authorization"])
            return httpx.Response(200, json=sample(time.time()))
        state = SimpleNamespace(samples=main.Samples(Path(tmp.name) / "s.db", 3600), platform_token="p" * 20,
                                platform=httpx.AsyncClient(base_url="http://pm", transport=httpx.MockTransport(platform)))
        self.addCleanup(state.samples.close)
        self.assertTrue(asyncio.run(main.collect_once(SimpleNamespace(state=state))))
        self.assertEqual(seen, ["Bearer " + "p" * 20])
        self.assertEqual(state.samples.latest()["linux"][0]["node"], "server1")
        state.platform = httpx.AsyncClient(base_url="http://pm", transport=httpx.MockTransport(lambda r: httpx.Response(503)))
        self.assertFalse(asyncio.run(main.collect_once(SimpleNamespace(state=state))))
        self.assertIn("503", state.last_error)
        old = main.Samples(Path(tmp.name) / "r.db", 60)
        old.add({"timestamp": time.time() - 3600}); old.add({"timestamp": time.time()})
        self.assertEqual(len(old.since(0)), 1)                     # retención
        old.close()


if __name__ == "__main__":
    unittest.main()
