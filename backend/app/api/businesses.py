from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.business import BusinessPublic, BusinessSignup, BusinessSignupOut
from app.services import business_service

router = APIRouter(prefix="/businesses", tags=["Businesses"])


@router.post("", response_model=BusinessSignupOut, status_code=status.HTTP_201_CREATED)
def create_business(data: BusinessSignup, db: DbSession):
    """Start using the service: create a business and its first admin, who then logs in.

    The admin adds agents and categories; customers register with the business's code.
    """
    business, admin = business_service.signup(db, data)
    return BusinessSignupOut(business=business, admin=admin)


@router.get("/{slug}", response_model=BusinessPublic)
def get_business(slug: str, db: DbSession):
    """Public: a business's name for its code, so the sign-up page can say who you are joining."""
    return business_service.get_active(db, slug)
