from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Role = Literal["admin", "professor", "student"]
Action = Literal[
    "platform.read", "slice.create", "slice.read", "slice.update", "slice.delete",
    "slice.assign", "slice.start", "slice.stop", "slice.metrics", "vm.console",
    "template.read", "template.write", "image.manage", "infrastructure.manage",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Model):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize(cls, value):
        return value.lower()


class UserCreate(Login):
    password: SecretStr = Field(min_length=15, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role


class UserUpdate(Model):
    role: Role | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if self.role is None and self.active is None:
            raise ValueError("Specify role or active")
        return self


class PasswordReset(Model):
    password: SecretStr = Field(min_length=15, max_length=128)


class PasswordChange(PasswordReset):
    current_password: SecretStr = Field(min_length=1, max_length=128)


class CourseCreate(Model):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    professor_can_modify: bool = True


class Quotas(Model):
    max_slices: int = Field(default=0, ge=0, le=10000)
    max_vcpus: int = Field(default=0, ge=0, le=100000)
    max_ram_mb: int = Field(default=0, ge=0, le=1000000000)
    max_disk_gb: int = Field(default=0, ge=0, le=1000000000)


class Membership(Model):
    quotas: Quotas = Field(default_factory=Quotas)


class ResourceCreate(Model):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    kind: Literal["slice", "vm"]
    course_id: str = Field(min_length=1, max_length=64)
    professor_id: str = Field(min_length=1, max_length=64)
    parent_slice_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def parent(self):
        if (self.kind == "vm") != (self.parent_slice_id is not None):
            raise ValueError("Only VM resources require parent_slice_id")
        return self


class AuthorizationRequest(Model):
    action: Action
    course_id: str | None = Field(default=None, max_length=64)
    resource_id: str | None = Field(default=None, max_length=128)


class Decision(Model):
    model_config = ConfigDict(extra="forbid", strict=True)
    allowed: bool
    action: Action
    reason: str


class UserView(Model):
    id: str
    username: str
    display_name: str
    role: Role
    active: bool


class TokenResponse(Model):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class Message(Model):
    status: str
