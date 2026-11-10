from typing import Annotated
from fastapi import Path as PathParam
import hashlib
import hmac
import sqlite3
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import (AuthorizationRequest, CourseCreate, Decision, Login, Membership,
                     Message, PasswordChange, PasswordReset, Person, ResourceCreate, SliceRegistration,
                     TokenResponse, UserCreate, UserUpdate, UserView)
from .policy import decide
from .security import PASSWORDS, authenticate, login as perform_login, unauthorized
from .settings import Settings
from .store import Store, audit, public_user, require_row


Identifier = Annotated[str, PathParam(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")]


@asynccontextmanager
async def lifespan(app):
    app.state.settings = Settings.load()
    app.state.secret = app.state.settings.read_secret()
    app.state.store = Store(app.state.settings.database)
    app.state.store.check_schema()
    app.state.service_hash = app.state.settings.service_token_hash()
    yield


app = FastAPI(title="G5 IAM", version="0.2.0", lifespan=lifespan,
              description="Identidad, sesiones y autorización académica. No aprovisiona infraestructura.")
bearer = HTTPBearer(auto_error=False)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Never echo password/input values from Pydantic errors.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"]} for e in exc.errors()
    ]})


@app.exception_handler(sqlite3.IntegrityError)
async def conflict(request, exc):
    return JSONResponse(status_code=409, content={"detail": "conflict"})


@app.exception_handler(sqlite3.OperationalError)
async def unavailable(request, exc):
    return JSONResponse(status_code=503, content={"detail": "iam_storage_unavailable"})


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


def context(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    store = request.app.state.store
    actor = None
    try:
        with store.transaction() as db:
            if not credentials or credentials.scheme.lower() != "bearer":
                raise unauthorized()
            user, claims = authenticate(db, request.app.state.secret, request.app.state.settings,
                                        credentials.credentials)
            actor = user["id"]
            yield db, user, claims
    except HTTPException as exc:
        if exc.status_code in (401, 403):
            route = request.scope.get("route")
            store.record(actor, request.method + " " + (route.path if route else "request"), None, "denied")
        raise


def service(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """Identidad de servicio del Slice Manager (D-14): solo para el registro interno de recursos."""
    expected = request.app.state.service_hash
    if not expected or not credentials or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    if not hmac.compare_digest(hashlib.sha256(credentials.credentials.encode()).hexdigest(), expected):
        raise unauthorized()
    with request.app.state.store.transaction() as db:
        yield db


def admin(ctx=Depends(context, scope="function")):
    if ctx[1]["role"] != "admin":
        raise HTTPException(403, "not_authorized")
    return ctx


@app.get("/healthz")
def health():
    return {"service": "iam", "status": "ok"}


@app.get("/readyz")
def ready(request: Request):
    with request.app.state.store.transaction() as db:
        db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    return health()


@app.post("/v1/auth/login", response_model=TokenResponse)
def login(body: Login, request: Request):
    return perform_login(request.app.state.store, request.app.state.settings, request.app.state.secret, body)


@app.get("/v1/auth/me", response_model=UserView)
def me(ctx=Depends(context, scope="function")):
    db, user, _ = ctx
    audit(db, user["id"], "identity.read", user["id"], "allowed")
    return public_user(user)


@app.post("/v1/auth/logout", response_model=Message)
def logout(ctx=Depends(context, scope="function")):
    db, user, claims = ctx
    db.execute("DELETE FROM sessions WHERE jti=?", (claims["jti"],))
    audit(db, user["id"], "logout", user["id"], "allowed")
    return {"status": "logged_out"}


@app.post("/v1/auth/password", response_model=Message)
def change_password(body: PasswordChange, ctx=Depends(context, scope="function")):
    db, user, _ = ctx
    if not PASSWORDS.verify(body.current_password.get_secret_value(), user["password_hash"]):
        raise unauthorized()
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (PASSWORDS.hash(body.password.get_secret_value()), user["id"]))
    db.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
    audit(db, user["id"], "password.change", user["id"], "allowed")
    return {"status": "password_changed_login_required"}


@app.post("/v1/iam/authorize", response_model=Decision)
def authorize(body: AuthorizationRequest, ctx=Depends(context, scope="function")):
    db, user, _ = ctx
    decision = decide(db, user, body)
    audit(db, user["id"], body.action, body.resource_id or body.course_id,
          "allowed" if decision.allowed else "denied")
    return decision


@app.get("/v1/iam/users", response_model=list[UserView])
def list_users(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), ctx=Depends(admin)):
    db, user, _ = ctx
    audit(db, user["id"], "users.list", None, "allowed")
    return [public_user(r) for r in db.execute("SELECT * FROM users ORDER BY username LIMIT ? OFFSET ?", (limit, offset))]


