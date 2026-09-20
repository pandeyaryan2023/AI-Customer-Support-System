from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Every database model inherits from this class."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
