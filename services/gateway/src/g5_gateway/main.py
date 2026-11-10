"""Gateway: own process, HTTP-only communication with Slice Manager."""
import logging
import math
import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from .auth import router, platform_access, iam_call, token
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger("g5.gateway")


class Health(BaseModel):
    service: Literal["gateway"] = "gateway"
    status: Literal["ok"] = "ok"


class UpstreamHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    service: Literal["slice-manager"]
    status: Literal["ok"]


class Readiness(Health):
    dependencies: dict[str, Literal["ok"]]


# Local representation of the HTTP contract; no imports from Slice Manager.
class Features(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    slice_lifecycle: bool
    persistence: bool
    iam: bool
    queue: bool
    linux_r2: bool
    openstack: bool
    placement: bool


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    service: Literal["slice-manager"]
    api_version: Literal["v1"]
    phase: Literal["bootstrap"]
    features: Features


ERROR_RESPONSES = {
    502: {"description": "Respuesta inválida o error del Slice Manager"},
    503: {"description": "Slice Manager no disponible"},
    504: {"description": "Slice Manager excedió el tiempo límite"},
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("SLICE_MANAGER_URL", "http://127.0.0.1:8001").rstrip("/")
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in {"", "/"}):
        raise ValueError("SLICE_MANAGER_URL debe ser un origen HTTP(S) sin credenciales ni ruta")
    timeout = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "3"))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("UPSTREAM_TIMEOUT_SECONDS debe ser positivo y finito")
    iam_url = os.getenv("IAM_URL", "http://127.0.0.1:8002").rstrip("/")
    iam_parts = urlsplit(iam_url)
    if (iam_parts.scheme not in {"http", "https"} or not iam_parts.hostname
            or iam_parts.username or iam_parts.password or iam_parts.query or iam_parts.fragment
            or iam_parts.path not in {"", "/"}):
        raise ValueError("IAM_URL must be an HTTP(S) origin")
    async with httpx.AsyncClient(
        base_url=url, timeout=httpx.Timeout(timeout), trust_env=False,
        follow_redirects=False,
    ) as client:
        app.state.slice_manager = client
        async with httpx.AsyncClient(base_url=iam_url, timeout=timeout, trust_env=False,
                                     follow_redirects=False) as iam:
            app.state.iam = iam
            # Topology Manager (paso 6): opcional; sin él, sus rutas responden 503.
            topo_url = os.getenv("TOPOLOGY_MANAGER_URL")
            if topo_url:
                topo_url = topo_url.rstrip("/")
                tp = urlsplit(topo_url)
                if (tp.scheme not in {"http", "https"} or not tp.hostname or tp.username or tp.password
                        or tp.query or tp.fragment or tp.path not in {"", "/"}):
                    raise ValueError("TOPOLOGY_MANAGER_URL must be an HTTP(S) origin")
            image_url = os.getenv("IMAGE_CATALOG_URL")
            if image_url:
                image_url = image_url.rstrip("/")
                ip = urlsplit(image_url)
                if (ip.scheme not in {"http", "https"} or not ip.hostname or ip.username or ip.password
                        or ip.query or ip.fragment or ip.path not in {"", "/"}):
                    raise ValueError("IMAGE_CATALOG_URL must be an HTTP(S) origin")
            async with httpx.AsyncClient(base_url=topo_url or "http://topology.invalid", timeout=timeout,
                                         trust_env=False, follow_redirects=False) as topology, \
                    httpx.AsyncClient(base_url=image_url or "http://images.invalid", timeout=timeout,
                                      trust_env=False, follow_redirects=False) as images:
                app.state.topology_manager = topology if topo_url else None
                app.state.image_catalog = images if image_url else None
                yield


app = FastAPI(
    title="G5 API Gateway", version="0.2.0", lifespan=lifespan,
    description="Gateway con autenticación y autorización delegadas a IAM.",
)


async def fetch(request: Request, path: str, model: type[BaseModel], access_token=None) -> BaseModel:
    try:
        response = await request.app.state.slice_manager.get(path, headers={"Authorization": "Bearer " + access_token} if access_token else {})
        if response.status_code in (401, 403):
            raise HTTPException(response.status_code, "not_authorized",
                                headers={"WWW-Authenticate": "Bearer"} if response.status_code == 401 else {})
        if response.status_code == 503:
            raise HTTPException(503, "slice_manager_unavailable")
        if response.status_code != 200:
            logger.warning("slice_manager returned status=%s", response.status_code)
            raise HTTPException(502, "slice_manager_bad_response")
        return model.model_validate(response.json())
    except httpx.TimeoutException:
        raise HTTPException(504, "slice_manager_timeout") from None
    except httpx.RequestError:
        raise HTTPException(503, "slice_manager_unavailable") from None
    except (ValueError, ValidationError):
        raise HTTPException(502, "slice_manager_bad_response") from None