@app.post("/v1/iam/users", response_model=UserView, status_code=201)
def create_user(body: UserCreate, ctx=Depends(admin)):
    db, user, _ = ctx
    identity = str(uuid.uuid4())
    db.execute("INSERT INTO users(id,username,display_name,password_hash,role) VALUES(?,?,?,?,?)",
               (identity, body.username, body.display_name, PASSWORDS.hash(body.password.get_secret_value()), body.role))
    audit(db, user["id"], "user.create", identity, "allowed")
    return public_user(require_row(db, "users", identity))


@app.patch("/v1/iam/users/{user_id}", response_model=UserView)
def update_user(user_id: Identifier, body: UserUpdate, ctx=Depends(admin)):
    db, user, _ = ctx
    target = require_row(db, "users", user_id)
    role = body.role if body.role is not None else target["role"]
    active = body.active if body.active is not None else bool(target["active"])
    if target["role"] == "admin" and target["active"] and (role != "admin" or not active):
        if db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
            raise HTTPException(409, "last_active_admin")
    db.execute("UPDATE users SET role=?,active=? WHERE id=?", (role, int(active), user_id))
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    audit(db, user["id"], "user.update", user_id, "allowed")
    return public_user(require_row(db, "users", user_id))


@app.post("/v1/iam/users/{user_id}/password", response_model=Message)
def reset_password(user_id: Identifier, body: PasswordReset, ctx=Depends(admin)):
    db, user, _ = ctx
    require_row(db, "users", user_id)
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (PASSWORDS.hash(body.password.get_secret_value()), user_id))
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    audit(db, user["id"], "password.reset", user_id, "allowed")
    return {"status": "password_reset_sessions_revoked"}


@app.get("/v1/iam/courses")
def list_courses(ctx=Depends(context, scope="function")):
    db, user, _ = ctx
    if user["role"] == "admin":
        rows = db.execute("SELECT * FROM courses ORDER BY id").fetchall()
    else:
        rows = db.execute("SELECT c.* FROM courses c JOIN memberships m ON c.id=m.course_id WHERE m.user_id=? ORDER BY c.id", (user["id"],)).fetchall()
    audit(db, user["id"], "courses.list", None, "allowed")
    return [dict(r) for r in rows]


@app.post("/v1/iam/courses", status_code=201)
def create_course(body: CourseCreate, ctx=Depends(admin)):
    db, user, _ = ctx
    db.execute("INSERT INTO courses VALUES(?,?,?)", (body.id, body.name, int(body.professor_can_modify)))
    audit(db, user["id"], "course.create", body.id, "allowed")
    return body


@app.put("/v1/iam/courses/{course_id}/members/{user_id}")
def set_membership(course_id: Identifier, user_id: Identifier, body: Membership, ctx=Depends(admin)):
    db, user, _ = ctx
    require_row(db, "courses", course_id)
    require_row(db, "users", user_id)
    db.execute("INSERT INTO memberships VALUES(?,?,?) ON CONFLICT(course_id,user_id) DO UPDATE SET quotas=excluded.quotas",
               (course_id, user_id, body.quotas.model_dump_json()))
    audit(db, user["id"], "membership.set", course_id + ":" + user_id, "allowed")
    return {"course_id": course_id, "user_id": user_id, "quotas": body.quotas}


@app.delete("/v1/iam/courses/{course_id}/members/{user_id}", response_model=Message)
def remove_membership(course_id: Identifier, user_id: Identifier, ctx=Depends(admin)):
    db, user, _ = ctx
    db.execute("DELETE FROM memberships WHERE course_id=? AND user_id=?", (course_id, user_id))
    # Removing and re-enrolling a student must not silently restore old grants.
    db.execute("DELETE FROM assignments WHERE user_id=? AND resource_id IN (SELECT id FROM resources WHERE course_id=?)", (user_id, course_id))
    audit(db, user["id"], "membership.remove", course_id + ":" + user_id, "allowed")
    return {"status": "membership_removed"}


