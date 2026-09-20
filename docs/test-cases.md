# Test cases

Automated tests: `cd backend; pytest`. Last run: **34 passed** (2026-09-20), using in-memory SQLite.
Not yet covered: PostgreSQL-specific behaviour, frontend, AI, AWS (none built yet).

## Authentication (`tests/test_auth.py`, 9 tests)

| Case | Expected |
|---|---|
| Health endpoint | `{"status": "ok"}` |
| Register with valid data | 201, role CUSTOMER, no password in response |
| Register duplicate email (different letter case) | 409 |
| Register with short password / bad email / short name | 422 |
| Register with `"role": "ADMIN"` in the body | Ignored; account is CUSTOMER |
| Login then `/auth/me` | 200, correct user |
| Wrong password vs unknown email | Both 401 with identical message |
| No token / garbage token | 401 |
| Disabled user: login and old token | Login 403, old token 401 |

## Tickets and authorization (`tests/test_tickets.py`, 18 tests)

| Case | Expected |
|---|---|
| Customer lists tickets | Only their own |
| New ticket defaults | OPEN, MEDIUM, unassigned |
| Too-short title/description; unknown category | 422; 400 |
| Customer B reads or replies to customer A's ticket | 404 |
| No token; agent creates ticket | 401; 403 |
| Customer changes status / priority, assigns, escalates | 403 |
| Agent's default list vs `unassigned=true` queue; claiming | Own only; queue works; claim OK |
| Agent replies or changes status before claiming | 403 |
| Agent opens or steals another agent's ticket | 404 |
| Agent reassigns own ticket; admin assigns any; unknown agent | 200; 200; 404 |
| Conversation and automatic status changes | OPEN to IN_PROGRESS on agent reply; back to IN_PROGRESS on customer reply |
| Resolve / close / reopen rules; closed ticket | OPEN to CLOSED gives 409; closed ticket rejects messages, status changes, assignment (409) |
| Priority change; empty or invalid update | 200; 422 |
| Escalation with short / valid reason | 422; ESCALATED plus a message |
| Unknown ticket ID | 404 |
| List filters (status, priority, unassigned, invalid value) | Filtered; 422 for invalid |

## Admin (`tests/test_admin.py`, 7 tests)

| Case | Expected |
|---|---|
| Customer and agent call admin endpoints; no token | 403; 401 |
| Admin creates agent; agent logs in; duplicate email | 201; role AGENT; 409 |
| Admin lists users and filters by role | Correct counts |
| Admin disables self; unknown user | 400; 404 |
| Category create, duplicate name, deactivate, customer view, unknown id | 201, 409, customers see only active, 404; inactive category rejected for new ticket (400) |
| Stats | Correct totals |
| Admin reads any ticket | 200 |

## Manual tests still to do

- Full flow in Swagger (`/docs`) against real PostgreSQL.
- Postman collection.
- Database failure behaviour (stop PostgreSQL, check `/health/db` returns 503).
