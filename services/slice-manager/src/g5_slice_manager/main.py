"""Slice Manager: intención del usuario, autorización con IAM y delegación al platform-manager.

Flujo (D-12): el usuario llama con su token; IAM dice quién es y si puede crear en el curso;
el Slice Manager llama al platform-manager con un token de servicio propio y guarda la relación
slice → dueño/curso. El platform-manager ejecuta y conserva el estado real del slice.
"""
import hashlib
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, ValidationError


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


class SliceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    spec: dict[str, Any] = Field(description="Especificación del slice (formato del platform-manager)")


class Accepted(BaseModel):
    slice_id: str
    operation_id: str
    status: str


class SliceView(BaseModel):
    id: str
    name: str | None
    provider: str
    status: str
    course_id: str
    owner_id: str
    owner: str
    created_at: float


class SliceEvent(BaseModel):
    seq: int
    event: str | None = None
    detail: str | None = None
    timestamp: float | None = None


class VmView(BaseModel):
    name: str
    image: str | None = None
    vcpus: int | None = None
    memory_mb: int | None = None
    disk_gb: int | None = None
    networks: list[str] = []


class SliceDetail(SliceView):
    vms: list[VmView] = []
    events: list[SliceEvent]


class Console(BaseModel):
    url: str
    provider: str
    vm: str


class UserView(BaseModel):
    id: str
    username: str
    role: Literal["admin", "professor", "student"]
    active: bool


def origin(name, default):
    url = os.getenv(name, default).rstrip("/")
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}):
        raise ValueError(name + " must be an HTTP(S) origin")
    return url