@app.get("/v1/iam/courses/{course_id}/members/{user_id}")
def get_membership(course_id: Identifier, user_id: Identifier, ctx=Depends(context, scope="function")):
    import json
    db, user, _ = ctx
    if user["role"] != "admin" and user["id"] != user_id:
        raise HTTPException(403, "not_authorized")
    row = db.execute("SELECT quotas FROM memberships WHERE course_id=? AND user_id=?", (course_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "not_found")
    audit(db, user["id"], "membership.read", course_id + ":" + user_id, "allowed")
    return {"course_id": course_id, "user_id": user_id, "quotas": json.loads(row["quotas"])}


@app.post("/v1/iam/resources", status_code=201)
def register_resource(body: ResourceCreate, ctx=Depends(admin)):
    # Authorization metadata only. This endpoint neither creates nor discovers a VM/slice.
    db, user, _ = ctx
    require_row(db, "courses", body.course_id)
    professor = require_row(db, "users", body.professor_id)
    membership = db.execute("SELECT 1 FROM memberships WHERE course_id=? AND user_id=?", (body.course_id, body.professor_id)).fetchone()
    if professor["role"] != "professor" or not professor["active"] or not membership:
        raise HTTPException(409, "professor_not_in_course")
    if body.kind == "vm":
        parent = require_row(db, "resources", body.parent_slice_id)
        if parent["kind"] != "slice" or parent["course_id"] != body.course_id or parent["professor_id"] != body.professor_id:
            raise HTTPException(409, "invalid_parent_slice")
    db.execute("INSERT INTO resources VALUES(?,?,?,?,?)",
               (body.id, body.kind, body.course_id, body.professor_id, body.parent_slice_id))
    audit(db, user["id"], "resource.register_metadata", body.id, "allowed")
    return body


@app.get("/v1/iam/resources")
def list_resources(ctx=Depends(context, scope="function")):
    db, user, _ = ctx
    rows = db.execute("SELECT * FROM resources ORDER BY id").fetchall()
    visible = []
    for row in rows:
        action = "vm.console" if row["kind"] == "vm" else "slice.read"
        if decide(db, user, AuthorizationRequest(action=action, resource_id=row["id"])).allowed:
            visible.append(dict(row))
    audit(db, user["id"], "resources.list_metadata", None, "allowed")
    return visible


@app.put("/v1/iam/resources/{resource_id}/assignments/{user_id}", response_model=Message)
def assign_resource(resource_id: Identifier, user_id: Identifier, ctx=Depends(context, scope="function")):
    db, user, _ = ctx
    resource = require_row(db, "resources", resource_id)
    slice_id = resource["parent_slice_id"] if resource["kind"] == "vm" else resource_id
    if not decide(db, user, AuthorizationRequest(action="slice.assign", resource_id=slice_id)).allowed:
        raise HTTPException(403, "not_authorized")
    student = require_row(db, "users", user_id)
    member = db.execute("SELECT 1 FROM memberships WHERE course_id=? AND user_id=?", (resource["course_id"], user_id)).fetchone()
    if student["role"] != "student" or not student["active"] or not member:
        raise HTTPException(409, "student_not_in_course")
    if resource["kind"] == "vm" and not db.execute("SELECT 1 FROM assignments WHERE resource_id=? AND user_id=?", (slice_id, user_id)).fetchone():
        raise HTTPException(409, "slice_assignment_required")
    db.execute("INSERT OR IGNORE INTO assignments VALUES(?,?)", (resource_id, user_id))
    audit(db, user["id"], "assignment.set", resource_id + ":" + user_id, "allowed")
    return {"status": "assigned"}


@app.delete("/v1/iam/resources/{resource_id}/assignments/{user_id}", response_model=Message)
def unassign_resource(resource_id: Identifier, user_id: Identifier, ctx=Depends(context, scope="function")):
    db, user, _ = ctx
    resource = require_row(db, "resources", resource_id)
    slice_id = resource["parent_slice_id"] if resource["kind"] == "vm" else resource_id
    if not decide(db, user, AuthorizationRequest(action="slice.assign", resource_id=slice_id)).allowed:
        raise HTTPException(403, "not_authorized")
    db.execute("DELETE FROM assignments WHERE user_id=? AND (resource_id=? OR resource_id IN (SELECT id FROM resources WHERE parent_slice_id=?))", (user_id, resource_id, resource_id))
    audit(db, user["id"], "assignment.remove", resource_id + ":" + user_id, "allowed")
    return {"status": "unassigned"}


@app.get("/v1/iam/audit")
def list_audit(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), ctx=Depends(admin)):
    db, user, _ = ctx
    audit(db, user["id"], "audit.read", None, "allowed")
    return [dict(r) for r in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))]



