"""VM Placement (R4): servicio sin estado. Recibe el inventario de hosts y las VMs del slice y devuelve
un plan {vm -> host} con BCDP v2, o el rechazo con su motivo. No reserva: la reserva atómica la hace el
platform-manager y, si falla por capacidad, el slice-manager vuelve a pedir un plan.
Solo lo llaman módulos autorizados (token de servicio, R1C-D-06).
"""
import hmac
import os
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .planner import plan as make_plan

ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Health(BaseModel):
    service: Literal["vm-placement"] = "vm-placement"
    status: Literal["ok"] = "ok"


class Host(Model):
    id: str = Field(pattern=ID)
    zone: str | None = Field(default=None, max_length=64)
    cpu_cores: int = Field(ge=1, le=1024, description="CPU físicas del host")
    ram_mb: int = Field(ge=0, description="RAM neta (ya descontada la reserva del host)")
    disk_mb: int = Field(ge=0, description="Disco neto")
    vcpus_used: int = Field(default=0, ge=0, description="vCPU ya comprometidas")
    cpu_real_cent: int | None = Field(default=None, ge=0, description="CPU real en centésimas; null = sin telemetría")
    ram_used_mb: int = Field(default=0, ge=0)
    disk_used_mb: int = Field(default=0, ge=0)
    occupied: bool = Field(default=False, description="Ya aloja VMs de otros slices")
    healthy: bool = True
    age_s: float | None = Field(default=None, ge=0, description="Antigüedad de la telemetría")


class Vm(Model):
    id: str = Field(pattern=ID)
    vcpus: int = Field(ge=1, le=64)
    ram_mb: int = Field(ge=1)
    disk_mb: int = Field(ge=0)
    cpu_cent: int | None = Field(default=None, ge=0, description="CPU prevista; null = demanda completa")
    host: str | None = Field(default=None, pattern=ID, description="Servidor fijado por el usuario")


class Policy(Model):
    cpu_ratio: float = Field(default=2.0, gt=0, le=16)
    cpu_limit: float = Field(default=0.85, gt=0, le=1)
    max_age_s: float = Field(default=15, gt=0)
    timeout_s: float = Field(default=1.0, gt=0, le=10)


class PlacementRequest(Model):
    provider: Literal["linux", "openstack"]
    zone: str | None = Field(default=None, max_length=64)
    hosts: list[Host] = Field(max_length=256)
    vms: list[Vm] = Field(min_length=1, max_length=2000)
    policy: Policy = Policy()

    @model_validator(mode="after")
    def unique(self):
        if len({h.id for h in self.hosts}) != len(self.hosts):
            raise ValueError("ids de host repetidos")
        if len({v.id for v in self.vms}) != len(self.vms):
            raise ValueError("ids de VM repetidos")
        return self


class Discarded(BaseModel):
    host: str
    reason: str


class PlacementResponse(BaseModel):
    status: Literal["PLAN_FOUND", "HEURISTIC_NO_PLAN", "PLANNING_TIMEOUT", "INVALID_OR_ERROR"]
    algorithm: str
    plan: dict[str, str]
    hosts_used: list[str]
    hosts_opened: int = Field(description="Z: hosts que no tenían VMs y quedan ocupados")
    discarded_hosts: list[Discarded]
    reason: str | None
    elapsed_ms: float


def load_tokens():
    path = os.getenv("PLACEMENT_TOKEN_FILE")
    if not path:
        raise RuntimeError("PLACEMENT_TOKEN_FILE es obligatorio")
    tokens = [t.strip() for t in Path(path).read_text(encoding="utf-8").splitlines() if t.strip()]
    if not tokens or any(len(t) < 32 for t in tokens):
        raise RuntimeError("PLACEMENT_TOKEN_FILE debe contener tokens de servicio de al menos 32 caracteres")
    return tokens


bearer = HTTPBearer(auto_error=False)
_tokens = []


def service(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not _tokens:
        _tokens.extend(load_tokens())
    given = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
    if not any(hmac.compare_digest(given, t) for t in _tokens):
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})


app = FastAPI(title="G5 VM Placement", version="0.1.0",
              description="Plan de ubicación de VMs por slice completo (BCDP v2). Sin estado; no reserva.")


@app.get("/healthz", response_model=Health, tags=["health"])
def health() -> Health:
    return Health()


@app.post("/v1/placements", response_model=PlacementResponse, tags=["placement"], dependencies=[Depends(service)])
def placements(body: PlacementRequest) -> PlacementResponse:
    return PlacementResponse(**make_plan(body.model_dump()))
