"""Topology Manager: topologías predefinidas, combinación, borradores versionados, importar/exportar y
compilación a la especificación del platform-manager. No despliega: eso lo hace el slice-manager.
"""
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .compiler import PROVIDERS, CompileError, compile_spec
from .generators import GENERATORS, combine, generate
from .model import IDENT, Topology, images, sizes


class Health(BaseModel):
    service: Literal["topology-manager"] = "topology-manager"
    status: Literal["ok"] = "ok"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateRequest(Model):
    kind: str = Field(max_length=32)
    n: int = Field(ge=1, le=64)
    name: str | None = Field(default=None, pattern=IDENT)
    prefix: str = Field(default="n", pattern=r"^[a-z][a-z0-9]{0,8}$")
    image: str = "cirros"
    size: str = "small"


class CombineRequest(Model):
    base: Topology
    add: Topology
    connect: tuple[str, str] | None = Field(default=None, description="(nodo de base, nodo de add) a enlazar")


class CompileRequest(Model):
    topology: Topology
    provider: Literal["openstack", "linux"] = "openstack"
    name: str | None = Field(default=None, pattern=IDENT)


class DraftWrite(Model):
    topology: Topology


class DraftUpdate(Model):
    topology: Topology
    version: int = Field(ge=1)


class DraftSummary(BaseModel):
    id: str
    name: str
    version: int
    nodes: int
    segments: int
    updated_at: float


class Draft(DraftSummary):
    topology: Topology


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


