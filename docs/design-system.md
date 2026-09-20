# Design system

The interface is built from one token file and one component library. Nothing in the
application uses a raw colour, size or duration value.

| File | Role |
|---|---|
| `frontend/css/tokens.css` | Every colour, size, radius, shadow and duration |
| `frontend/css/app.css` | Components built only from those tokens |
| `frontend/js/ui.js` | The component library — shell, tables, badges, toasts, sheets |

## The idea

A support desk is about one question: **where is this complaint, and who holds it?**
So status is expressed as structure, not decoration:

- every ticket row carries a coloured left rail in its status colour;
- the ticket page opens with a lifecycle pipeline showing the current stage.

Everything else is kept deliberately quiet.

## Colour

The brand is a deep ink rather than a hue. That leaves the whole colour range free to
carry meaning, because the application already spends ten colours on status and priority.

| Token | Value | Use |
|---|---|---|
| `--ink` | `#131A26` | Sidebar, headings |
| `--ink-soft` | `#1E2938` | Sidebar hover and active item |
| `--canvas` | `#F5F6F8` | Page background |
| `--surface` | `#FFFFFF` | Cards, tables, inputs |
| `--line` | `#E4E7EC` | Borders and dividers |
| `--text` | `#1F2937` | Body text |
| `--text-muted` | `#667085` | Labels, timestamps |
| `--accent` | `#0E7C86` | Primary actions only |
| `--accent-hover` | `#0A616A` | Hover on primary actions |

Semantic colours stay meaningful: blue = open, amber = in progress, violet = waiting,
red = escalated, green = resolved, slate = closed.

**The rule that keeps ten colours calm:** badges are pale tints, buttons are solid fills.
An action can never be mistaken for a state.

## Typography

Plus Jakarta Sans, self-hosted in `frontend/fonts/` (49 KB, two Latin subsets), so the
application works with no internet connection.

| Role | Size | Weight |
|---|---|---|
| Statistic | 30px | 700 |
| Page title | 24px | 700 |
| Section heading | 16px | 600 |
| Body | 14px | 400 |
| Label | 13px | 500 |
| Metadata | 12px | 400 |

Numbers use `tabular-nums` so ticket IDs and counts line up in columns.

## Spacing, radius, elevation

**Spacing** — a 4px base: 4, 8, 12, 16, 20, 24, 32, 48.

**Radius** — `--r-sm` 6px (inputs, buttons), `--r-md` 10px (cards), `--r-lg` 14px
(drawers), `--r-full` (badges, avatars).

**Elevation** — three levels, each with a meaning, rather than one shadow on everything:

| Level | Meaning |
|---|---|
| Border only | Static content: stat tiles, table containers |
| `--shadow-raised` | Interactive surfaces: the ticket card, the manage panel |
| `--shadow-floating` / `--shadow-dialog` | Things that sit above the page: toasts, slide-overs |

**Motion** — 120–200ms on hover, focus and disclosure only. Nothing animates on page load.
Every animation is disabled under `prefers-reduced-motion`.

## Application shell

A fixed 240px ink sidebar with role-specific navigation, and a sticky page header.
Below 900px the sidebar becomes a slide-in drawer with a scrim, opened by a menu button
and closed with Escape or by clicking the scrim.

| Role | Navigation |
|---|---|
| Customer | Dashboard · My complaints |
| Agent | Dashboard · My tickets · Unassigned |
| Admin | Dashboard · Tickets · Users · Agents · Categories |

Views inside a page are addressed by hash (`admin.html#/users`), so the browser back
button works and links can point at a specific section.

## Components

Shell, sidebar, page header, stat tile, distribution bar, data table, ticket table with
status rail, badge, avatar, segmented control, toast, slide-over sheet, empty state,
skeleton loader, lifecycle pipeline, form field, button (four variants, three sizes,
with a loading state).

## Accessibility

- One `:focus-visible` treatment across the product.
- A skip link to the main content.
- The drawer and slide-over set `aria-modal`, close on Escape and return focus to whatever opened them.
- Navigation marks the current page with `aria-current="page"`; the segmented control uses `role="tab"` and `aria-selected`.
- Toasts live in an `aria-live="polite"` region, so they announce without stealing focus.
- Every form control has a real `<label>` bound by `for`/`id`.

## What the redesign did not touch

No backend file was opened. In the frontend, `api()`, `getSession()`, `requireRole()`,
`logout()`, every endpoint path and every payload are unchanged, as is all role logic
(`isStaff`, `canManage`, `isMine`). The redesign changed how the application looks,
not what it does.
