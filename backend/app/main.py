from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import admin, agents, auth, categories, tickets
from app.api.deps import DbSession
from app.core.config import settings

app = FastAPI(
    title="AI-Powered Customer Support and Complaint Management System",
    version="0.1.0",
)

# CORS: only the listed frontend origins may call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(categories.router)
app.include_router(agents.router)
app.include_router(admin.router)

# The web interface (plain HTML/CSS/JS) is served from the same server at /app/,
# so the browser and the API share one origin.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"  # <project root>/frontend
if FRONTEND_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/app/")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.get("/health/db", tags=["Health"])
def health_db(db: DbSession):
    """Checks that the database connection works."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is unavailable")
    return {"status": "ok", "database": "connected"}
