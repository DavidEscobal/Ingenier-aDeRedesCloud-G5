"""R4: VM Placement (BCDP v2) — caso de control del HLD, regresión de la guía, validador, VMs fijadas,
zona, telemetría vencida, límite de tiempo, determinismo y token de servicio."""
import math
import os
import random
import secrets
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from g5_placement import engine, main
from g5_placement.planner import plan

TOKEN = secrets.token_urlsafe(32)
POLICY = {"cpu_ratio": 2.0, "cpu_limit": 0.85, "max_age_s": 15, "timeout_s": 1.0}


def generar_datos(N, M, semilla=10, ocupados=0, holgura=1.0):
    """Generador de bcdp2.py, devuelto en el formato del adaptador."""
    rng = random.Random(semilla)
    cpu = [rng.randint(1, 4) for _ in range(N)]
    ram = [rng.choice([1, 2, 4, 8]) for _ in range(N)]
    disco = [rng.choice([4, 8, 16, 32]) for _ in range(N)]
    demanda = [cpu[i] * rng.randint(20, 70) for i in range(N)]
    a = [int(h < ocupados) for h in range(M)]
    cpu_previa = [2 * v for v in a]; ram_previa = [2 * v for v in a]; disco_previo = [8 * v for v in a]
    fondo = [25 + 25 * v for v in a]
    orden = list(range(N)); rng.shuffle(orden)
    grupos = [orden[h::M] for h in range(M)]
    cap = []
    for h, g in enumerate(grupos):
        c_nom = 1 + math.ceil(holgura * (cpu_previa[h] + sum(cpu[i] for i in g)) / 2)
        c_real = math.ceil(holgura * (fondo[h] + sum(demanda[i] for i in g)) / 85)
        f = max(2, c_nom, c_real)
        cap.append([2 * (f - 1), 85 * f, ram_previa[h] + math.ceil(holgura * 1.10 * sum(ram[i] for i in g)),
                    disco_previo[h] + math.ceil(holgura * 1.10 * sum(disco[i] for i in g))])
    uso = [[cpu_previa[h], fondo[h], ram_previa[h], disco_previo[h]] for h in range(M)]
    dem = [[cpu[i], demanda[i], ram[i], disco[i]] for i in range(N)]
    return {"N": N, "M": M, "a": a, "_cap": cap, "_uso": uso, "_dem": dem}


def control(M):
    dems = [192, 160, 96, 64, 64, 64]
    return {"N": 6, "M": M, "a": [0] * M, "_cap": [[6, 340, 100, 100]] * M, "_uso": [[0, 20, 0, 0]] * M,
            "_dem": [[1, x, 1, 1] for x in dems]}


def host(i, **kw):
    h = {"id": "server%d" % i, "zone": "z1", "cpu_cores": 4, "ram_mb": 2816, "disk_mb": 5120}
    h.update(kw)
    return h


def vm(i, **kw):
    v = {"id": "vm%d" % i, "vcpus": 1, "ram_mb": 512, "disk_mb": 1024}
    v.update(kw)
    return v


def request(hosts, vms, zone=None, **policy):
    return {"zone": zone, "hosts": hosts, "vms": vms, "policy": dict(POLICY, **policy)}


class Engine(unittest.TestCase):
    def test_control_hld_z2(self):
        for M in (2, 3):
            d = control(M)
            ok, z = engine.validar(d, engine.bcdp_v2(d))
            self.assertTrue(ok)
            self.assertEqual(z, 2)

    def test_bfd_peor_en_control(self):
        d = control(3)
        asg = engine.bfd_hld(d)
        ok, z = engine.validar(d, asg) if asg else (False, None)
        self.assertTrue(not ok or z > 2)

    def test_regresion_guia(self):
        for N, M, holg, z_medio in ((60, 10, 1.5, 6.2), (120, 20, 1.2, 15.2), (120, 20, 1.0, 19.1)):
            zs = []
            for semilla in range(110, 201, 10):
                d = generar_datos(N, M, semilla, holgura=holg)
                ok, z = engine.validar(d, engine.bcdp_v2(d))
                self.assertTrue(ok, (N, M, semilla, holg))
                zs.append(z)
            self.assertAlmostEqual(sum(zs) / len(zs), z_medio, places=1)

    def test_validador(self):
        d = control(2)
        self.assertFalse(engine.validar(d, {0: 0, 1: 0, 2: 0, 3: 0, 4: 0})[0])          # VM sin asignar
        self.assertFalse(engine.validar(d, {i: 0 for i in range(6)})[0])                 # host excedido
        self.assertTrue(engine.validar(d, {0: 0, 1: 1, 2: 1, 3: 0, 4: 0, 5: 1})[0])


