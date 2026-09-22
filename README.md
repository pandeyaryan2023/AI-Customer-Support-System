# AI-Powered Customer Support and Complaint Management System

BCA-507 Minor Project. Customers raise complaints, support agents resolve them, admins manage the system.

## Current status

| Part | Status |
|---|---|
| Python CLI prototype (`python-prototype/`) | Done |
| Backend: FastAPI + PostgreSQL + SQLAlchemy + Alembic | Done |
| Authentication (bcrypt + JWT) and role-based access | Done |
| Core ticket management (customer / agent / admin APIs) | Done |
| Automated tests (pytest) | 284 passing, plus 20 opt-in tests against the real model (see [docs/test-cases.md](docs/test-cases.md)) |
| Knowledge base: document upload, storage, list, delete | Done (Phase 1) — no AI yet |
| Knowledge base: text extraction from PDF (pypdf) and UTF-8 text | Done (Phase 2) |
| Knowledge base: text cleaning, chunking, local embeddings (Ollama `nomic-embed-text`) | Done (Phase 3) |
| Semantic search: cosine similarity over stored embeddings (admin test endpoint) | Done (Phase 4) |
| AI answers (RAG) with local `llama3.2:3b`, grounded in the knowledge base; customer "Ask support" | Done (Phase 5) |
| Human handoff: "Talk to Human Support" turns an unanswered question into a normal ticket with its AI context | Done (Phase 6) |
| Frontend (HTML / CSS / JavaScript) | Done — customer, agent and admin interfaces, with a token-based design system ([docs/design-system.md](docs/design-system.md)) |
| AI ticket analysis and response assistance | Not started |
| AWS and Amazon Connect | Not started |

## Run the backend (Windows)

```powershell
cd backend
python -m venv .venv                      # once
.\.venv\Scripts\activate
pip install -r requirements.txt           # once

copy .env.example .env                    # then edit .env: DATABASE_URL and JWT_SECRET_KEY
# create an empty database in PostgreSQL first, e.g.  CREATE DATABASE support_db;

alembic upgrade head                      # creates the tables
python create_admin.py                    # creates the first admin account
uvicorn app.main:app --reload             # http://127.0.0.1:8000/docs
```

Then open **http://127.0.0.1:8000/app/** for the web interface. FastAPI serves the frontend, so one server runs everything.

- `GET /health` checks the API, `GET /health/db` checks the database connection.
- Interactive API docs (Swagger): http://127.0.0.1:8000/docs. Use **Authorize** with the admin email as the username.

## Run the tests

```powershell
cd backend
.\.venv\Scripts\activate
pytest
```
Tests use an in-memory SQLite database, so they never touch your PostgreSQL data,
and a fake Ollama, so they never need Ollama running.

Embeddings and answers need Ollama with two models: `ollama pull nomic-embed-text` and
`ollama pull llama3.2:3b` (once).
If Ollama is not running, uploads still work; the document shows *Not indexed* and can be
retried from the Knowledge base screen.

Retrieval-quality tests use the real model, so they are opt-in (they need Ollama running):

```powershell
$env:RUN_OLLAMA_TESTS = "1"; pytest tests/test_retrieval_quality.py
```

## Folders

| Folder | Purpose |
|---|---|
| `backend/app/api` | HTTP endpoints (routers) and login/permission dependencies |
| `backend/app/schemas` | Pydantic models: what the API accepts and returns |
| `backend/app/services` | Business rules (who may do what, allowed status changes) |
| `backend/app/models` | SQLAlchemy models = database tables |
| `backend/app/database` | Engine, session, base class |
| `backend/app/core` | Settings and security (hashing, JWT) |
| `backend/alembic` | Database migrations |
| `backend/tests` | Automated tests |
| `python-prototype` | Original CLI prototype |
| `docs` | Project documentation |
| `frontend/css` | `tokens.css` (design tokens) and `app.css` (components) |
| `frontend/js` | `ui.js` (components), `common.js` (API and session), one script per page |
| `frontend/fonts` | Self-hosted Plus Jakarta Sans, so the app works offline |

See [docs/database.md](docs/database.md) and [docs/api.md](docs/api.md).
