from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import Role, User
from app.schemas.user import UserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def create_user(db: Session, data: UserCreate, role: Role, business_id: int) -> User:
    """Add a user to a business. The caller commits, so related rows share one transaction."""
    if get_user_by_email(db, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")

    user = User(
        full_name=data.full_name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=role,
        business_id=business_id,
    )
    db.add(user)
    db.flush()  # sends the INSERT so user.id is available, but does not commit yet
    return user


def register_customer(db: Session, data: UserCreate, business_id: int) -> User:
    user = create_user(db, data, Role.CUSTOMER, business_id)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    # Same message for "unknown email" and "wrong password" so attackers can't tell which.
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled")
    if not user.business.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This business account has been disabled")
    return user
