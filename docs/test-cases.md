# Test cases

Automated tests: `cd backend; pytest`. Last run: **189 passed, 20 skipped** (2026-09-22), using
in-memory SQLite and a fake Ollama (`tests/conftest.py`), so no test needs Ollama running.
The 20 skipped are the opt-in real-model tests (`RUN_OLLAMA_TESTS=1`): **20 passed** when run.
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

## Text extraction (`tests/test_text_extraction.py`, 21 tests)

| Case | Expected |
|---|---|
| Two-page PDF (extractor alone) | Both pages' text, separated by a blank line; `page_count` 2 |
| UTF-8 text with BOM, `₹`, `–` and Windows line endings | Text intact, BOM removed, `
` becomes `
` |
| Corrupted PDF, zero pages, blank page (scan), password-protected | `ExtractionError` with a matching reason |
| Text file in Latin-1, in UTF-16, or only whitespace | `ExtractionError` with a matching reason |
| Stored file missing | "The stored file is missing" |
| NUL characters in extracted text | Removed (PostgreSQL cannot store them) |
| Upload a valid PDF / text file | 201, `EXTRACTED`; `/text` returns the content; lists omit the text |
| Upload a corrupted PDF, a scanned PDF, a blank text file | 201 but `FAILED` with the reason; original kept byte for byte; `/text` 409 |
| The PDF library raises an unexpected error (`KeyError`) | 201, `FAILED`, "Unexpected error while reading the file"; no 500 |
| Document stored before Phase 2 | Listed as `PENDING`; `POST /extract` makes it `EXTRACTED` |
| Retry: file missing, then restored | `FAILED` (old text cleared), then `EXTRACTED` |
| Customer or agent calls `/extract` or `/text`; no token | 403; 401 |
| Unknown document | 404 |

Manual check (Edge, against a scratch PostgreSQL database, 2026-09-22): 15 checks passed,
0 console errors. `Customer_Support_Knowledge_Base_Test.pdf` extracted to 1 page, 512
characters, including "Customers can request a refund within 30 days of purchase."
A document stored before Phase 2 was extracted with the **Extract text** button; a damaged
and a scanned PDF were kept as Failed with their reasons, and **Retry** failed cleanly again;
a UTF-8 text file kept `₹` and `–`; no page overflow at 390 px.

## Cleaning and chunking (`tests/test_chunking.py`, 25 tests)

| Case | Expected |
|---|---|
| Ligatures, non-breaking spaces, soft hyphens, zero-width characters, NUL, control characters | Removed or normalised |
| Tabs, repeated spaces, 4+ blank lines, Windows line endings | Tidied |
| Punctuation, `₹`, `–`, Hindi, German, Chinese, curly quotes | Unchanged; cleaning twice = cleaning once |
| Normal text / short text / 1,200 words at 500/75 | Whole sentences per chunk / 1 chunk / 3 chunks, nothing lost |
| Overlap 20 words, overlap 0 | Next chunk repeats the last two sentences / shares nothing |
| One 30-word "sentence" with no punctuation at 10/3 | Split by words, exactly 3 words shared |
| Line break inside a sentence | Sentence kept whole |
| The test PDF's text | 1 chunk at 500 words; at 30 words, 3 chunks starting at its 3 headings |
| Empty or whitespace-only text | No chunks |
| Indexes, order, word counts, same input twice, invalid sizes | 0..n-1 in reading order, exact counts, identical, ValueError |

## Embedding client (`tests/test_embedding_client.py`, 18 tests)

| Case | Expected |
|---|---|
| Two texts; request body; 20 texts | Two vectors in order; model, `search_document: ` prefix, `truncate: false`; batches of 16 and 4 |
| Ollama not running; timeout; model not installed (404); other error (400) | `EmbeddingError` with a readable reason |
| Not JSON, missing key, wrong shape, wrong count, empty or null vector, 384 numbers | `EmbeddingError`; nothing returned |
| A string, boolean, NaN or null inside the vector | `EmbeddingError` |

## Indexing pipeline (`tests/test_indexing.py`, 22 tests)

| Case | Expected |
|---|---|
| Upload text / PDF | `INDEXED`, 1 chunk; `/chunks` shows 768 numbers, a preview, never the full vector |
| Stored vector | Exactly the numbers Ollama returned |
| Long document at 20/5 words | Several chunks, indexes 0..n-1, sent to Ollama in the same order |
| Re-index twice; re-index at a new chunk size | Still one chunk 0; exactly the new set, old chunk gone |
| Re-index one document | Other documents' chunks untouched |
| Re-extraction fails, then succeeds | Chunks removed (`NOT_INDEXED`), then rebuilt |
| Ollama unavailable at upload | 201, text kept and viewable, `FAILED` with reason, no chunks |
| Ollama back, retry | `INDEXED` |
| Re-index fails after a success | Old chunks removed: chunks exist only when `INDEXED` |
| Malformed, empty or wrong-dimension embeddings | `FAILED`, nothing saved |
| Unexpected error while chunking | `FAILED`, "Unexpected error while indexing"; no 500 |
| Extraction failed; text only invisible characters | Not indexed, Ollama never called; `/index` 409 / `FAILED` |
| Delete document | Its chunks deleted |
| Database fails at commit | Rolled back: the previous chunk and status unchanged, even in the same session |
| Customer or agent calls `/index`, `/chunks`; no token; unknown id | 403; 401; 404 |

