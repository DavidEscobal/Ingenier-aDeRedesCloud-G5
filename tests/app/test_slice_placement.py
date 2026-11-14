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
        return httpx.Response(200, json={"collected_at": 0, "age_s": 3, "hosts": self.hosts})

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


if __name__ == "__main__":
    unittest.main()
