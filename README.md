# AI-Powered Customer Support and Complaint Management System

BCA-507 Minor Project. Customers raise complaints, support agents resolve them, admins manage the system.

## Current status

| Part | Status |
|---|---|
| Python CLI prototype (`python-prototype/`) | Done |
| Backend: FastAPI + PostgreSQL + SQLAlchemy + Alembic | Done |
| Authentication (bcrypt + JWT) and role-based access | Done |
| Core ticket management (customer / agent / admin APIs) | Done |
| Automated tests (pytest) | 35 passing (see [docs/test-cases.md](docs/test-cases.md)) |
| Frontend (HTML / CSS / JavaScript) | Done — customer, agent and admin interfaces |
| AI analysis and response assistance | Not started |
| Knowledge base / RAG | Not started |
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
Tests use an in-memory SQLite database, so they never touch your PostgreSQL data.

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
| `frontend` | Reserved for the web interface |

See [docs/database.md](docs/database.md) and [docs/api.md](docs/api.md).
