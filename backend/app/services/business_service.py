"""Phase 8: businesses (tenants). Creating one, and finding one by its public code."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, Role, User
from app.schemas.business import BusinessSignup
from app.services import user_service


def signup(db: Session, data: BusinessSignup) -> tuple[Business, User]:
    """Create a business and its first admin in ONE transaction: both are saved, or neither."""
    if db.scalar(select(Business).where(Business.slug == data.business_slug)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This business code is already taken")
    business = Business(name=data.business_name, slug=data.business_slug)
    db.add(business)
    db.flush()  # gives the business its id, without committing yet
    admin = user_service.create_user(db, data, Role.ADMIN, business.id)  # 409 if the email is taken
    db.commit()
    db.refresh(business)
    db.refresh(admin)
    return business, admin


def get_active(db: Session, slug: str) -> Business:
    business = db.scalar(select(Business).where(Business.slug == slug.lower()))
    if business is None or not business.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return business
