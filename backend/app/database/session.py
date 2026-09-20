from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# The engine manages connections to PostgreSQL. It only connects when first used.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# A session is one "conversation" with the database (a unit of work / transaction).
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    """FastAPI dependency: one session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
