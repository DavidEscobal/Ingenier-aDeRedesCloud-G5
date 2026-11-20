"""R4 en el Slice Manager: Monitoreo -> VM Placement (BCDP v2 real) -> spec con host por VM -> platform-manager,
con registro de planes recientes y reintento si la reserva atómica falló por capacidad."""
import asyncio
import json
import unittest

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from g5_placement import main as placement_main
from g5_slice_manager.placement import Ledger, Planner

TOKEN_P, TOKEN_M = "p" * 40, "m" * 40
SPEC = {"name": "anillo", "provider": "openstack", "networks": [{"name": "l1", "cidr": "10.0.0.0/24"}],
        "vms": [{"name": "vm%d" % i, "image": "cirros", "vcpus": 1, "memory_mb": 512, "disk_gb": 1,
                 "nics": [{"network": "l1"}]} for i in range(1, 4)]}


def host(name, zone="nova", **kw):
    h = {"id": name, "provider": "openstack", "zone": zone, "cpu_cores": 4, "vcpus_max": None, "ram_mb": 3936,
         "disk_mb": 9216, "vcpus_used": 0, "ram_used_mb": 512, "disk_used_mb": 0, "occupied": False,
         "cpu_real_cent": None, "healthy": True, "age_s": 3.0}
    h.update(kw)
    return h


class Env:
    """Monitoreo simulado + el servicio vm-placement real (en proceso)."""

    def __init__(self, hosts):
        self.hosts, self.placements = hosts, []
        placement_main._tokens[:] = [TOKEN_P]
        self.app_client = TestClient(placement_main.app)

    def monitoring(self, request):
        assert request.headers["Authorization"] == "Bearer " + TOKEN_M
        hosts = self.hosts[request.url.params["provider"]] if isinstance(self.hosts, dict) else self.hosts
        return httpx.Response(200, json={"collected_at": 0, "age_s": 3, "hosts": hosts})

    def placement(self, request):
        body = json.loads(request.content)
        self.placements.append(body)
        r = self.app_client.post("/v1/placements", json=body, headers={"Authorization": request.headers["Authorization"]})
        return httpx.Response(r.status_code, json=r.json())

    def planner(self, clock=None):
        p = Planner(httpx.AsyncClient(base_url="http://mon", transport=httpx.MockTransport(self.monitoring)),
                    httpx.AsyncClient(base_url="http://pl", transport=httpx.MockTransport(self.placement)),
                    TOKEN_M, TOKEN_P, {"cpu_ratio": 2.0, "cpu_limit": 0.85, "max_age_s": 15, "timeout_s": 1.0})
        if clock:
            p.ledger = Ledger(clock=clock)
        return p


def run(coro):
    return asyncio.run(coro)


