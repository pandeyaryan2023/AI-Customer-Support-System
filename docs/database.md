# Database design

PostgreSQL, accessed through SQLAlchemy, created by Alembic migrations
`0001_create_core_tables` and `0002_add_documents_table`.

## Tables

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Everyone who can log in | `id` PK, `email` (unique), `hashed_password`, `role` (CUSTOMER / AGENT / ADMIN), `is_active` |
| `agents` | Extra details for agent users (1-to-1 with `users`) | `id` PK, `user_id` FK -> users (unique), `department` |
| `categories` | Complaint categories managed by the admin | `id` PK, `name` (unique), `is_active` |
| `tickets` | Customer complaints | `id` PK, `customer_id` FK -> users, `assigned_agent_id` FK -> agents (nullable), `category_id` FK -> categories (nullable), `status`, `priority` |
| `ticket_messages` | Conversation on a ticket | `id` PK, `ticket_id` FK -> tickets, `sender_id` FK -> users, `message` |
| `documents` | Knowledge-base files (the bytes are on disk, not in the database) | `id` PK, `title`, `original_filename` (display only), `stored_filename` (unique, generated), `content_type`, `size_bytes`, `uploaded_by_id` FK -> users |

## Relationships

- A customer (user) **raises** many tickets. `tickets.customer_id -> users.id`
- An agent is **assigned** many tickets; a ticket has at most one agent. `tickets.assigned_agent_id -> agents.id`
- A ticket **belongs to** at most one category. `tickets.category_id -> categories.id`
- A ticket **has** many messages, each **sent by** one user.
- A user **may have** one agent profile (only when their role is AGENT).
- An admin **uploads** many documents. `documents.uploaded_by_id -> users.id`

Uploaded files are stored in `backend/storage/documents/` under a random name
(`stored_filename`), never under the uploader's filename. That folder is outside
`frontend/`, so it is not publicly served, and it is excluded from Git.

## Enumerated values (stored as text)

- Ticket status: OPEN, IN_PROGRESS, WAITING_FOR_CUSTOMER, ESCALATED, RESOLVED, CLOSED
- Priority: LOW, MEDIUM, HIGH, URGENT
- Role: CUSTOMER, AGENT, ADMIN

## Indexes

`users.email` (unique), `tickets.status`, `tickets.customer_id`, `tickets.assigned_agent_id`, `ticket_messages.ticket_id`. These columns are used in almost every query filter.

## Compared with the synopsis ER diagram

**To check against your submitted ER diagram** (I have not seen the diagram itself):

- `USERS`, `AGENTS`, `TICKETS`, `TICKET_MESSAGES` are implemented as listed.
- `CATEGORIES` is an **addition**: the synopsis says the admin manages categories, which needs its own table. If your ER diagram has no such entity, add it to the diagram.
- `AI_ANALYSIS` is **not created yet**. It will be added, with its own migration, when the AI module is built.