@app.put("/v1/iam/internal/slices/{slice_id}", response_model=Message)
def register_slice(slice_id: Identifier, body: SliceRegistration, db=Depends(service, scope="function")):
    """Registra (idempotente) un slice y sus VMs para que IAM decida asignaciones, lectura y consola."""
    if body.id != slice_id:
        raise HTTPException(422, "id_mismatch")
    require_row(db, "courses", body.course_id)
    professor = require_row(db, "users", body.professor_id)
    member = db.execute("SELECT 1 FROM memberships WHERE course_id=? AND user_id=?",
                        (body.course_id, body.professor_id)).fetchone()
    if professor["role"] != "professor" or not professor["active"] or not member:
        raise HTTPException(409, "professor_not_in_course")
    existing = db.execute("SELECT * FROM resources WHERE id=?", (slice_id,)).fetchone()
    if existing and (existing["kind"], existing["course_id"], existing["professor_id"]) != ("slice", body.course_id, body.professor_id):
        raise HTTPException(409, "conflict")
    db.execute("INSERT OR IGNORE INTO resources VALUES(?,?,?,?,?)", (slice_id, "slice", body.course_id, body.professor_id, None))
    for vm in body.vms:
        db.execute("INSERT OR IGNORE INTO resources VALUES(?,?,?,?,?)",
                   (f"{slice_id}-{vm}", "vm", body.course_id, body.professor_id, slice_id))
    audit(db, "service:slice-manager", "resource.register_slice", slice_id, "allowed")
    return {"status": "registered"}


@app.get("/v1/iam/courses/{course_id}/students", response_model=list[Person])
def course_students(course_id: Identifier, ctx=Depends(context, scope="function")):
    """Alumnos activos del curso: para que el profesor elija a quién asignar un slice."""
    db, user, _ = ctx
    require_row(db, "courses", course_id)
    member = db.execute("SELECT 1 FROM memberships WHERE course_id=? AND user_id=?", (course_id, user["id"])).fetchone()
    if not (user["role"] == "admin" or (user["role"] == "professor" and member)):
        raise HTTPException(403, "not_authorized")
    rows = db.execute("SELECT u.id, u.username, u.display_name FROM users u JOIN memberships m ON m.user_id=u.id "
                      "WHERE m.course_id=? AND u.role='student' AND u.active=1 ORDER BY u.username", (course_id,)).fetchall()
    audit(db, user["id"], "course.students", course_id, "allowed")
    return [dict(r) for r in rows]


@app.get("/v1/iam/resources/{resource_id}/assignments", response_model=list[Person])
def resource_assignments(resource_id: Identifier, ctx=Depends(context, scope="function")):
    """A quién está asignado un slice; mismo permiso que asignar (profesor del slice o admin)."""
    db, user, _ = ctx
    resource = require_row(db, "resources", resource_id)
    slice_id = resource["parent_slice_id"] if resource["kind"] == "vm" else resource_id
    if not decide(db, user, AuthorizationRequest(action="slice.assign", resource_id=slice_id)).allowed:
        raise HTTPException(403, "not_authorized")
    rows = db.execute("SELECT u.id, u.username, u.display_name FROM users u JOIN assignments a ON a.user_id=u.id "
                      "WHERE a.resource_id=? ORDER BY u.username", (resource_id,)).fetchall()
    return [dict(r) for r in rows]