class SlicePlacement(unittest.TestCase):
    def tearDown(self):
        placement_main._tokens.clear()

    def test_plan_escribe_host_y_zona(self):
        env = Env([host("worker1", "zona-a"), host("worker2", "zona-a"), host("worker3", "zona-b")])
        sent = []

        async def submit(spec):
            sent.append(spec)
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        job, summary = run(env.planner().admit(SPEC, "zona-b", submit))
        self.assertEqual(summary["status"], "PLAN_FOUND")
        self.assertEqual({v["host"] for v in sent[0]["vms"]}, {"worker3"})
        self.assertEqual({v["zone"] for v in sent[0]["vms"]}, {"zona-b"})
        self.assertEqual(summary["hosts_opened"], 1)
        self.assertNotIn("host", SPEC["vms"][0])                 # la spec original no se toca

    def test_disco_decimal_se_planifica_redondeando_hacia_arriba(self):
        # Anexo del Ex2: Ubuntu 20.04 con 2,5 GB. Antes int(2.5) = 2 GB subestimaba el disco.
        env = Env([host("worker1", disk_mb=2600), host("worker2")])
        spec = json.loads(json.dumps(SPEC)); spec["vms"] = spec["vms"][:1]; spec["vms"][0]["disk_gb"] = 2.5

        async def submit(s):
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        job, summary = run(env.planner().admit(spec, None, submit))
        self.assertEqual(env.placements[0]["vms"][0]["disk_mb"], 2560)
        self.assertEqual(summary["status"], "PLAN_FOUND")
        planner = env.planner()
        planner.ledger.add("openstack", dict(spec, vms=[dict(spec["vms"][0], host="worker1")]))
        self.assertEqual(planner.ledger.usage("openstack")["worker1"][2], 2560)
        spec["vms"][0]["disk_gb"] = "x"
        with self.assertRaises(HTTPException) as e:
            run(env.planner().plan(spec))
        self.assertEqual(e.exception.status_code, 422)

    def test_linux_usa_el_disco_libre_real_y_reparte_entre_servidores(self):
        # Caso real (19/11): 6 GB reservables por servidor en cluster.json, pero ~6 GB libres de verdad y el agente
        # exige además 2 GB de margen y las imágenes base. Antes el plan juntaba las 3 VMs en un servidor y el agente
        # rechazaba el slice; ahora la Ubuntu queda sola y las CirrOS en otro servidor.
        hosts = [host(n, "linux", provider="linux", disk_mb=6144, ram_mb=3840, ram_used_mb=0, disk_free_mb=free)
                 for n, free in (("server1", 5573), ("server2", 6033), ("server3", 5747))]
        spec = {"name": "lineal", "provider": "linux", "networks": [], "vms": [
            {"name": "vm1", "image": "cirros-062", "vcpus": 1, "memory_mb": 512, "disk_gb": 1},
            {"name": "vm2", "image": "focal-server-cloudimg-amd64", "vcpus": 1, "memory_mb": 1024, "disk_gb": 2.5},
            {"name": "vm3", "image": "cirros-062", "vcpus": 1, "memory_mb": 512, "disk_gb": 1}]}

        def images(request):
            assert request.headers["Authorization"] == "Bearer " + "x" * 40
            return httpx.Response(200, json=[{"name": "cirros-062", "size": 21430272},
                                             {"name": "focal-server-cloudimg-amd64", "size": 987693056}])
        env = Env(hosts)
        planner = env.planner()
        planner.platform = httpx.AsyncClient(base_url="http://pm", transport=httpx.MockTransport(images))
        planner.platform_token = "x" * 40
        placed, summary = run(planner.plan(spec))
        where = {v["name"]: v["host"] for v in placed["vms"]}
        self.assertNotIn(where["vm2"], (where["vm1"], where["vm3"]), "la Ubuntu no cabe junto a las CirrOS")
        self.assertEqual(env.placements[0]["hosts"][1]["disk_mb"], 6033 - 2048 - 942 - 21)
        # Sin el dato de disco libre (p. ej. telemetría sin métricas) se usa la capacidad configurada.
        for h in hosts:
            h["disk_free_mb"] = None
        placed, _ = run(Env(hosts).planner().plan(spec))
        self.assertEqual(len({v["host"] for v in placed["vms"]}), 1)

    def test_sin_recursos_rechaza_con_motivo(self):
        env = Env([host("worker1", ram_used_mb=3800), host("worker2", healthy=False)])

        async def submit(spec):
            raise AssertionError("no debe llegar al platform-manager")
        with self.assertRaises(HTTPException) as e:
            run(env.planner().admit(SPEC, None, submit))
        self.assertEqual(e.exception.status_code, 409)
        self.assertIn("RAM", e.exception.detail)

    def test_registro_de_planes_recientes_evita_doble_asignacion(self):
        # Un host con espacio para 3 VMs pequeñas: dos slices seguidos con la misma muestra de monitoreo.
        now = [0.0]
        env = Env([host("worker1", cpu_real_cent=0, ram_mb=1600, ram_used_mb=0)])
        planner = env.planner(clock=lambda: now[0])

        async def submit(spec):
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        run(planner.admit(SPEC, None, submit))
        with self.assertRaises(HTTPException) as e:                  # sin el registro se habría sobreasignado
            run(planner.admit(SPEC, None, submit))
        self.assertEqual(e.exception.status_code, 409)
        now[0] = 1000.0                                              # vencido: manda de nuevo el monitoreo
        run(planner.admit(SPEC, None, submit))

    def test_reintenta_si_la_reserva_fallo_por_capacidad(self):
        env = Env([host("worker1"), host("worker2")])
        calls = []

        async def submit(spec):
            calls.append(spec)
            if len(calls) == 1:
                raise HTTPException(409, "Capacidad reservable insuficiente en worker1")
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        planner = env.planner()
        _, summary = run(planner.admit(SPEC, None, submit, wait=0))
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(len(env.placements), 2)

        async def other(spec):
            raise HTTPException(409, "Puerto externo reservado")
        with self.assertRaises(HTTPException):                       # otros 409 no se reintentan
            run(planner.admit(SPEC, None, other, wait=0))

    def test_vm_fijada_por_el_usuario(self):
        env = Env([host("worker1"), host("worker2")])
        spec = json.loads(json.dumps(SPEC)); spec["vms"][0]["host"] = "worker2"
        sent = []

        async def submit(s):
            sent.append(s)
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        run(env.planner().admit(spec, None, submit))
        self.assertEqual(sent[0]["vms"][0]["host"], "worker2")
        self.assertEqual(env.placements[0]["vms"][0]["host"], "worker2")

    def test_monitoreo_caido_o_spec_incompleta(self):
        env = Env([])
        env.monitoring = lambda r: httpx.Response(503, json={"detail": "Monitoreo sin muestras"})
        with self.assertRaises(HTTPException) as e:
            run(env.planner().plan(SPEC))
        self.assertEqual(e.exception.status_code, 503)
        with self.assertRaises(HTTPException) as e:
            run(env.planner().plan({"provider": "linux", "vms": [{"name": "x"}]}))
        self.assertEqual(e.exception.status_code, 422)


