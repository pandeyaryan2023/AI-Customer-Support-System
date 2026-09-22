# Database design

PostgreSQL, accessed through SQLAlchemy, created by Alembic migrations
`0001_create_core_tables`, `0002_add_documents_table`, `0003_add_document_text_extraction`, `0004_add_document_chunks` and
`0005_add_ticket_ai_handoff` and `0006_add_businesses_multi_tenancy`.

## Tables

| Table | Purpose | Key columns |
|---|---|---|
| `businesses` | The companies using the service (tenants) | `id` PK, `name`, `slug` (unique public code), `is_active`, `created_at` |
| `users` | Everyone who can log in | `id` PK, `business_id` FK -> businesses, `email` (unique across all businesses), `hashed_password`, `role` (CUSTOMER / AGENT / ADMIN), `is_active` |
| `agents` | Extra details for agent users (1-to-1 with `users`) | `id` PK, `user_id` FK -> users (unique), `department` |
| `categories` | Complaint categories managed by the admin | `id` PK, `business_id` FK -> businesses, `name` (unique within the business), `is_active` |
| `tickets` | Customer complaints | `id` PK, `business_id` FK -> businesses (always the customer's), `customer_id` FK -> users, `assigned_agent_id` FK -> agents (nullable), `category_id` FK -> categories (nullable), `status`, `priority`, `handoff_id` (unique, nullable), `ai_handoff` (JSON, nullable) |
| `ticket_messages` | Conversation on a ticket | `id` PK, `ticket_id` FK -> tickets, `sender_id` FK -> users, `message` |
| `documents` | Knowledge-base files (the bytes are on disk, not in the database) | `id` PK, `business_id` FK -> businesses, `title`, `original_filename` (display only), `stored_filename` (unique, generated), `content_type`, `size_bytes`, `uploaded_by_id` FK -> users, `status` (PENDING / EXTRACTED / FAILED), `extracted_text`, `page_count`, `char_count`, `extraction_error`, `index_status` (NOT_INDEXED / INDEXED / FAILED), `chunk_count`, `index_error` |
| `document_chunks` | Pieces of a document's text with their embedding vectors | `id` PK, `document_id` FK -> documents (ON DELETE CASCADE), `chunk_index`, `text`, `word_count`, `embedding` (JSONB list of 768 numbers), `embedding_model`, `created_at`; unique (`document_id`, `chunk_index`) |

## Relationships

- A business **has** many users, categories, tickets and documents. Agents, ticket messages and
  document chunks belong to a business through their user, ticket and document, so they have no
  `business_id` of their own.
- A customer (user) **raises** many tickets. `tickets.customer_id -> users.id`
- An agent is **assigned** many tickets; a ticket has at most one agent. `tickets.assigned_agent_id -> agents.id`
- A ticket **belongs to** at most one category. `tickets.category_id -> categories.id`
- A ticket **has** many messages, each **sent by** one user.
- A user **may have** one agent profile (only when their role is AGENT).
- An admin **uploads** many documents. `documents.uploaded_by_id -> users.id`
- A document **is split into** many chunks. `document_chunks.document_id -> documents.id`

Uploaded files are stored in `backend/storage/documents/` under a random name
(`stored_filename`), never under the uploader's filename. That folder is outside
`frontend/`, so it is not publicly served, and it is excluded from Git.

The extracted text is stored in `documents.extracted_text` (PostgreSQL `text`). The model
loads that column only when it is read (`deferred`), so listing documents stays fast.
Migration 0003 gives existing rows `status = 'PENDING'`.

Embeddings are stored as JSONB lists (no pgvector, which is not available for this
PostgreSQL version). The unique (`document_id`, `chunk_index`) constraint makes the database
itself refuse duplicate chunks, and also indexes `document_id`. Chunks are never edited, only
replaced, so they have `created_at` and no `updated_at`. Migration 0004 gives existing
documents `index_status = 'NOT_INDEXED'`.

A ticket raised through "Talk to Human Support" stores the AI context in `tickets.ai_handoff`
(the original question, why the AI stopped, the articles it looked at) and the handoff's id in
`tickets.handoff_id`, whose unique index allows one ticket per handoff. Both are NULL for all
other tickets; migration 0005 changes no existing data.

Migration 0006 adds multi-tenancy without losing data: if the database already has rows, it
creates one business, "Default business" (code `default`), and moves every existing user,
category, ticket and document into it; then `business_id` becomes required. An empty database
gets no business. Category names become unique per business (`uq_categories_business_name`)
instead of across the system. Indexes: `users.business_id`, `tickets.business_id`,
`documents.business_id`; categories use their unique (`business_id`, `name`) index. Going back
(`alembic downgrade 0005`) works unless two businesses share a category name.

## Enumerated values (stored as text)

- Ticket status: OPEN, IN_PROGRESS, WAITING_FOR_CUSTOMER, ESCALATED, RESOLVED, CLOSED
- Priority: LOW, MEDIUM, HIGH, URGENT
- Role: CUSTOMER, AGENT, ADMIN
- Document status: PENDING, EXTRACTED, FAILED
- Index status: NOT_INDEXED, INDEXED, FAILED

## Indexes

`users.email` (unique), `tickets.status`, `tickets.customer_id`, `tickets.assigned_agent_id`, `ticket_messages.ticket_id`. These columns are used in almost every query filter.

## Compared with the synopsis ER diagram

**To check against your submitted ER diagram** (I have not seen the diagram itself):

- `USERS`, `AGENTS`, `TICKETS`, `TICKET_MESSAGES` are implemented as listed.
- `CATEGORIES` is an **addition**: the synopsis says the admin manages categories, which needs its own table. If your ER diagram has no such entity, add it to the diagram.
- `AI_ANALYSIS` is **not created yet**. It will be added, with its own migration, when the AI module is built.
