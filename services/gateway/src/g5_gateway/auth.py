from typing import Annotated
from fastapi import Path as PathParam
"""Explicit IAM routes; no wildcard proxy and no trusted client identity headers."""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, SecretStr, ValidationError

from .iam_models import (AuthorizationRequest, CourseCreate, Decision, Login, Membership,
                         PasswordChange, PasswordReset, ResourceCreate, TokenResponse,
                         UserCreate, UserUpdate, UserView)

Identifier = Annotated[str, PathParam(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")]


router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "invalid_credentials", headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


def wire(value):
    # SecretStr.model_dump_json masks passwords; unwrap only for this HTTP request.
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, BaseModel):
        return {name: wire(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    return value


async def iam_call(request, method, path, access_token=None, body=None, params=None):
    try:
        response = await request.app.state.iam.request(
            method, path, headers={"Authorization": "Bearer " + access_token} if access_token else {},
            json=wire(body) if body is not None else None, params=params,
        )
    except httpx.TimeoutException:
        raise HTTPException(504, "iam_timeout") from None
    except httpx.RequestError:
        raise HTTPException(503, "iam_unavailable") from None
    if response.status_code >= 500:
        raise HTTPException(503, "iam_unavailable")
    if response.status_code not in {200, 201, 401, 403, 404, 409, 422, 429}:
        raise HTTPException(502, "iam_bad_response")
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(502, "iam_bad_response") from None
    if response.status_code in {401, 403, 404, 409, 422, 429}:
        # Fixed public errors; never echo upstream input or raw exception text.
        detail = {401: "invalid_credentials", 403: "not_authorized", 404: "not_found",
                  409: "conflict", 422: "invalid_request", 429: "too_many_attempts"}[response.status_code]
        headers = {"WWW-Authenticate": "Bearer"} if response.status_code == 401 else {}
        if response.status_code == 429:
            headers["Retry-After"] = "60"
        raise HTTPException(response.status_code, detail, headers=headers)
    return data


async def principal(request: Request, access_token=Depends(token)):
    data = await iam_call(request, "GET", "/v1/auth/me", access_token)
    try:
        UserView.model_validate(data)
    except ValidationError:
        raise HTTPException(502, "iam_bad_response") from None
    return access_token


async def platform_access(request: Request, access_token=Depends(token)):
    data = await iam_call(request, "POST", "/v1/iam/authorize", access_token,
                          AuthorizationRequest(action="platform.read"))
    try:
        decision = Decision.model_validate(data)
        if decision.action != "platform.read":
            raise ValueError("wrong action")
    except (ValidationError, ValueError):
        raise HTTPException(502, "iam_bad_response") from None
    if not decision.allowed:
        raise HTTPException(403, "not_authorized")
    return access_token


@router.post("/v1/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(body: Login, request: Request):
    data = await iam_call(request, "POST", "/v1/auth/login", body=body)
    try:
        validated = TokenResponse.model_validate(data)
    except ValidationError:
        raise HTTPException(502, "iam_bad_response") from None
    return JSONResponse(validated.model_dump(), headers={"Cache-Control": "no-store"})


@router.get("/v1/auth/me", response_model=UserView, tags=["auth"])
async def me(request: Request, access_token=Depends(token)):
    return await iam_call(request, "GET", "/v1/auth/me", access_token)


@router.post("/v1/auth/logout", tags=["auth"])
async def logout(request: Request, access_token=Depends(token)):
    return await iam_call(request, "POST", "/v1/auth/logout", access_token)


@router.post("/v1/auth/password", tags=["auth"])
async def change_password(body: PasswordChange, request: Request, access_token=Depends(token)):
    return await iam_call(request, "POST", "/v1/auth/password", access_token, body)


@router.post("/v1/iam/authorize", response_model=Decision, tags=["authorization"])
async def authorize(body: AuthorizationRequest, request: Request, access_token=Depends(token)):
    return await iam_call(request, "POST", "/v1/iam/authorize", access_token, body)


@router.get("/v1/iam/users", response_model=list[UserView], tags=["IAM administration"])
async def users(request: Request, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), access_token=Depends(token)):
    return await iam_call(request, "GET", "/v1/iam/users", access_token, params={"limit": limit, "offset": offset})


@router.post("/v1/iam/users", response_model=UserView, status_code=201, tags=["IAM administration"])
async def create_user(body: UserCreate, request: Request, access_token=Depends(token)):
    return await iam_call(request, "POST", "/v1/iam/users", access_token, body)


@router.patch("/v1/iam/users/{user_id}", response_model=UserView, tags=["IAM administration"])
async def update_user(user_id: Identifier, body: UserUpdate, request: Request, access_token=Depends(token)):
    return await iam_call(request, "PATCH", f"/v1/iam/users/{user_id}", access_token, body)


@router.post("/v1/iam/users/{user_id}/password", tags=["IAM administration"])
async def reset_password(user_id: Identifier, body: PasswordReset, request: Request, access_token=Depends(token)):
    return await iam_call(request, "POST", f"/v1/iam/users/{user_id}/password", access_token, body)


@router.get("/v1/iam/courses", tags=["courses"])
async def courses(request: Request, access_token=Depends(token)):
    return await iam_call(request, "GET", "/v1/iam/courses", access_token)


@router.post("/v1/iam/courses", status_code=201, tags=["courses"])
async def create_course(body: CourseCreate, request: Request, access_token=Depends(token)):
    return await iam_call(request, "POST", "/v1/iam/courses", access_token, body)


@router.put("/v1/iam/courses/{course_id}/members/{user_id}", tags=["courses"])
async def set_membership(course_id: Identifier, user_id: Identifier, body: Membership, request: Request, access_token=Depends(token)):
    return await iam_call(request, "PUT", f"/v1/iam/courses/{course_id}/members/{user_id}", access_token, body)


@router.delete("/v1/iam/courses/{course_id}/members/{user_id}", tags=["courses"])
async def delete_membership(course_id: Identifier, user_id: Identifier, request: Request, access_token=Depends(token)):
    return await iam_call(request, "DELETE", f"/v1/iam/courses/{course_id}/members/{user_id}", access_token)


@router.get("/v1/iam/courses/{course_id}/members/{user_id}", tags=["courses"])
async def get_membership(course_id: Identifier, user_id: Identifier, request: Request, access_token=Depends(token)):
    return await iam_call(request, "GET", f"/v1/iam/courses/{course_id}/members/{user_id}", access_token)


@router.get("/v1/iam/courses/{course_id}/students", tags=["courses"])
async def course_students(course_id: Identifier, request: Request, access_token=Depends(token)):
    return await iam_call(request, "GET", f"/v1/iam/courses/{course_id}/students", access_token)


@router.post("/v1/iam/resources", status_code=201, tags=["authorization metadata"])
async def register_resource(body: ResourceCreate, request: Request, access_token=Depends(token)):
    return await iam_call(request, "POST", "/v1/iam/resources", access_token, body)


@router.get("/v1/iam/resources", tags=["authorization metadata"])
async def resources(request: Request, access_token=Depends(token)):
    return await iam_call(request, "GET", "/v1/iam/resources", access_token)


@router.put("/v1/iam/resources/{resource_id}/assignments/{user_id}", tags=["authorization metadata"])
async def assign_resource(resource_id: Identifier, user_id: Identifier, request: Request, access_token=Depends(token)):
    return await iam_call(request, "PUT", f"/v1/iam/resources/{resource_id}/assignments/{user_id}", access_token)


@router.delete("/v1/iam/resources/{resource_id}/assignments/{user_id}", tags=["authorization metadata"])
async def unassign_resource(resource_id: Identifier, user_id: Identifier, request: Request, access_token=Depends(token)):
    return await iam_call(request, "DELETE", f"/v1/iam/resources/{resource_id}/assignments/{user_id}", access_token)


@router.get("/v1/iam/audit", tags=["IAM administration"])
async def audit(request: Request, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0), access_token=Depends(token)):
    return await iam_call(request, "GET", "/v1/iam/audit", access_token, params={"limit": limit, "offset": offset})
