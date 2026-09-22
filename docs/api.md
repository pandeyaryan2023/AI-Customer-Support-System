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
| GET | `/agents` | agent, admin | Active agents (names only), for assignment drop-downs |
| GET | `/admin/users` | admin | All users (`?role=`) |
| PATCH | `/admin/users/{id}` | admin | Enable / disable an account |
| GET, POST | `/admin/agents` | admin | List / create agents |
| GET, POST | `/admin/categories` | admin | List all / create category |
| PATCH | `/admin/categories/{id}` | admin | Rename, describe, activate / deactivate |
| GET | `/admin/stats` | admin | Ticket, priority and user counts |

## Knowledge base

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/admin/documents` | admin | Upload a document. `multipart/form-data` with `title` and `file` |
| GET | `/admin/documents` | admin | List documents, newest first |
| DELETE | `/admin/documents/{id}` | admin | Remove the document and its file (204) |
| POST | `/admin/documents/{id}/extract` | admin | Extract (or re-extract) the text of a stored document |
| GET | `/admin/documents/{id}/text` | admin | The extracted text (409 if the document has none) |
| POST | `/admin/documents/{id}/index` | admin | Chunk and embed again, replacing old chunks (409 if no text) |
| GET | `/admin/documents/{id}/chunks` | admin | Stored chunks in order, with each vector's length and first 8 numbers |

Upload rules: `.pdf` or `.txt` only (415 otherwise); the bytes must match the extension —
a PDF must start with `%PDF-`, text must be UTF-8 (415); not empty (400); at most
`max_upload_mb`, default 10 MB (413); title 2–200 characters (422).
The uploader's filename is kept for display only; the file is saved under a generated name.
`DELETE` exists for documents only: an outdated policy must stop being used as a source.

Text extraction runs straight after every upload. The upload succeeds even when extraction
fails: the document keeps its file and gets `status` `FAILED` with the reason in
`extraction_error` (damaged PDF, password-protected, no pages, no text layer such as a scan,
not UTF-8, empty). `status` is `PENDING` (not extracted yet, e.g. uploaded before Phase 2),
`EXTRACTED` or `FAILED`. Document lists never include the text itself; use `/text`.

After extraction the text is cleaned, split into chunks of whole sentences (up to
`chunk_words` = 500 words, neighbours sharing up to `chunk_overlap_words` = 75 words) and
embedded by the local Ollama model `nomic-embed-text` (768 numbers per chunk).
`index_status` is `NOT_INDEXED`, `INDEXED` or `FAILED` (reason in `index_error`, e.g. Ollama
not running, model not installed, invalid reply). A document has chunks only when it is
`INDEXED`; re-indexing replaces its chunks in one transaction, so they are never duplicated.
A failed indexing never fails the upload, and never touches the file or the extracted text.

## Semantic search

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/admin/documents/search` | admin | Find the chunks closest in meaning to a question (retrieval only, no answer) |

Body: `{"query": "Can I get my money back after 20 days?", "top_k": 3, "threshold": 0.55}`.
`query` is 2–500 characters; `top_k` (1–20) and `threshold` (0–1) are optional and default to
`search_top_k` = 3 and `search_similarity_threshold` = 0.55 (an *initial prototype threshold*,
measured on the test knowledge base). Any other field is rejected (422), so a request cannot
choose which knowledge base it searches.

The question is embedded with the `search_query: ` prefix (documents use `search_document: `),
compared by cosine similarity with every chunk of an `INDEXED` document made by the same model,
ranked highest first, filtered by the threshold and cut to `top_k`.

The response has `outcome`: `FOUND`, `NO_MATCH` (nothing reached the threshold; `results` is
empty, never low-scoring chunks) or `NO_INDEXED_DOCUMENTS`; a `message`; the `top_k` and
`threshold` used; `chunks_searched`, `chunks_skipped` (damaged vectors left out), `best_similarity`;
and `results`: `chunk_id`, `document_id`, `document_title`, `chunk_index`, `text`, `similarity`.
No vectors, stored filenames or paths are returned. If Ollama or the database is unavailable the
response is **503** with the reason, never an empty result.

## AI assistant

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/ai/ask` | customer, admin | Answer a question from the knowledge base only |

Body: `{"question": "Can I get a refund after 20 days?"}` (2–500 characters; any other field is
rejected with 422, so a client cannot pass rules, context or a model). Response:

```json
{"status": "ANSWERED",
 "answer": "You can request a refund within 30 days of purchase...",
 "sources": [{"document_title": "Customer support knowledge base", "chunk_index": 0, "similarity": 0.656}],
 "model": "llama3.2:3b"}
```

`status` is `ANSWERED` or `NOT_ENOUGH_INFORMATION` (a fixed reply, no sources). The second happens
when search finds nothing relevant (the model is **not** called; `model` is null), when the
model says it cannot answer, or when its answer contains a number that appears nowhere in the
retrieved knowledge or the question. Retrieved text is treated as data: sentences addressed to
the AI ("ignore previous instructions", "note for the assistant", "SYSTEM:"...) are removed
before the model sees it. If search or the model is unavailable the response is **503** with a
generic message; the real reason is only written to the server log.

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
