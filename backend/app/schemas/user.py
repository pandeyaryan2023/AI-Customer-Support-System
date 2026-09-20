from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.models.enums import Role

FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class UserCreate(BaseModel):
    full_name: FullName
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes, so longer passwords are rejected.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes long")
        return value


class AgentCreate(UserCreate):
    department: Optional[str] = Field(default=None, max_length=100)


class UserBrief(BaseModel):
    """Minimal public info about a user (safe to show inside a ticket)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: Role


class UserOut(UserBrief):
    email: str
    is_active: bool
    created_at: datetime


class AgentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department: Optional[str]
    user: UserBrief


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department: Optional[str]
    user: UserOut


class UserActiveUpdate(BaseModel):
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    full_name: str
