"""Slice Manager bootstrap. No provisioning or simulated slice storage."""
from typing import Literal

import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import ValidationError
from pydantic import BaseModel, ConfigDict


class Health(BaseModel):
    service: Literal["slice-manager"] = "slice-manager"
    status: Literal["ok"] = "ok"


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    slice_lifecycle: bool = False
    persistence: bool = False
    iam: bool = True
    queue: bool = False
    linux_r2: bool = False
    openstack: bool = False
    placement: bool = False


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    service: Literal["slice-manager"] = "slice-manager"
    api_version: Literal["v1"] = "v1"
    phase: Literal["bootstrap"] = "bootstrap"
    features: Features


@asynccontextmanager
async def lifespan(app):
    url = os.getenv("IAM_URL", "http://127.0.0.1:8002").rstrip("/")
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}):
        raise ValueError("IAM_URL must be an HTTP(S) origin")
    async with httpx.AsyncClient(base_url=url, timeout=3, trust_env=False, follow_redirects=False) as client:
        app.state.iam = client
        yield


bearer = HTTPBearer(auto_error=False)


async def iam_request(request, method, path, token=None, body=None):
    try:
        response = await request.app.state.iam.request(
            method, path, headers={"Authorization": "Bearer " + token} if token else {}, json=body)
    except httpx.RequestError:
        raise HTTPException(503, "iam_unavailable") from None
    if response.status_code in (401, 403):
        raise HTTPException(response.status_code, "not_authorized",
                            headers={"WWW-Authenticate": "Bearer"} if response.status_code == 401 else {})
    if response.status_code != 200:
        raise HTTPException(503, "iam_unavailable")
    try:
        return response.json()
    except ValueError:
        raise HTTPException(502, "iam_bad_response") from None


class PlatformDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allowed: bool
    action: Literal["platform.read"]
    reason: str


async def authorize_platform(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    data = await iam_request(request, "POST", "/v1/iam/authorize", credentials.credentials,
                             {"action": "platform.read"})
    try:
        decision = PlatformDecision.model_validate(data)
    except ValidationError:
        raise HTTPException(502, "iam_bad_response") from None
    if not decision.allowed:
        raise HTTPException(403, "not_authorized")


app = FastAPI(
    title="G5 Slice Manager", version="0.2.0", lifespan=lifespan,
    description="Base de comunicación. Aún no admite ni ejecuta operaciones de slices.",
)


@app.get("/healthz", response_model=Health, tags=["health"])
def health() -> Health:
    return Health()


@app.get("/readyz", response_model=Health, tags=["health"])
async def ready(request: Request) -> Health:
    data = await iam_request(request, "GET", "/readyz")
    if data != {"service": "iam", "status": "ok"}:
        raise HTTPException(502, "iam_bad_response")
    return Health()


@app.get("/v1/capabilities", response_model=Capabilities, tags=["platform"], dependencies=[Depends(authorize_platform)])
def capabilities() -> Capabilities:
    return Capabilities(features=Features())