def linux(name, **kw):
    return host(name, "linux", provider="linux", **kw)


AUTO = dict(SPEC, provider="auto")


class AutoProvider(unittest.TestCase):
    """LAB7: el módulo decide la plataforma cuando la entrada pide modo automático (casos A1–A5 del informe)."""

    def tearDown(self):
        placement_main._tokens.clear()

    def admit(self, hosts, submit=None, spec=AUTO):
        sent = []

        async def accept(s):
            sent.append(s)
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        job, summary = run(Env(hosts).planner().admit_auto(spec, None, submit or accept, wait=0))
        return summary, sent

    def test_a1_elige_el_unico_proveedor_con_capacidad(self):
        summary, sent = self.admit({"linux": [linux("server1", ram_used_mb=3800)],
                                    "openstack": [host("worker1"), host("worker2")]})
        self.assertEqual((summary["provider"], summary["mode"]), ("openstack", "auto"))
        self.assertEqual(sent[0]["provider"], "openstack")
        self.assertTrue(all(v["host"].startswith("worker") and v["zone"] == "nova" for v in sent[0]["vms"]))
        self.assertEqual([r["provider"] for r in summary["rejected"]], ["linux"])

    def test_a2_elige_el_que_abre_menos_hosts_nuevos(self):
        # Linux tendría que encender un servidor vacío; OpenStack tiene uno ya ocupado con hueco (Z = 0).
        summary, sent = self.admit({"linux": [linux("server1"), linux("server2")],
                                    "openstack": [host("worker1", occupied=True, vcpus_used=1, ram_used_mb=512, cpu_real_cent=0)]})
        self.assertEqual(summary["provider"], "openstack")
        self.assertEqual(summary["hosts_opened"], 0)
        self.assertEqual({c["provider"]: c["hosts_opened"] for c in summary["candidates"]}, {"openstack": 0, "linux": 1})

    def test_a3_empate_prefiere_linux(self):
        summary, sent = self.admit({"linux": [linux("server1")], "openstack": [host("worker1")]})
        self.assertEqual(summary["provider"], "linux")
        self.assertNotIn("zone", sent[0]["vms"][0], "la zona de Nova solo se escribe en OpenStack")
        self.assertEqual({v["host"] for v in sent[0]["vms"]}, {"server1"})

    def test_a4_ninguno_puede_rechaza_con_el_motivo_de_cada_uno(self):
        with self.assertRaises(HTTPException) as e:
            self.admit({"linux": [linux("server1", ram_used_mb=3800)], "openstack": [host("worker1", healthy=False)]})
        self.assertEqual(e.exception.status_code, 409)
        self.assertIn("linux:", e.exception.detail)
        self.assertIn("openstack:", e.exception.detail)

    def test_a5_si_la_plataforma_rechaza_la_spec_prueba_la_siguiente(self):
        calls = []

        async def submit(s):
            calls.append(s["provider"])
            if s["provider"] == "linux":
                raise HTTPException(409, "Linux admite imágenes CirrOS o Ubuntu (debian-12)")
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        summary, _ = self.admit({"linux": [linux("server1")], "openstack": [host("worker1")]}, submit)
        self.assertEqual(calls, ["linux", "openstack"])
        self.assertEqual(summary["provider"], "openstack")
        self.assertIn("debian-12", summary["rejected"][0]["reason"])

    def test_vm_fijada_decide_la_plataforma_y_carrera_perdida_replanifica(self):
        spec = json.loads(json.dumps(AUTO)); spec["vms"][0]["host"] = "worker1"
        summary, sent = self.admit({"linux": [linux("server1")], "openstack": [host("worker1")]}, spec=spec)
        self.assertEqual((summary["provider"], sent[0]["vms"][0]["host"]), ("openstack", "worker1"))
        calls = []

        async def submit(s):
            calls.append(s["provider"])
            if len(calls) == 1:
                raise HTTPException(409, "Capacidad reservable insuficiente en server1")
            return {"id": "j", "slice_id": "s", "status": "PENDING"}
        summary, _ = self.admit({"linux": [linux("server1")], "openstack": [host("worker1")]}, submit)
        self.assertEqual(summary["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
