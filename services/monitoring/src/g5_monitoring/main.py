"""Monitoring (D-13): recolecta cada MONITORING_INTERVAL_S una muestra de telemetría del platform-manager
(agente Linux y API de Nova), la guarda en SQLite durante MONITORING_RETENTION_H y responde el estado actual
y el historial. Lo consultan el slice-manager (token de servicio, para el placement) y la web (usuario vía IAM).
La telemetría no reserva ni confirma recursos.
"""
import asyncio
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .normalize import hosts_from_sample

logger = logging.getLogger("g5.monitoring")


class Health(BaseModel):
    service: Literal["monitoring"] = "monitoring"
    status: Literal["ok"] = "ok"


def origin(name, default):
    url = os.getenv(name, default).rstrip("/")
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}):
        raise ValueError(name + " must be an HTTP(S) origin")
    return url


def read_tokens(path, minimum=32):
    tokens = [t.strip() for t in Path(path).read_text(encoding="utf-8").splitlines() if t.strip()]
    if not tokens or any(len(t) < minimum for t in tokens):
        raise ValueError(str(path) + " debe contener tokens de al menos %d caracteres" % minimum)
    return tokens


class Samples:
    """Muestras completas por instante (JSON), con retención acotada."""

    def __init__(self, path, retention_s):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.lock = threading.Lock()
        self.retention_s = retention_s
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS samples(ts REAL PRIMARY KEY, body TEXT NOT NULL)")

    def add(self, sample):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO samples VALUES(?,?)", (sample["timestamp"], json.dumps(sample)))
            self.db.execute("DELETE FROM samples WHERE ts < ?", (time.time() - self.retention_s,))

    def latest(self):
        with self.lock:
            row = self.db.execute("SELECT body FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def since(self, ts):
        with self.lock:
            rows = self.db.execute("SELECT body FROM samples WHERE ts >= ? ORDER BY ts", (ts,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def close(self):
        self.db.close()


async def collect_once(app):
    """Pide una muestra al platform-manager y la guarda. Devuelve True si se guardó."""
    try:
        response = await app.state.platform.get("/v1/metrics", headers={"Authorization": "Bearer " + app.state.platform_token})
    except httpx.RequestError as exc:
        app.state.last_error = "platform-manager sin respuesta: %s" % type(exc).__name__
        return False
    if response.status_code != 200:
        app.state.last_error = "platform-manager respondió %s" % response.status_code
        return False
    try:
        sample = response.json()
        float(sample["timestamp"])
    except (ValueError, KeyError, TypeError):
        app.state.last_error = "muestra inválida"
        return False
    app.state.samples.add(sample)
    app.state.last_error = None
    return True


async def collector(app, interval):
    while True:
        started = time.monotonic()
        try:
            await collect_once(app)
        except Exception:                                    # el recolector no debe morir
            logger.exception("fallo al recolectar")
        await asyncio.sleep(max(1.0, interval - (time.monotonic() - started)))


@asynccontextmanager
async def lifespan(app):
    app.state.samples = Samples(os.getenv("MONITORING_DB_PATH", "state/monitoring/samples.db"),
                                float(os.getenv("MONITORING_RETENTION_H", "24")) * 3600)
    app.state.service_tokens = read_tokens(os.environ["MONITORING_TOKEN_FILE"])
    app.state.platform_token = read_tokens(os.environ["PLATFORM_TOKEN_FILE"], 16)[0]
    app.state.last_error = "sin muestras todavía"
    interval = float(os.getenv("MONITORING_INTERVAL_S", "10"))
    async with httpx.AsyncClient(base_url=origin("PLATFORM_MANAGER_URL", "http://127.0.0.1:8001"), timeout=45,
                                 trust_env=False, follow_redirects=False) as platform, \
            httpx.AsyncClient(base_url=origin("IAM_URL", "http://127.0.0.1:8002"), timeout=3,
                              trust_env=False, follow_redirects=False) as iam:
        app.state.platform, app.state.iam = platform, iam
        task = asyncio.create_task(collector(app, interval)) if interval > 0 else None
        try:
            yield
        finally:
            if task:
                task.cancel()
            app.state.samples.close()


bearer = HTTPBearer(auto_error=False)


async def reader(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """Token de servicio (slice-manager) o usuario activo validado por IAM (web)."""
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    given = credentials.credentials
    if any(hmac.compare_digest(given, t) for t in request.app.state.service_tokens):
        return "service"
    try:
        response = await request.app.state.iam.get("/v1/auth/me", headers={"Authorization": "Bearer " + given})
    except httpx.RequestError:
        raise HTTPException(503, "iam_unavailable") from None
    if response.status_code == 401:
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    if response.status_code != 200:
        raise HTTPException(503, "iam_unavailable")
    user = response.json()
    if not user.get("active"):
        raise HTTPException(403, "not_authorized")
    return user.get("role", "student")


app = FastAPI(title="G5 Monitoring", version="0.1.0", lifespan=lifespan,
              description="Estado actual e historial de los servidores Linux y OpenStack (D-13).")


@app.get("/healthz", response_model=Health, tags=["health"])
def health() -> Health:
    return Health()


@app.get("/v1/monitoring/state", tags=["monitoring"])
def state(request: Request, provider: Literal["linux", "openstack"] | None = None, who=Depends(reader)):
    sample = request.app.state.samples.latest()
    if sample is None:
        raise HTTPException(503, "Monitoreo sin muestras: " + (request.app.state.last_error or ""))
    now = time.time()
    data = hosts_from_sample(sample, now)
    hosts = data["linux"] + data["openstack"]
    if provider:
        hosts = [h for h in hosts if h["provider"] == provider]
    if who not in ("service", "admin"):            # solo el administrador ve el detalle por VM
        hosts = [dict(h, vm_usage=[]) for h in hosts]
    return {"collected_at": sample["timestamp"], "age_s": round(now - sample["timestamp"], 1),
            "collector_error": request.app.state.last_error, "openstack_error": data["openstack_error"],
            "hosts": hosts}


@app.get("/v1/monitoring/history", tags=["monitoring"])
def history(request: Request, host: str = Query(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"),
            minutes: int = Query(default=60, ge=1, le=1440), who=Depends(reader)):
    points = []
    for sample in request.app.state.samples.since(time.time() - minutes * 60):
        data = hosts_from_sample(sample, sample["timestamp"])
        h = next((x for x in data["linux"] + data["openstack"] if x["id"] == host), None)
        if h:
            points.append({"t": sample["timestamp"], "cpu_real_cent": h["cpu_real_cent"],
                           "vcpus_used": h["vcpus_used"], "ram_used_mb": h["ram_used_mb"],
                           "memory_available_mb": h["memory_available_mb"], "disk_used_mb": h["disk_used_mb"],
                           "vms": h["vms"],
                           # OpenStack: CPU medida de las VMs de G5 (diagnósticos de Nova) y carga del compute
                           "vms_cpu_cent": sum(v.get("cpu_cent") or 0 for v in h.get("vm_usage") or []),
                           "load1": (h.get("load") or [None])[0]})
    if not points:
        raise HTTPException(404, "Sin datos para " + host)
    return {"host": host, "minutes": minutes, "points": points}
