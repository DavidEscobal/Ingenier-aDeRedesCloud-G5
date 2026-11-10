"""Image Catalog (D-15): catálogo de imágenes independiente del proveedor.

Es dueño de los metadatos (nombre, formato, tamaño, SHA-256, quién la importó, en qué proveedor está). Los bytes
no se guardan aquí: la subida se reenvía en streaming al platform-manager, que la materializa en el proveedor
(hoy Glance de OpenStack). Importar exige `image.manage` en IAM (admin); listar, cualquier usuario autenticado.
"""
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
from pydantic import BaseModel, ValidationError

NAME = r"^[a-z0-9][a-z0-9._-]{0,62}$"


class Health(BaseModel):
    service: Literal["image-catalog"] = "image-catalog"
    status: Literal["ok"] = "ok"


class Image(BaseModel):
    name: str
    provider: str
    status: str
    disk_format: str | None = None
    size: int | None = None
    sha256: str | None = None
    source: Literal["catalog", "provider"]
    uploaded_by: str | None = None
    description: str | None = None
    created_at: float | str | None = None


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


class Catalog:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS images(name TEXT PRIMARY KEY, provider TEXT NOT NULL,
            provider_id TEXT, disk_format TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL,
            uploaded_by TEXT NOT NULL, description TEXT, created_at REAL NOT NULL)""")

    def add(self, row):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO images VALUES(:name,:provider,:provider_id,:disk_format,:size,"
                            ":sha256,:uploaded_by,:description,:created_at)", row)

    def all(self):
        with self.lock:
            return {r["name"]: dict(r) for r in self.db.execute("SELECT * FROM images")}

    def close(self):
        self.db.close()


@asynccontextmanager
async def lifespan(app):
    app.state.catalog = Catalog(os.getenv("IMAGE_DB_PATH", "state/images/catalog.db"))
    app.state.max_bytes = int(os.getenv("IMAGE_MAX_MB", "1024")) * 1024 * 1024
    platform_url = os.getenv("PLATFORM_MANAGER_URL")
    app.state.platform_token = None
    if platform_url:
        platform_url = origin("PLATFORM_MANAGER_URL", platform_url)
        app.state.platform_token = Path(os.environ["PLATFORM_TOKEN_FILE"]).read_text(encoding="utf-8").strip()
        if len(app.state.platform_token) < 32:
            raise ValueError("PLATFORM_TOKEN_FILE debe contener un token de servicio")
    async with httpx.AsyncClient(base_url=origin("IAM_URL", "http://127.0.0.1:8002"), timeout=3,
                                 trust_env=False, follow_redirects=False) as iam, \
            httpx.AsyncClient(base_url=platform_url or "http://platform.invalid", timeout=20,
                              trust_env=False, follow_redirects=False) as platform:
        app.state.iam = iam
        app.state.platform = platform if platform_url else None
        try:
            yield
        finally:
            app.state.catalog.close()


bearer = HTTPBearer(auto_error=False)


def credentials_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


async def iam(request, method, path, token, body=None):
    try:
        response = await request.app.state.iam.request(method, path, headers={"Authorization": "Bearer " + token}, json=body)
    except httpx.RequestError:
        raise HTTPException(503, "iam_unavailable") from None
    if response.status_code == 401:
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    if response.status_code != 200:
        raise HTTPException(503, "iam_unavailable")
    return response.json()


async def current_user(request: Request, token=Depends(credentials_token)) -> UserView:
    try:
        user = UserView.model_validate(await iam(request, "GET", "/v1/auth/me", token))
    except ValidationError:
        raise HTTPException(502, "iam_bad_response") from None
    if not user.active:
        raise HTTPException(403, "not_authorized")
    return user


def platform(request):
    if request.app.state.platform is None:
        raise HTTPException(503, "platform_unavailable")
    return request.app.state.platform, {"Authorization": "Bearer " + request.app.state.platform_token}


app = FastAPI(title="G5 Image Catalog", version="0.1.0", lifespan=lifespan,
              description="Catálogo de imágenes independiente del proveedor; importa en streaming hacia el proveedor.")


@app.get("/healthz", response_model=Health, tags=["health"])
def health() -> Health:
    return Health()


@app.get("/v1/images", response_model=list[Image], tags=["images"])
async def list_images(request: Request, user: UserView = Depends(current_user)) -> list[Image]:
    """Imágenes utilizables: las de Glance (activas y públicas) con los metadatos del catálogo cuando existen."""
    client, headers = platform(request)
    try:
        response = await client.get("/v1/provider-images/openstack", headers=headers)
    except httpx.RequestError:
        raise HTTPException(503, "platform_unavailable") from None
    if response.status_code != 200:
        raise HTTPException(503, "platform_unavailable")
    catalog = request.app.state.catalog.all()
    result = []
    for image in response.json():
        if image.get("status") != "active" or image.get("visibility") not in ("public", "community"):
            continue
        meta = catalog.get(image.get("name"))
        result.append(Image(name=image["name"], provider="openstack", status=image["status"],
                            disk_format=image.get("disk_format"), size=image.get("size"),
                            sha256=meta and meta["sha256"], source="catalog" if meta else "provider",
                            uploaded_by=meta and meta["uploaded_by"], description=meta and meta["description"],
                            created_at=meta["created_at"] if meta else image.get("created_at")))
    return sorted(result, key=lambda i: i.name)


@app.post("/v1/images", response_model=Image, status_code=201, tags=["images"])
async def import_image(request: Request, name: str = Query(pattern=NAME),
                       disk_format: Literal["qcow2", "raw"] = "qcow2",
                       description: str = Query(default="", max_length=200),
                       token=Depends(credentials_token), user: UserView = Depends(current_user)) -> Image:
    """Cuerpo = bytes de la imagen (Content-Length obligatorio). Se reenvía en streaming; nada se guarda aquí."""
    decision = await iam(request, "POST", "/v1/iam/authorize", token, {"action": "image.manage"})
    if not decision.get("allowed"):
        raise HTTPException(403, "not_authorized")
    try:
        size = int(request.headers.get("content-length", ""))
    except ValueError:
        raise HTTPException(411, "Se requiere Content-Length") from None
    if size <= 0:
        raise HTTPException(422, "Archivo vacío")
    if size > request.app.state.max_bytes:
        raise HTTPException(413, f"La imagen supera el límite de {request.app.state.max_bytes // (1024 * 1024)} MB")
    client, headers = platform(request)

    async def body():
        async for chunk in request.stream():
            yield chunk

    try:
        response = await client.put(f"/v1/provider-images/openstack/{name}", params={"disk_format": disk_format},
                                    content=body(), headers=dict(headers, **{"Content-Length": str(size),
                                                                             "Content-Type": "application/octet-stream"}),
                                    timeout=httpx.Timeout(900, connect=10))
    except httpx.TimeoutException:
        raise HTTPException(504, "platform_timeout") from None
    except httpx.RequestError:
        raise HTTPException(503, "platform_unavailable") from None
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(502, "platform_bad_response") from None
    if response.status_code != 201:
        message = data.get("error") if isinstance(data, dict) else None
        if response.status_code in (400, 409, 413):
            raise HTTPException(409 if response.status_code == 409 else 422 if response.status_code == 400 else 413,
                                str(message)[:300])
        raise HTTPException(502, "platform_error")
    row = dict(name=name, provider="openstack", provider_id=data.get("id"), disk_format=disk_format,
               size=data.get("size", size), sha256=data.get("sha256", ""), uploaded_by=user.username,
               description=description or None, created_at=time.time())
    request.app.state.catalog.add(row)
    return Image(name=name, provider="openstack", status="active", disk_format=disk_format, size=row["size"],
                 sha256=row["sha256"], source="catalog", uploaded_by=user.username, description=row["description"],
                 created_at=row["created_at"])
