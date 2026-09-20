# API reference

Base URL (development): `http://127.0.0.1:8000`. The live, interactive version is at `/docs`.
Authenticated endpoints need the header `Authorization: Bearer <token>`.

## Health

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/health` | anyone | API is running |
| GET | `/health/db` | anyone | Database connection works |

## Authentication

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/auth/register` | anyone | Register as a customer (JSON: full_name, email, password) |
| POST | `/auth/login` | anyone | Login (form fields: `username` = email, `password`); returns token, role |
| GET | `/auth/me` | any logged-in user | Current user |

## Tickets

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/tickets` | customer | Create a complaint |
| GET | `/tickets` | any | List tickets visible to you. Filters: `status`, `priority`, `unassigned=true` |
| GET | `/tickets/{id}` | owner / assigned agent / unassigned (agents) / admin | Details with messages |
| POST | `/tickets/{id}/messages` | ticket owner, assigned agent, admin | Send a message |
| PATCH | `/tickets/{id}` | assigned agent, admin | Change status (e.g. RESOLVED), priority, category |
| POST | `/tickets/{id}/assign` | agent (claim unassigned / hand over own), admin | Assign or reassign |
| POST | `/tickets/{id}/escalate` | assigned agent, admin | Escalate with a reason |

## Categories and admin

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/categories` | any logged-in user | Active categories |
| GET | `/admin/users` | admin | All users (`?role=`) |
| PATCH | `/admin/users/{id}` | admin | Enable / disable an account |
| GET, POST | `/admin/agents` | admin | List / create agents |
| GET, POST | `/admin/categories` | admin | List all / create category |
| PATCH | `/admin/categories/{id}` | admin | Rename, describe, activate / deactivate |
| GET | `/admin/stats` | admin | Ticket, priority and user counts |

## Status change rules

```
OPEN                 -> IN_PROGRESS, WAITING_FOR_CUSTOMER, ESCALATED, RESOLVED
IN_PROGRESS          -> WAITING_FOR_CUSTOMER, ESCALATED, RESOLVED
WAITING_FOR_CUSTOMER -> IN_PROGRESS, ESCALATED, RESOLVED
ESCALATED            -> IN_PROGRESS, RESOLVED
RESOLVED             -> IN_PROGRESS (reopen), CLOSED
CLOSED               -> (final)
```
An invalid change returns `409`. An agent's first reply moves OPEN to IN_PROGRESS; a customer reply moves WAITING_FOR_CUSTOMER back to IN_PROGRESS.

## Common status codes

`200` OK, `201` created, `400` bad reference (e.g. unknown category), `401` not logged in or bad token, `403` logged in but not allowed, `404` not found (also used when a ticket exists but you may not see it), `409` conflict (duplicate email, invalid status change, closed ticket), `422` invalid input.

## Known limitations

- Escalation reasons are stored as a normal message, so the customer can see them. There is no internal-notes feature yet.
- Escalation only sets the status; there is no separate "escalation queue" or manager role.
- No password reset, email notifications or token refresh yet.
- No rate limiting on login.