Manual check (2026-09-22, scratch PostgreSQL database, real Ollama `nomic-embed-text`, Edge):
`Customer_Support_Knowledge_Base_Test.pdf` gave 1 chunk (81 words) with a 768-number JSONB
vector identical to a fresh Ollama call; three re-runs left exactly 1 chunk row; at 30/15
words it gave 5 sequential chunks; an unreachable Ollama gave `FAILED` with no chunks and
**Retry indexing** in the browser fixed it. 12/12 API/database checks and 9/9 browser checks
passed, 0 console errors, no overflow at 390 px.

## Vector maths (`tests/test_vector_math.py`, 18 tests)

| Case | Expected |
|---|---|
| Known angle, identical, scaled, orthogonal, opposite vectors | 0.7071, 1, 1, 0, -1 |
| Matrix version vs the formula row by row (768 dimensions) | Equal |
| Mismatched dimensions; zero question or zero stored vector | ValueError |
| Ranking; threshold (inclusive); top_k; nothing above threshold; no scores; ties | Highest first; filtered; cut; empty; empty; original order |
| Stored vectors that are missing, text, a dict, too short, non-numeric, NaN, all zero | Left out of the matrix |

## Search service and API (`tests/test_search.py`, 32 tests)

Chunks are seeded with vectors along known axes, so the right scores are known exactly.

| Case | Expected |
|---|---|
| Mostly-refund question | Only the refund chunk (0.909 >= 0.55); exact fields; no vectors or file names |
| threshold 0 | All chunks, highest first, scores 0.909 / 0.404 / 0.101 |
| Question sent to Ollama | Trimmed, with `search_query: ` prefix |
| Two documents | Both can appear, ranked together |
| threshold 0.95 / 0.55 / 0.3 / 0; top_k 2 / 1; settings changed | 0 / 1 / 2 / 3 results; 2 / 1; defaults follow settings |
| top_k 0 or 21, threshold -0.1 or 1.5, top_k "many" | 422 |
| Unrelated question | `NO_MATCH`, no results, best_similarity 0 |
| Empty knowledge base; only FAILED documents | `NO_INDEXED_DOCUMENTS`, Ollama not called |
| FAILED, NOT_INDEXED, extraction-failed and other-model chunks that match perfectly | Never returned |
| Query empty, blank, 1 character, 501 characters, missing | 422 |
| Extra field (`business_id`, `document_ids`, `scope`) | 422 |
| Ollama down; question vector wrong size, empty or all zeros | 503 with the reason |
| Damaged stored vectors; all stored vectors damaged | Skipped and counted; 503 "Re-index" |
| Database fails while loading chunks | 503 "The knowledge base could not be read" |
| Customer or agent; no token | 403; 401 |

## Retrieval quality with the real model (`tests/test_retrieval_quality.py`, 20 tests, opt-in)

The test PDF's text is indexed for real, at the default size (1 chunk) and at one chunk per section.
Six answerable questions must find their section (ranked first when sections are separate chunks);
three unrelated questions must return `NO_MATCH`; threshold 0.9 must reject a real match.

Manual check (2026-09-22, scratch PostgreSQL, real `nomic-embed-text`, the test PDF, default settings):

| Question | Top result | Similarity | Threshold | Result |
|---|---|---:|---:|---|
| Can I get my money back after 20 days? | chunk 0 (whole document) | 0.656 | 0.55 | FOUND |
| What is the company's refund time limit? | chunk 0 (whole document) | 0.789 | 0.55 | FOUND |
| How long does delivery take? | chunk 0 (whole document) | 0.667 | 0.55 | FOUND |
| When is customer support available? | chunk 0 (whole document) | 0.729 | 0.55 | FOUND |
| What is the capital of France? | (chunk 0 scored 0.387) | 0.387 | 0.55 | NO_MATCH |

With one chunk per section the top chunk was the right section every time (0.664, 0.784, 0.781,
0.828; France 0.425). A FAILED document was not searched, an unreachable Ollama gave
SearchUnavailable, and each search took about 0.4–0.5 s. 9/9 checks passed.

## Manual tests still to do

- Full flow in Swagger (`/docs`) against real PostgreSQL.
- Postman collection.
- Database failure behaviour (stop PostgreSQL, check `/health/db` returns 503).