class Drafts:
    """Borradores por dueño con control de versión optimista (409 si la versión quedó obsoleta)."""

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            name TEXT NOT NULL, version INTEGER NOT NULL, document TEXT NOT NULL, created_at REAL, updated_at REAL)""")

    @staticmethod
    def summary(row):
        doc = json.loads(row["document"])
        return dict(id=row["id"], name=row["name"], version=row["version"], nodes=len(doc["nodes"]),
                    segments=len(doc.get("segments", [])), updated_at=row["updated_at"])

    def list(self, owner):
        with self.lock:
            rows = self.db.execute("SELECT * FROM drafts WHERE owner_id=? ORDER BY updated_at DESC", (owner,)).fetchall()
        return [self.summary(r) for r in rows]

    def get(self, owner, did):
        with self.lock:
            row = self.db.execute("SELECT * FROM drafts WHERE id=? AND owner_id=?", (did, owner)).fetchone()
        if not row:
            raise HTTPException(404, "not_found")
        return dict(self.summary(row), topology=json.loads(row["document"]))

    def create(self, owner, topology):
        did, now = uuid.uuid4().hex, time.time()
        with self.lock:
            self.db.execute("INSERT INTO drafts VALUES(?,?,?,?,?,?,?)",
                            (did, owner, topology.name, 1, topology.model_dump_json(), now, now))
        return self.get(owner, did)

    def update(self, owner, did, topology, version):
        with self.lock:
            cur = self.db.execute("UPDATE drafts SET name=?, version=version+1, document=?, updated_at=? "
                                  "WHERE id=? AND owner_id=? AND version=?",
                                  (topology.name, topology.model_dump_json(), time.time(), did, owner, version))
            exists = self.db.execute("SELECT 1 FROM drafts WHERE id=? AND owner_id=?", (did, owner)).fetchone()
        if not exists:
            raise HTTPException(404, "not_found")
        if cur.rowcount == 0:
            raise HTTPException(409, "Otra pestaña o persona guardó una versión más nueva; recarga el borrador")
        return self.get(owner, did)

    def delete(self, owner, did):
        with self.lock:
            cur = self.db.execute("DELETE FROM drafts WHERE id=? AND owner_id=?", (did, owner))
        if cur.rowcount == 0:
            raise HTTPException(404, "not_found")

    def close(self):
        self.db.close()


@asynccontextmanager
async def lifespan(app):
    app.state.drafts = Drafts(os.getenv("TOPOLOGY_DB_PATH", "state/topology/drafts.db"))
    async with httpx.AsyncClient(base_url=origin("IAM_URL", "http://127.0.0.1:8002"), timeout=3,
                                 trust_env=False, follow_redirects=False) as iam:
        app.state.iam = iam
        try:
            yield
        finally:
            app.state.drafts.close()


bearer = HTTPBearer(auto_error=False)


async def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UserView:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        response = await request.app.state.iam.get("/v1/auth/me", headers={"Authorization": "Bearer " + credentials.credentials})
    except httpx.RequestError:
        raise HTTPException(503, "iam_unavailable") from None
    if response.status_code == 401:
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    if response.status_code != 200:
        raise HTTPException(503, "iam_unavailable")
    try:
        user = UserView.model_validate(response.json())
    except (ValueError, ValidationError):
        raise HTTPException(502, "iam_bad_response") from None
    if not user.active:
        raise HTTPException(403, "not_authorized")
    return user


def unprocessable(message):
    return HTTPException(422, str(message)[:500])


DraftId = Annotated[str, PathParam(pattern=r"^[0-9a-f]{32}$")]
User = Annotated[UserView, Depends(current_user)]

app = FastAPI(title="G5 Topology Manager", version="0.1.0", lifespan=lifespan,
              description="Topologías predefinidas, borradores e importar/exportar; compila a la spec del platform-manager.")


@app.exception_handler(RequestValidationError)
async def readable_validation_error(request, exc):
    # Mensajes legibles para la web (import de JSON, edición): "campo: motivo; ...".
    parts = []
    for error in exc.errors()[:6]:
        where = ".".join(str(x) for x in error["loc"] if x not in ("body", "topology"))
        message = error["msg"].removeprefix("Value error, ")
        parts.append(f"{where}: {message}" if where else message)
    return JSONResponse(status_code=422, content={"detail": "Topología inválida: " + "; ".join(parts)})


@app.get("/healthz", response_model=Health, tags=["health"])
def health() -> Health:
    return Health()


@app.get("/v1/topologies/catalog", tags=["topologies"])
def catalog(user: User):
    return {"generators": [dict(id=k, **v) for k, v in GENERATORS.items()], "sizes": sizes(),
            "images": images(), "providers": list(PROVIDERS), "schema_version": 1}


@app.post("/v1/topologies/generate", response_model=Topology, tags=["topologies"])
def generate_topology(body: GenerateRequest, user: User) -> Topology:
    if body.size not in {s["id"] for s in sizes()} or body.image not in images():
        raise unprocessable("Tamaño o imagen no disponibles")
    try:
        return generate(body.kind, body.n, body.name, body.prefix, body.image, body.size)
    except (ValueError, ValidationError) as exc:
        raise unprocessable(exc) from None


@app.post("/v1/topologies/combine", response_model=Topology, tags=["topologies"])
def combine_topologies(body: CombineRequest, user: User) -> Topology:
    if body.connect:
        if body.connect[0] not in {n.id for n in body.base.nodes} or body.connect[1] not in {n.id for n in body.add.nodes}:
            raise unprocessable("Los nodos a enlazar deben existir en cada topología")
    try:
        return combine(body.base, body.add, body.connect)
    except (ValueError, ValidationError) as exc:
        raise unprocessable(exc) from None


@app.post("/v1/topologies/validate", tags=["topologies"])
def validate_topology(body: DraftWrite, user: User):
    """Para importar: el esquema ya se validó al leer el cuerpo; aquí se revisa además el catálogo."""
    problems = body.topology.check_catalog()
    return {"valid": not problems, "problems": problems, "nodes": len(body.topology.nodes),
            "segments": len(body.topology.segments)}


@app.post("/v1/topologies/compile", tags=["topologies"])
def compile_topology(body: CompileRequest, user: User):
    try:
        return compile_spec(body.topology, body.provider, body.name)
    except CompileError as exc:
        raise unprocessable(exc) from None


@app.get("/v1/drafts", response_model=list[DraftSummary], tags=["drafts"])
def list_drafts(request: Request, user: User):
    return request.app.state.drafts.list(user.id)


@app.post("/v1/drafts", response_model=Draft, status_code=201, tags=["drafts"])
def create_draft(body: DraftWrite, request: Request, user: User):
    return request.app.state.drafts.create(user.id, body.topology)


@app.get("/v1/drafts/{draft_id}", response_model=Draft, tags=["drafts"])
def get_draft(draft_id: DraftId, request: Request, user: User):
    return request.app.state.drafts.get(user.id, draft_id)


@app.put("/v1/drafts/{draft_id}", response_model=Draft, tags=["drafts"])
def update_draft(draft_id: DraftId, body: DraftUpdate, request: Request, user: User):
    return request.app.state.drafts.update(user.id, draft_id, body.topology, body.version)


@app.delete("/v1/drafts/{draft_id}", tags=["drafts"])
def delete_draft(draft_id: DraftId, request: Request, user: User):
    request.app.state.drafts.delete(user.id, draft_id)
    return {"status": "deleted"}
