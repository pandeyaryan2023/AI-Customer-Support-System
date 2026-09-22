# Test cases

Automated tests: `cd backend; pytest`. Last run: **35 passed** (2026-09-20), using in-memory SQLite.
Not yet covered by pytest: PostgreSQL-specific behaviour, AI, AWS (none built yet).

## Browser walkthrough (scripted, Microsoft Edge)

Re-run after the visual redesign on 2026-09-20: **29 checks, all passed, 0 console errors.**
The only non-2xx server responses were the five deliberate negative tests
(wrong password 401, foreign ticket 404, short escalation reason 422, duplicate category 409,
disabled account 403).

Added by the redesign run: complaint creation through the slide-over panel, the lifecycle
pipeline, a customer being redirected away from `admin.html`, logout, Escape closing the
slide-over, the mobile drawer, and no horizontal overflow at 1440 / 1280 / 1024 / 768 / 480 / 390 px.

The table below lists the original fourteen cases; all still pass.

| Case | Expected | Result |
|---|---|---|
| Register with mismatched passwords, then matching | Error shown; then account created | Pass |
| Login with wrong password | "Incorrect email or password" | Pass |
| Customer raises a complaint with a category | Appears in list as OPEN / MEDIUM | Pass |
| Customer opens own ticket, sends a message | No "Manage ticket" panel; message sent | Pass |
| Another customer opens that ticket URL directly | "Ticket not found" | Pass |
| Agent's own list vs unassigned queue; claim | Empty; queue shows it; claim works | Pass |
| Agent escalates with a 2-character reason | Rejected (422) | Pass |
| Agent replies | Status becomes IN_PROGRESS | Pass |
| Agent sets priority URGENT, escalates with a reason | ESCALATED plus "[Escalated]" message | Pass |
| Agent resolves then closes | Closed ticket refuses further messages | Pass |
| Admin creates duplicate category ("delivery" vs "Delivery") | "already exists" | Pass |
| Admin creates an agent | Agent listed | Pass |
| Admin disables a customer, customer tries to log in, admin re-enables | Login refused ("disabled"); works after re-enabling | Pass |
| Every page at 400px width | No sideways scrolling | Pass |

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

## Knowledge base (`tests/test_documents.py`, 18 tests)

| Case | Expected |
|---|---|
| Admin uploads a PDF | 201; file saved under a generated name; stored filename not exposed |
| Admin uploads a UTF-8 text file | 201, `text/plain` |
| List | Newest first |
| Filenames `../../../etc/evil.pdf`, `..\..\windows\evil.pdf`, `C:\Users\...\refund.pdf` | Shown as the bare name; file stays inside the storage folder |
| `virus.exe`, `invoice.pdf.exe` | 415, nothing saved |
| Text file renamed `fake.pdf` | 415, nothing saved |
| Binary content in a `.txt` | 415, nothing saved |
| Empty file | 400, nothing saved |
| File over the size limit | 413, nothing saved |
| Title empty, blank, 1 character, 201 characters | 422 |
| Customer or agent calls upload / list / delete; no token | 403; 401 |
| Delete | 204; row and file removed; second delete 404 |

Browser check of the Knowledge base screen (Edge, 2026-09-22): empty state, upload of a PDF
and a text file, fake PDF rejected by the server, `.exe` blocked in the browser before any
request, delete, no overflow at 390 px — all passed, 0 console errors.

## Manual tests still to do

- Full flow in Swagger (`/docs`) against real PostgreSQL.
- Postman collection.
- Database failure behaviour (stop PostgreSQL, check `/health/db` returns 503).