@app.get("/healthz", response_model=Health, tags=["health"])
def health() -> Health:
    # Process liveness does not claim dependency readiness.
    return Health()


@app.get("/readyz", response_model=Readiness, tags=["health"], responses=ERROR_RESPONSES)
async def ready(request: Request) -> Readiness:
    await fetch(request, "/readyz", UpstreamHealth)
    iam_health = await iam_call(request, "GET", "/readyz")
    if iam_health != {"service": "iam", "status": "ok"}:
        raise HTTPException(502, "iam_bad_response")
    return Readiness(dependencies={"slice-manager": "ok", "iam": "ok"})


@app.get("/v1/platform/capabilities", response_model=Capabilities,
         tags=["platform"], responses=ERROR_RESPONSES)
async def capabilities(request: Request, access_token=Depends(platform_access)) -> BaseModel:
    return await fetch(request, "/v1/capabilities", Capabilities, access_token)


app.include_router(router)


# --- Slices (D-12): rutas explícitas hacia el Slice Manager; la autorización la decide él con IAM.
SliceId = Annotated[str, PathParam(pattern=r"^[0-9a-f]{32}$")]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64,
                                       pattern=r"^[A-Za-z0-9_-]+$")]
SLICE_STATUSES = {200, 202, 401, 403, 404, 409, 413, 422, 502, 503, 504}


class SliceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    spec: dict[str, Any]


async def upstream_call(client, name: str, method: str, path: str, access_token: str, body=None, key=None):
    """Reenvío explícito a un servicio interno: token del usuario, cuerpo JSON y errores con detalle legible."""
    if client is None:
        raise HTTPException(503, name + "_unavailable")
    headers = {"Authorization": "Bearer " + access_token}
    if key:
        headers["Idempotency-Key"] = key
    timeout = float(os.getenv("SLICE_TIMEOUT_SECONDS", "30"))
    try:
        response = await client.request(method, path, headers=headers, json=body, timeout=timeout)
    except httpx.TimeoutException:
        raise HTTPException(504, name + "_timeout") from None
    except httpx.RequestError:
        raise HTTPException(503, name + "_unavailable") from None
    if response.status_code not in SLICE_STATUSES | {201, 204}:
        logger.warning("%s returned status=%s", name, response.status_code)
        raise HTTPException(502, name + "_bad_response")
    if response.status_code == 204:
        return Response(status_code=204)
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(502, name + "_bad_response") from None
    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        headers = {"WWW-Authenticate": "Bearer"} if response.status_code == 401 else {}
        raise HTTPException(response.status_code, detail if isinstance(detail, str) else name + "_error",
                            headers=headers)
    return JSONResponse(status_code=response.status_code, content=data)


async def slice_call(request: Request, method: str, path: str, access_token: str, body=None, key=None):
    return await upstream_call(request.app.state.slice_manager, "slice_manager", method, path, access_token, body, key)


async def topology_call(request: Request, method: str, path: str, access_token: str, body=None):
    return await upstream_call(request.app.state.topology_manager, "topology_manager", method, path, access_token, body)


@app.post("/v1/slices", status_code=202, tags=["slices"], responses=ERROR_RESPONSES)
async def create_slice(body: SliceCreate, request: Request, key: IdempotencyKey, access_token=Depends(token)):
    return await slice_call(request, "POST", "/v1/slices", access_token, body.model_dump(), key)


@app.get("/v1/slices", tags=["slices"], responses=ERROR_RESPONSES)
async def list_slices(request: Request, access_token=Depends(token)):
    return await slice_call(request, "GET", "/v1/slices", access_token)


@app.get("/v1/slices/{slice_id}", tags=["slices"], responses=ERROR_RESPONSES)
async def get_slice(slice_id: SliceId, request: Request, access_token=Depends(token)):
    return await slice_call(request, "GET", "/v1/slices/" + slice_id, access_token)


@app.delete("/v1/slices/{slice_id}", status_code=202, tags=["slices"], responses=ERROR_RESPONSES)
async def delete_slice(slice_id: SliceId, request: Request, key: IdempotencyKey, access_token=Depends(token)):
    return await slice_call(request, "DELETE", "/v1/slices/" + slice_id, access_token, key=key)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]} for e in exc.errors()
    ]})


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response



VmName = Annotated[str, PathParam(pattern=r"^[a-z][a-z0-9-]{0,31}$")]


@app.post("/v1/slices/{slice_id}/vms/{vm}/console", tags=["slices"], responses=ERROR_RESPONSES)
async def vm_console(slice_id: SliceId, vm: VmName, request: Request, access_token=Depends(token)):
    return await slice_call(request, "POST", "/v1/slices/%s/vms/%s/console" % (slice_id, vm), access_token)