class Registry:
    """Relación slice → dueño/curso. Fuente de verdad del Slice Manager (no del estado de ejecución)."""

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS slices(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            owner TEXT NOT NULL, course_id TEXT NOT NULL, name TEXT, provider TEXT NOT NULL, created_at REAL NOT NULL)""")

    def add(self, sid, user, course_id, spec):
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO slices VALUES(?,?,?,?,?,?,?)",
                            (sid, user.id, user.username, course_id, spec.get("name"),
                             spec.get("provider", "linux"), time.time()))

    def get(self, sid):
        with self.lock:
            row = self.db.execute("SELECT * FROM slices WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None

    def visible(self, user):
        with self.lock:
            if user.role == "admin":
                rows = self.db.execute("SELECT * FROM slices ORDER BY created_at").fetchall()
            else:
                rows = self.db.execute("SELECT * FROM slices WHERE owner_id=? ORDER BY created_at", (user.id,)).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.db.close()


@asynccontextmanager
async def lifespan(app):
    iam_url = origin("IAM_URL", "http://127.0.0.1:8002")
    platform_url = os.getenv("PLATFORM_MANAGER_URL")
    app.state.platform_token = None
    app.state.registry = None
    if platform_url:
        platform_url = origin("PLATFORM_MANAGER_URL", platform_url)
        token_file = Path(os.environ["PLATFORM_TOKEN_FILE"])
        app.state.platform_token = token_file.read_text(encoding="utf-8").strip()
        if len(app.state.platform_token) < 32:
            raise ValueError("PLATFORM_TOKEN_FILE debe contener un token de servicio")
        app.state.registry = Registry(os.getenv("SLICE_DB_PATH", "state/slice/slices.db"))
    timeout = float(os.getenv("PLATFORM_TIMEOUT_SECONDS", "20"))
    async with httpx.AsyncClient(base_url=iam_url, timeout=3, trust_env=False, follow_redirects=False) as iam, \
            httpx.AsyncClient(base_url=platform_url or "http://platform.invalid", timeout=timeout,
                              trust_env=False, follow_redirects=False) as platform:
        app.state.iam = iam
        app.state.platform = platform if platform_url else None
        try:
            yield
        finally:
            if app.state.registry:
                app.state.registry.close()


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


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allowed: bool
    action: str
    reason: str


def credentials_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


async def allowed(request, token, action, **scope):
    data = await iam_request(request, "POST", "/v1/iam/authorize", token, {"action": action, **scope})
    try:
        decision = Decision.model_validate(data)
    except ValidationError:
        raise HTTPException(502, "iam_bad_response") from None
    if decision.action != action:
        raise HTTPException(502, "iam_bad_response")
    return decision.allowed


async def authorize_platform(request: Request, token=Depends(credentials_token)):
    if not await allowed(request, token, "platform.read"):
        raise HTTPException(403, "not_authorized")


async def current_user(request: Request, token=Depends(credentials_token)) -> UserView:
    data = await iam_request(request, "GET", "/v1/auth/me", token)
    try:
        user = UserView.model_validate(data)
    except ValidationError:
        raise HTTPException(502, "iam_bad_response") from None
    if not user.active:
        raise HTTPException(403, "not_authorized")
    return user


def platform_ready(request):
    if request.app.state.platform is None:
        raise HTTPException(503, "platform_unavailable")
    return request.app.state.platform, request.app.state.registry


async def platform_call(request, method, path, body=None, key=None):
    client, _ = platform_ready(request)
    headers = {"Authorization": "Bearer " + request.app.state.platform_token}
    if key:
        headers["Idempotency-Key"] = key
    try:
        response = await client.request(method, path, headers=headers, json=body)
    except httpx.TimeoutException:
        raise HTTPException(504, "platform_timeout") from None
    except httpx.RequestError:
        raise HTTPException(503, "platform_unavailable") from None
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(502, "platform_bad_response") from None
    if response.status_code in (200, 201, 202):
        return data
    message = data.get("error") if isinstance(data, dict) else None
    if response.status_code == 400:
        raise HTTPException(422, "invalid_spec: " + str(message)[:300])
    if response.status_code in (409, 413):
        raise HTTPException(response.status_code, str(message)[:300] or "conflict")
    if response.status_code == 404:
        raise HTTPException(404, "not_found")
    if response.status_code in (401, 403):
        # Error de configuración del token de servicio: no es culpa del usuario.
        raise HTTPException(502, "platform_auth_error")
    raise HTTPException(503, "platform_unavailable")


def platform_key(user, key):
    # El platform-manager ve un único dueño (el servicio): se separan las claves por usuario.
    return hashlib.sha256((user.id + ":" + key).encode()).hexdigest()


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64,
                                       pattern=r"^[A-Za-z0-9_-]+$")]
SliceId = Annotated[str, PathParam(pattern=r"^[0-9a-f]{32}$")]
VmName = Annotated[str, PathParam(pattern=r"^[a-z][a-z0-9-]{0,31}$")]


def owned(registry, sid, user):
    row = registry.get(sid)
    # 404 también para slices ajenos: no se revela su existencia.
    if not row or (user.role != "admin" and row["owner_id"] != user.id):
        raise HTTPException(404, "not_found")
    return row


def view(row, status):
    return SliceView(id=row["id"], name=row["name"], provider=row["provider"], status=status,
                     course_id=row["course_id"], owner_id=row["owner_id"], owner=row["owner"],
                     created_at=row["created_at"])


app = FastAPI(
    title="G5 Slice Manager", version="0.3.0", lifespan=lifespan,
    description="Intención y autorización de slices; delega la ejecución en el platform-manager.",
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
def capabilities(request: Request) -> Capabilities:
    on = request.app.state.platform is not None
    return Capabilities(features=Features(slice_lifecycle=on, persistence=on, queue=on, openstack=on, linux_r2=on))


@app.post("/v1/slices", response_model=Accepted, status_code=202, tags=["slices"])
async def create_slice(body: SliceCreate, request: Request, key: IdempotencyKey,
                       token=Depends(credentials_token), user: UserView = Depends(current_user)) -> Accepted:
    platform_ready(request)
    if not await allowed(request, token, "slice.create", course_id=body.course_id):
        raise HTTPException(403, "not_authorized")
    job = await platform_call(request, "POST", "/v1/slices", body.spec, platform_key(user, key))
    try:
        accepted = Accepted(slice_id=job["slice_id"], operation_id=job["id"], status=job["status"])
    except (KeyError, TypeError, ValidationError):
        raise HTTPException(502, "platform_bad_response") from None
    request.app.state.registry.add(accepted.slice_id, user, body.course_id, body.spec)
    return accepted


@app.get("/v1/slices", response_model=list[SliceView], tags=["slices"])
async def list_slices(request: Request, user: UserView = Depends(current_user)) -> list[SliceView]:
    _, registry = platform_ready(request)
    rows = registry.visible(user)
    if not rows:
        return []
    states = {s["id"]: s["status"] for s in await platform_call(request, "GET", "/v1/slices")}
    return [view(r, states.get(r["id"], "UNKNOWN")) for r in rows]


@app.get("/v1/slices/{slice_id}", response_model=SliceDetail, tags=["slices"])
async def get_slice(slice_id: SliceId, request: Request, user: UserView = Depends(current_user)) -> SliceDetail:
    _, registry = platform_ready(request)
    row = owned(registry, slice_id, user)
    state = await platform_call(request, "GET", "/v1/slices/" + slice_id)
    events = await platform_call(request, "GET", "/v1/slices/%s/events" % slice_id)
    recent = [SliceEvent(**{k: e.get(k) for k in ("seq", "event", "detail", "timestamp")})
              for e in reversed(events[:50])] if isinstance(events, list) else []
    spec = state.get("spec") if isinstance(state.get("spec"), dict) else {}
    vms = [VmView(name=v["name"], image=v.get("image"), vcpus=v.get("vcpus"), memory_mb=v.get("memory_mb"),
                  disk_gb=v.get("disk_gb"), networks=[n.get("network") for n in v.get("nics", []) if n.get("network")])
           for v in spec.get("vms", []) if isinstance(v, dict) and v.get("name")]
    return SliceDetail(**view(row, state.get("status", "UNKNOWN")).model_dump(), vms=vms, events=recent)


@app.delete("/v1/slices/{slice_id}", response_model=Accepted, status_code=202, tags=["slices"])
async def delete_slice(slice_id: SliceId, request: Request, key: IdempotencyKey,
                       user: UserView = Depends(current_user)) -> Accepted:
    _, registry = platform_ready(request)
    owned(registry, slice_id, user)
    job = await platform_call(request, "DELETE", "/v1/slices/" + slice_id, key=platform_key(user, key))
    try:
        return Accepted(slice_id=slice_id, operation_id=job["id"], status=job["status"])
    except (KeyError, TypeError, ValidationError):
        raise HTTPException(502, "platform_bad_response") from None


@app.post("/v1/slices/{slice_id}/vms/{vm}/console", response_model=Console, tags=["slices"])
async def vm_console(slice_id: SliceId, vm: VmName, request: Request, user: UserView = Depends(current_user)) -> Console:
    """URL de consola (noVNC con token de Nova, de vida corta). Solo dueño o admin, como el resto del slice."""
    _, registry = platform_ready(request)
    owned(registry, slice_id, user)
    data = await platform_call(request, "POST", "/v1/slices/%s/vms/%s/console" % (slice_id, vm), {})
    url = data.get("url") if isinstance(data, dict) else None
    if not isinstance(url, str) or not url:
        raise HTTPException(502, "platform_bad_response")
    return Console(url=url, provider=data.get("provider", "unknown"), vm=vm)
