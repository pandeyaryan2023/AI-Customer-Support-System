from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.schemas.business import CustomerRegister, MeOut
from app.schemas.user import Token, UserOut
from app.services import business_service, user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: CustomerRegister, db: DbSession):
    """Customer self-registration on a business's support portal (`business` is its public code).

    Agents and admins are created by that business's admin.
    """
    business = business_service.get_active(db, data.business)
    return user_service.register_customer(db, data, business.id)


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """Log in with form fields `username` (the email) and `password`."""
    user = user_service.authenticate(db, form.username, form.password)
    return Token(access_token=create_access_token(user.id, user.business_id), role=user.role,
                 full_name=user.full_name, business_name=user.business.name)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser):
    return user