UserId = Annotated[str, PathParam(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]


class AssignmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


@app.get("/v1/slices/{slice_id}/assignments", tags=["slices"], responses=ERROR_RESPONSES)
async def slice_assignments(slice_id: SliceId, request: Request, access_token=Depends(token)):
    return await slice_call(request, "GET", f"/v1/slices/{slice_id}/assignments", access_token)


@app.post("/v1/slices/{slice_id}/assignments", tags=["slices"], responses=ERROR_RESPONSES)
async def assign_slice(slice_id: SliceId, body: AssignmentBody, request: Request, access_token=Depends(token)):
    return await slice_call(request, "POST", f"/v1/slices/{slice_id}/assignments", access_token, body.model_dump())


@app.delete("/v1/slices/{slice_id}/assignments/{user_id}", tags=["slices"], responses=ERROR_RESPONSES)
async def unassign_slice(slice_id: SliceId, user_id: UserId, request: Request, access_token=Depends(token)):
    return await slice_call(request, "DELETE", f"/v1/slices/{slice_id}/assignments/{user_id}", access_token)

# --- Topologías y borradores (paso 6): rutas explícitas hacia el Topology Manager, dueño del documento.
DraftId = Annotated[str, PathParam(pattern=r"^[0-9a-f]{32}$")]
JsonBody = Annotated[dict[str, Any], Body()]


@app.get("/v1/topologies/catalog", tags=["topologies"], responses=ERROR_RESPONSES)
async def topology_catalog(request: Request, access_token=Depends(token)):
    return await topology_call(request, "GET", "/v1/topologies/catalog", access_token)


@app.post("/v1/topologies/{operation}", tags=["topologies"], responses=ERROR_RESPONSES)
async def topology_operation(operation: Literal["generate", "combine", "validate", "compile"], body: JsonBody,
                             request: Request, access_token=Depends(token)):
    return await topology_call(request, "POST", "/v1/topologies/" + operation, access_token, body)


@app.get("/v1/drafts", tags=["drafts"], responses=ERROR_RESPONSES)
async def list_drafts(request: Request, access_token=Depends(token)):
    return await topology_call(request, "GET", "/v1/drafts", access_token)


@app.post("/v1/drafts", status_code=201, tags=["drafts"], responses=ERROR_RESPONSES)
async def create_draft(body: JsonBody, request: Request, access_token=Depends(token)):
    return await topology_call(request, "POST", "/v1/drafts", access_token, body)


@app.get("/v1/drafts/{draft_id}", tags=["drafts"], responses=ERROR_RESPONSES)
async def get_draft(draft_id: DraftId, request: Request, access_token=Depends(token)):
    return await topology_call(request, "GET", "/v1/drafts/" + draft_id, access_token)


@app.put("/v1/drafts/{draft_id}", tags=["drafts"], responses=ERROR_RESPONSES)
async def update_draft(draft_id: DraftId, body: JsonBody, request: Request, access_token=Depends(token)):
    return await topology_call(request, "PUT", "/v1/drafts/" + draft_id, access_token, body)


@app.delete("/v1/drafts/{draft_id}", tags=["drafts"], responses=ERROR_RESPONSES)
async def delete_draft(draft_id: DraftId, request: Request, access_token=Depends(token)):
    return await topology_call(request, "DELETE", "/v1/drafts/" + draft_id, access_token)



# --- Imágenes (D-15): rutas explícitas hacia el Image Catalog. La importación se reenvía en streaming.
@app.get("/v1/images", tags=["images"], responses=ERROR_RESPONSES)
async def list_images(request: Request, access_token=Depends(token)):
    return await upstream_call(request.app.state.image_catalog, "image_catalog", "GET", "/v1/images", access_token)


@app.post("/v1/images", status_code=201, tags=["images"], responses=ERROR_RESPONSES)
async def import_image(request: Request, name: str, disk_format: Literal["qcow2", "raw"] = "qcow2",
                       description: str = "", access_token=Depends(token)):
    client = request.app.state.image_catalog
    if client is None:
        raise HTTPException(503, "image_catalog_unavailable")
    length = request.headers.get("content-length")
    if not length or not length.isdigit():
        raise HTTPException(411, "Se requiere Content-Length")

    async def body():
        async for chunk in request.stream():
            yield chunk

    try:
        response = await client.post("/v1/images", params={"name": name, "disk_format": disk_format, "description": description},
                                     content=body(), headers={"Authorization": "Bearer " + access_token,
                                                              "Content-Length": length,
                                                              "Content-Type": "application/octet-stream"},
                                     timeout=httpx.Timeout(900, connect=10))
    except httpx.TimeoutException:
        raise HTTPException(504, "image_catalog_timeout") from None
    except httpx.RequestError:
        raise HTTPException(503, "image_catalog_unavailable") from None
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(502, "image_catalog_bad_response") from None
    if response.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        raise HTTPException(response.status_code if response.status_code in SLICE_STATUSES | {411} else 502,
                            detail if isinstance(detail, str) else "image_catalog_error",
                            headers={"WWW-Authenticate": "Bearer"} if response.status_code == 401 else {})
    return JSONResponse(status_code=response.status_code, content=data)
