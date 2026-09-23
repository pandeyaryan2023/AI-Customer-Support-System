# API reference

Base URL (development): `http://127.0.0.1:8000`. The live, interactive version is at `/docs`.
Authenticated endpoints need the header `Authorization: Bearer <token>`.

## Health

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/health` | anyone | API is running |
| GET | `/health/db` | anyone | Database connection works |

## Businesses (multi-tenancy)

Every user belongs to exactly one business, and everything below only ever shows or changes
data of the caller's own business. The business is never taken from a request: it comes from
the signed-in user (the login token carries it as `bid`, and it must match the user's record).
A resource of another business behaves exactly like one that does not exist (404), and an id
from another business (a category, an agent, a handoff) is refused.

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/businesses` | anyone | Create a business and its first admin: `business_name`, `business_slug` (its public code), `full_name`, `email`, `password` |
| GET | `/businesses/{slug}` | anyone | A business's name for its code (for the sign-up page) |

## Authentication

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/auth/register` | anyone | Register as a customer of a business (JSON: full_name, email, password, `business` = its code) |
| POST | `/auth/login` | anyone | Login (form fields: `username` = email, `password`); returns token, role, business name |
| GET | `/auth/me` | any logged-in user | Current user, with their business |

## Tickets

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/tickets` | customer | Create a complaint (optionally from an AI handoff, see below) |
| GET | `/tickets` | any | List tickets visible to you. Filters: `status`, `priority`, `unassigned=true` |
| GET | `/tickets/{id}` | owner / assigned agent / unassigned (agents) / admin | Details with messages |
| POST | `/tickets/{id}/messages` | ticket owner, assigned agent, admin | Send a message |
| PATCH | `/tickets/{id}` | assigned agent, admin | Change status (e.g. RESOLVED), priority, category |
| POST | `/tickets/{id}/assign` | agent (claim unassigned / hand over own), admin | Assign or reassign |
| POST | `/tickets/{id}/escalate` | assigned agent, admin | Escalate with a reason |
| POST | `/tickets/{id}/ai-analysis` | agent, admin who can view the ticket | AI suggestions (nothing is changed or sent) |

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

## AI ticket analysis

`POST /tickets/{id}/ai-analysis` (no body) returns suggestions from the local `llama3.2:3b`:

```json
{"category": {"id": 3, "name": "Refunds"}, "priority": "HIGH", "sentiment": "negative",
 "summary": "...", "suggested_reply": "...", "model": "llama3.2:3b", "ignored_instructions": false}
```

Customers get 403; an agent gets 404 for a ticket they may not view (the same rule as
`GET /tickets/{id}`). The model reads the title, the description (up to 300 words), the last 8
messages as "Customer" / "Support agent" (up to 120 words each, 1,000 in total) and the current
category and priority: no names, emails or ids. Its answer is forced into a JSON schema and then
checked again: `category` is only ever an **active existing** category (anything else, including an
invented name, becomes null), `priority` one of LOW / MEDIUM / HIGH / URGENT, `sentiment` one of
positive / neutral / negative; any field without a usable value is null. Sentences in the ticket
addressed to the AI ("ignore your instructions...") are left out of what the model reads, and
`ignored_instructions` tells the agent this happened. Nothing is stored and nothing is changed or
sent: the agent applies a suggestion with the normal `PATCH /tickets/{id}` and sends a reply with
the normal `POST /tickets/{id}/messages`. If the model is unavailable or returns nothing usable, the
response is 503 with a generic message.

## AI assistant

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/ai/ask` | customer, admin | Answer a customer's message, from the knowledge base or as a general question |

Body: `{"question": "Can I get a refund after 20 days?"}` (2–500 characters; any other field is
rejected with 422, so a client cannot pass rules, context, a model — or an intent). Response:

```json
{"intent": "COMPANY_KNOWLEDGE",
 "status": "ANSWERED",
 "answer": "You can request a refund within 30 days of purchase...",
 "sources": [{"document_title": "Customer support knowledge base", "chunk_index": 0, "similarity": 0.656}],
 "model": "llama3.2:3b"}
```

`intent` is what the message was, decided by the server before anything else runs:

| Intent | What happens | Answer | Sources |
|---|---|---|---|
| `COMPANY_KNOWLEDGE` | The knowledge base is searched and the answer is grounded in it, exactly as before | From the articles | The articles used |
| `GENERAL` | Nothing to do with this business: the model answers from general knowledge and is told to say nothing about the shop. The knowledge base is never searched | General | Always empty |
| `COMPLAINT` | Something has gone wrong: a fixed acknowledgement. **No ticket is created** | Fixed text, `model` null | Empty |
| `HUMAN_HANDOFF` | The customer asked for a person: a fixed reply pointing at the complaint form | Fixed text, `model` null | Empty |

The decision is a separate `llama3.2:3b` call constrained to a JSON schema
(`intent`, `confidence`, `reason`), not a similarity score, so "Do you sell gift cards?" is a
company question even when no article mentions gift cards. The message is passed as data inside a
`<message>` block. Anything unusable — not JSON, an intent outside the four, or Ollama being
down — falls back to `COMPANY_KNOWLEDGE`, the careful path, which only repeats stored company
text and refuses when it cannot. The model's `confidence` and `reason` stay on the server (log
only) and are never part of the response.

`status` is `ANSWERED` or `NOT_ENOUGH_INFORMATION` (a fixed reply, no sources). The second happens
when search finds nothing relevant (the model is **not** called; `model` is null), when the
model says it cannot answer, or when its answer contains a number that appears nowhere in the
retrieved knowledge or the question. Retrieved text is treated as data: sentences addressed to
the AI ("ignore previous instructions", "note for the assistant", "SYSTEM:"...) are removed
before the model sees it. If search or the model is unavailable the response is **503** with a
generic message; the real reason is only written to the server log.

A `NOT_ENOUGH_INFORMATION` reply to a customer also carries a `handoff_token` — including the
complaint and "I want a person" replies, which use the same route. Nothing is
stored and no ticket is created unless the customer chooses "Talk to Human Support", which
sends the normal `POST /tickets` body plus `"handoff_token": "..."`. The token is signed by the
server (audience `ai-handoff`, so it can never be used to log in), tied to the customer who
asked, and valid for `handoff_token_expire_minutes` = 60. The ticket's AI context is taken from
the token, never from the form. A token that is forged, tampered with, expired or someone
else's gives **400** and creates nothing. Sending the same token twice returns the same ticket
(one ticket per handoff, enforced by a unique index).

Every ticket response now has `from_ai_handoff` (true / false) and `ai_handoff` (null, or
`question`, `ai_status`, `reason`, `sources` [title, chunk_index, similarity], `asked_at`).
It never contains the prompt or article text.

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
