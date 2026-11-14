"""Planificación de un slice (R4) desde el Slice Manager, según la arquitectura de G5:

    1. Monitoreo   -> estado actual de los hosts del proveedor (capacidad, compromisos, CPU real, edad)
    2. VM Placement -> plan {vm -> host} con BCDP v2 o rechazo con motivo
    3. El plan se escribe en la spec (`host` por VM; en OpenStack también su zona) y el platform-manager
       la reserva de forma atómica. Si la capacidad cambió (409), se vuelve a planificar.

Como la telemetría puede tener hasta ~10 s, los planes admitidos recientemente se suman como compromiso
durante LEDGER_TTL_S (conservador: puede contarse dos veces mientras Nova o el registro aún no lo reflejan).
La telemetría no reserva: la reserva sigue siendo del platform-manager.
"""
import asyncio
import copy
import time

import httpx
from fastapi import HTTPException

LEDGER_TTL_S = 90


class Ledger:
    """Compromisos de planes admitidos hace menos de LEDGER_TTL_S, por (proveedor, host)."""

    def __init__(self, ttl=LEDGER_TTL_S, clock=time.monotonic):
        self.ttl, self.clock, self.items = ttl, clock, []

    def add(self, provider, spec):
        now = self.clock()
        for vm in spec["vms"]:
            if vm.get("host"):
                self.items.append((now + self.ttl, provider, vm["host"], vm["vcpus"], vm["memory_mb"], vm["disk_gb"] * 1024))

    def usage(self, provider):
        now = self.clock()
        self.items = [i for i in self.items if i[0] > now]
        out = {}
        for _, p, host, cpu, mem, disk in self.items:
            if p == provider:
                u = out.setdefault(host, [0, 0, 0])
                u[0] += cpu; u[1] += mem; u[2] += disk
        return out


class Planner:
    def __init__(self, monitoring, placement, monitoring_token, placement_token, policy=None):
        self.monitoring, self.placement = monitoring, placement
        self.monitoring_token, self.placement_token = monitoring_token, placement_token
        self.policy = policy or {}
        self.ledger = Ledger()
        self.locks = {"linux": asyncio.Lock(), "openstack": asyncio.Lock()}

    async def _get(self, client, path, token, name):
        try:
            r = await client.get(path, headers={"Authorization": "Bearer " + token})
        except httpx.RequestError:
            raise HTTPException(503, name + "_unavailable") from None
        if r.status_code != 200:
            detail = ""
            try:
                detail = r.json().get("detail", "")
            except ValueError:
                pass
            raise HTTPException(503, ("%s_unavailable: %s" % (name, detail))[:300])
        return r.json()

    async def hosts(self, provider):
        state = await self._get(self.monitoring, "/v1/monitoring/state?provider=" + provider,
                                self.monitoring_token, "monitoring")
        extra = self.ledger.usage(provider)
        hosts = []
        for h in state["hosts"]:
            add = extra.get(h["id"], [0, 0, 0])
            real = h.get("cpu_real_cent")
            hosts.append({"id": h["id"], "zone": h.get("zone"), "cpu_cores": max(1, int(h["cpu_cores"])),
                          "vcpus_max": h.get("vcpus_max"),
                          "ram_mb": h["ram_mb"], "disk_mb": h["disk_mb"],
                          "vcpus_used": h["vcpus_used"] + add[0], "ram_used_mb": h["ram_used_mb"] + add[1],
                          "disk_used_mb": h["disk_used_mb"] + add[2],
                          "cpu_real_cent": None if real is None else real + 100 * add[0],
                          "occupied": bool(h.get("occupied")) or bool(add[0]),
                          "healthy": bool(h.get("healthy")), "age_s": h.get("age_s")})
        return hosts

    async def plan(self, spec, zone=None):
        """Devuelve (spec con host por VM, resumen del plan). 409 con el motivo si no hay plan."""
        provider = spec.get("provider", "linux")
        try:
            vms = [{"id": v["name"], "vcpus": int(v["vcpus"]), "ram_mb": int(v["memory_mb"]),
                    "disk_mb": int(v["disk_gb"]) * 1024, **({"host": v["host"]} if v.get("host") else {})}
                   for v in spec["vms"]]
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "invalid_spec: cada VM necesita name, vcpus, memory_mb y disk_gb") from None
        hosts = await self.hosts(provider)
        body = {"provider": provider, "zone": zone, "hosts": hosts, "vms": vms, "policy": self.policy}
        try:
            r = await self.placement.post("/v1/placements", json=body,
                                          headers={"Authorization": "Bearer " + self.placement_token})
        except httpx.RequestError:
            raise HTTPException(503, "placement_unavailable") from None
        if r.status_code == 422:
            raise HTTPException(422, "invalid_spec: datos de VM no válidos para el placement")
        if r.status_code != 200:
            raise HTTPException(503, "placement_unavailable")
        result = r.json()
        summary = {"status": result["status"], "algorithm": result["algorithm"], "plan": result["plan"],
                   "hosts_opened": result["hosts_opened"], "reason": result["reason"], "zone": zone,
                   "discarded_hosts": result["discarded_hosts"], "elapsed_ms": result["elapsed_ms"]}
        if result["status"] != "PLAN_FOUND":
            raise HTTPException(409, ("Sin recursos para el slice (%s): %s" % (result["status"], result["reason"]))[:500])
        zones = {h["id"]: h["zone"] for h in hosts}
        placed = copy.deepcopy(spec)
        for vm in placed["vms"]:
            vm["host"] = result["plan"][vm["name"]]
            if provider == "openstack":
                vm["zone"] = zones.get(vm["host"]) or "nova"
        return placed, summary

    async def admit(self, spec, zone, submit, attempts=3, wait=2.0):
        """Plan + envío al platform-manager bajo un candado por proveedor; reintenta si la reserva falló por
        capacidad (otro slice ganó el hueco). `submit(spec)` devuelve la respuesta del platform-manager."""
        provider = spec.get("provider", "linux")
        async with self.locks.setdefault(provider, asyncio.Lock()):
            for attempt in range(attempts):
                placed, summary = await self.plan(spec, zone)
                try:
                    job = await submit(placed)
                except HTTPException as exc:
                    if exc.status_code == 409 and "apacidad" in str(exc.detail) and attempt + 1 < attempts:
                        await asyncio.sleep(wait)
                        continue
                    raise
                self.ledger.add(provider, placed)
                summary["attempts"] = attempt + 1
                return job, summary
