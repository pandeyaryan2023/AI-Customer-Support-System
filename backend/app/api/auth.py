from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.schemas.user import Token, UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: DbSession):
    """Customer self-registration. Agents and admins are created by an admin."""
    return user_service.register_customer(db, data)


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """Log in with form fields `username` (the email) and `password`."""
    user = user_service.authenticate(db, form.username, form.password)
    return Token(access_token=create_access_token(user.id), role=user.role, full_name=user.full_name)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