class Planner(unittest.TestCase):
    def test_slice_referencia_sin_telemetria(self):
        # 3 VMs de 2 vCPU sin perfil: con el 85 % de 4 CPU cabe una por host (tabla de la guía).
        hosts = [host(i) for i in (1, 2, 3)]
        r = plan(request(hosts, [vm(i, vcpus=2) for i in range(3)]))
        self.assertEqual(r["status"], "PLAN_FOUND")
        self.assertEqual(r["hosts_opened"], 3)
        r = plan(request(hosts, [vm(i, vcpus=2) for i in range(4)]))
        self.assertEqual(r["status"], "HEURISTIC_NO_PLAN")
        self.assertIn("recurso más ajustado: CPU real", r["reason"])

    def test_consolida_con_cpu_prevista(self):
        r = plan(request([host(i) for i in (1, 2, 3)], [vm(i, cpu_cent=40) for i in range(5)]))
        self.assertEqual(r["status"], "PLAN_FOUND")
        self.assertEqual(r["hosts_opened"], 1)

    def test_prefiere_host_ocupado(self):
        hosts = [host(1), host(2, occupied=True, vcpus_used=1, ram_used_mb=512, disk_used_mb=1024)]
        r = plan(request(hosts, [vm(1, cpu_cent=50)]))
        self.assertEqual(r["plan"], {"vm1": "server2"})
        self.assertEqual(r["hosts_opened"], 0)

    def test_vm_fijada(self):
        r = plan(request([host(1), host(2)], [vm(1, host="server2"), vm(2, cpu_cent=50)]))
        self.assertEqual(r["plan"]["vm1"], "server2")
        self.assertEqual(r["plan"]["vm2"], "server2")       # el host fijado ya cuenta como abierto
        r = plan(request([host(1)], [vm(1, host="server9")]))
        self.assertEqual(r["status"], "HEURISTIC_NO_PLAN")
        r = plan(request([host(1)], [vm(1, host="server1", ram_mb=9999)]))
        self.assertIn("no cabe (RAM)", r["reason"])

    def test_zona_salud_y_telemetria(self):
        hosts = [host(1, zone="z2"), host(2, healthy=False), host(3, age_s=40), host(4, age_s=3)]
        r = plan(request(hosts, [vm(1)], zone="z1"))
        self.assertEqual(r["plan"], {"vm1": "server4"})
        self.assertEqual({d["host"] for d in r["discarded_hosts"]}, {"server1", "server2", "server3"})
        r = plan(request(hosts[:3], [vm(1)], zone="z1"))
        self.assertEqual(r["status"], "HEURISTIC_NO_PLAN")
        self.assertIn("zona z1", r["reason"])

    def test_timeout(self):
        hosts = [host(i, cpu_cores=64, ram_mb=10 ** 6, disk_mb=10 ** 7) for i in range(200)]
        r = plan(request(hosts, [vm(i, vcpus=1 + i % 3, cpu_cent=10 + i % 50) for i in range(1500)], timeout_s=0.05))
        self.assertEqual(r["status"], "PLANNING_TIMEOUT")
        self.assertLess(r["elapsed_ms"], 2000)

    def test_determinista(self):
        req = request([host(i) for i in range(1, 5)], [vm(i, cpu_cent=30 + 7 * i) for i in range(8)])
        self.assertEqual(plan(req)["plan"], plan(req)["plan"])


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name) / "token"
        path.write_text(TOKEN + "\n", encoding="utf-8")
        os.environ["PLACEMENT_TOKEN_FILE"] = str(path)
        main._tokens.clear()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        main._tokens.clear()
        os.environ.pop("PLACEMENT_TOKEN_FILE", None)
        cls.tmp.cleanup()

    def body(self):
        return {"provider": "linux", "hosts": [host(1), host(2)], "vms": [vm(1), vm(2, host="server1")]}

    def test_requiere_token(self):
        self.assertEqual(self.client.post("/v1/placements", json=self.body()).status_code, 401)
        r = self.client.post("/v1/placements", json=self.body(), headers={"Authorization": "Bearer x" * 2})
        self.assertEqual(r.status_code, 401)

    def test_plan(self):
        r = self.client.post("/v1/placements", json=self.body(), headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["status"], "PLAN_FOUND")
        self.assertEqual(data["plan"]["vm2"], "server1")
        self.assertEqual(self.client.get("/healthz").json()["status"], "ok")

    def test_valida_entrada(self):
        body = self.body(); body["vms"].append(vm(1))
        r = self.client.post("/v1/placements", json=body, headers={"Authorization": "Bearer " + TOKEN})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
