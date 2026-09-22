"use strict";

/* ============================================================
   UI component library — presentation only.
   Nothing here talks to the API or decides permissions; it is
   handed data and renders it. Behaviour lives in common.js.
   ============================================================ */

/* ---------------------------------------------------------- DOM builder */

/** h("p", {class: "x"}, "text", childNode).
    Text is inserted as text, never as HTML, so user content cannot inject scripts. */
function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  node.append(...children.flat().filter((child) => child != null && child !== false));
  return node;
}

/* ---------------------------------------------------------- icons */

const ICON_PATHS = {
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  ticket: "M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z",
  inbox: "M4 13h4l2 3h4l2-3h4M4 13l2-7h12l2 7v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z",
  users: "M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 20v-2a4 4 0 0 0-3-3.87M16 2.13a4 4 0 0 1 0 7.75",
  headset: "M4 14v-2a8 8 0 0 1 16 0v2M4 14a2 2 0 0 1 2-2h1v6H6a2 2 0 0 1-2-2zM20 14a2 2 0 0 0-2-2h-1v6h1a2 2 0 0 0 2-2zM17 18v1a3 3 0 0 1-3 3h-2",
  tags: "M3 7v5.5a2 2 0 0 0 .6 1.4l7 7a2 2 0 0 0 2.8 0l5.5-5.5a2 2 0 0 0 0-2.8l-7-7a2 2 0 0 0-1.4-.6H5a2 2 0 0 0-2 2z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "M18 6 6 18M6 6l12 12",
  plus: "M12 5v14M5 12h14",
  check: "M20 6 9 17l-5-5",
  alert: "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4",
  message: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
  folder: "M3 7a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  file: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6",
  upload: "M12 15V3M7 8l5-5 5 5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
};

function icon(name, extraClass) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  if (extraClass) svg.setAttribute("class", extraClass);
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICON_PATHS[name] || ICON_PATHS.info);
  svg.append(path);
  return svg;
}

/* ---------------------------------------------------------- formatting */

function initials(name) {
  const parts = String(name || "?").trim().split(/\s+/);
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : parts[0].slice(0, 2);
  return letters.toUpperCase();
}

function avatar(name, size = "") {
  return h("span", { class: `avatar ${size}`, "aria-hidden": "true" }, initials(name));
}

function identity(name, sub, size = "avatar-sm") {
  return h("span", { class: "identity" },
    avatar(name, size),
    h("span", { class: "identity-text" },
      h("span", { class: "truncate strong" }, name),
      sub ? h("span", { class: "meta truncate" }, sub) : null));
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function fmtDay(iso) {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

/** "just now", "4h ago", "3d ago" — falls back to a date after a week. */
function fmtAgo(iso) {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return fmtDay(iso);
}

/** 2048 -> "2.0 KB", 1572864 -> "1.5 MB". */
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function labelOf(value) {
  return String(value).replaceAll("_", " ");
}

function titleCase(value) {
  return labelOf(value).toLowerCase().replace(/(^|\s)\w/g, (c) => c.toUpperCase());
}

/* ---------------------------------------------------------- badges */

function statusBadge(status) {
  return h("span", { class: `badge status-${status}` }, titleCase(status));
}

function priorityBadge(priority) {
  return h("span", { class: `badge priority-${priority}` }, titleCase(priority));
}

function roleBadge(role) {
  return h("span", { class: `badge badge-plain role-${role}` }, titleCase(role));
}

function activeBadge(isActive) {
  return h("span", { class: `badge ${isActive ? "state-active" : "state-disabled"}` },
    isActive ? "Active" : "Disabled");
}

function agentLabel(agent) {
  return agent.department ? `${agent.user.full_name} (${agent.department})` : agent.user.full_name;
}

function option(value, text, selected = false) {
  return h("option", { value, selected }, text);
}

/* ---------------------------------------------------------- toasts */

function toastHost() {
  let host = document.querySelector(".toasts");
  if (!host) {
    host = h("div", { class: "toasts", role: "status", "aria-live": "polite" });
    document.body.append(host);
  }
  return host;
}

const TOAST_ICON = { success: "check", error: "alert", info: "info" };

/** Show a toast. Replaces the old banner: nothing on the page moves. */
function toast(text, kind = "error") {
  const host = toastHost();
  const node = h("div", { class: `toast toast-${kind}` },
    icon(TOAST_ICON[kind] || "info"),
    h("p", { class: "toast-text" }, text),
    h("button", { class: "toast-close", type: "button", "aria-label": "Dismiss", onclick: () => dismiss() },
      icon("close")));

  function dismiss() {
    if (!node.isConnected) return;
    node.classList.add("is-leaving");
    setTimeout(() => node.remove(), 200);
  }

  host.append(node);
  // Keep the stack short so toasts never cover a panel for long.
  while (host.children.length > 3) host.firstElementChild.remove();
  setTimeout(dismiss, kind === "error" ? 6000 : 4000);
  return node;
}

/* `notify` and `clearNotice` keep their old names so existing call sites work. */
function notify(text, kind = "error") {
  toast(text, kind);
}

function clearNotice() {
  document.querySelectorAll(".toasts .toast").forEach((node) => node.remove());
}

/* ---------------------------------------------------------- button loading */

function setLoading(button, isLoading) {
  if (!button) return;
  button.classList.toggle("is-loading", isLoading);
  button.disabled = isLoading;
}

/* ---------------------------------------------------------- application shell */

const NAV = {
  CUSTOMER: [
    { id: "dashboard", label: "Dashboard", icon: "dashboard" },
    { id: "tickets", label: "My complaints", icon: "ticket" },
    { id: "ask", label: "Ask support", icon: "message" },
  ],
  AGENT: [
    { id: "dashboard", label: "Dashboard", icon: "dashboard" },
    { id: "mine", label: "My tickets", icon: "ticket" },
    { id: "queue", label: "Unassigned", icon: "inbox" },
  ],
  ADMIN: [
    { id: "dashboard", label: "Dashboard", icon: "dashboard" },
    { id: "tickets", label: "Tickets", icon: "ticket" },
    { id: "users", label: "Users", icon: "users" },
    { id: "agents", label: "Agents", icon: "headset" },
    { id: "categories", label: "Categories", icon: "tags" },
    { id: "documents", label: "Knowledge base", icon: "file" },
  ],
};

const ROLE_SUBTITLE = { CUSTOMER: "Customer portal", AGENT: "Agent workspace", ADMIN: "Administration" };

function brandMark() {
  return h("span", { class: "brand-mark", "aria-hidden": "true" }, icon("headset"));
}

/** Build the sidebar + header and return the element page content goes into.
    `onNavigate` receives a nav id; pages that are a single view can omit it. */
function mountShell(session, { active, onNavigate, home } = {}) {
  const items = NAV[session.role] || [];
  const drawer = { open: false };

  const navLinks = items.map((item) => {
    const isActive = item.id === active;
    const attrs = {
      class: "nav-item",
      href: onNavigate ? `#/${item.id}` : `${home || DASHBOARD[session.role]}#/${item.id}`,
    };
    if (isActive) attrs["aria-current"] = "page";
    const link = h("a", attrs, icon(item.icon), h("span", {}, item.label),
      h("span", { class: "nav-count hidden", "data-count": item.id }));
    link.addEventListener("click", (event) => {
      closeDrawer();
      if (onNavigate) {
        event.preventDefault();
        location.hash = `#/${item.id}`;
        onNavigate(item.id);
      }
    });
    return link;
  });

  const sidebar = h("aside", { class: "sidebar on-ink", id: "sidebar", "aria-label": "Main navigation" },
    h("a", { class: "sidebar-brand", href: DASHBOARD[session.role] },
      brandMark(),
      h("span", {},
        h("span", { class: "brand-name" }, "Support Desk"),
        // The business this user works in: everything on these pages belongs to it.
        h("span", { class: "brand-sub", title: "Your business" },
          session.business || ROLE_SUBTITLE[session.role] || ""))),
    h("nav", { class: "sidebar-nav" }, navLinks),
    h("div", { class: "sidebar-user" },
      avatar(session.name),
      h("span", { class: "sidebar-user-text" },
        h("span", { class: "sidebar-user-name truncate" }, session.name),
        h("span", { class: "sidebar-user-role" }, titleCase(session.role))),
      h("button", { class: "icon-btn", type: "button", title: "Log out", "aria-label": "Log out", onclick: logout },
        icon("logout"))));

  const toggle = h("button", {
    class: "icon-btn menu-toggle",
    type: "button",
    "aria-label": "Open navigation",
    "aria-controls": "sidebar",
    "aria-expanded": "false",
    onclick: () => (drawer.open ? closeDrawer() : openDrawer()),
  }, icon("menu"));
  toggle.style.color = "var(--text-muted)";

  const titleEl = h("h1", { class: "page-title" }, "");
  const subEl = h("p", { class: "meta hidden" }, "");
  const actionsEl = h("div", { class: "page-header-actions" });

  const header = h("header", { class: "page-header" },
    toggle,
    h("div", { class: "page-header-text" }, titleEl, subEl),
    actionsEl);

  const body = h("main", { class: "page-body", id: "main" });
  const scrim = h("div", { class: "scrim", onclick: () => closeDrawer() });

  document.body.prepend(
    h("a", { class: "skip-link", href: "#main" }, "Skip to content"),
    h("div", { class: "app" }, sidebar, h("div", { class: "workspace" }, header, body)),
    scrim);

  function openDrawer() {
    drawer.open = true;
    document.body.classList.add("drawer-open");
    toggle.setAttribute("aria-expanded", "true");
    const first = sidebar.querySelector("a, button");
    if (first) first.focus();
  }

  function closeDrawer() {
    if (!drawer.open) return;
    drawer.open = false;
    document.body.classList.remove("drawer-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.focus();
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && drawer.open) closeDrawer();
  });

  return {
    body,
    /** Set the page header. `actions` is an array of elements. */
    setHeader(title, { subtitle = "", actions = [] } = {}) {
      titleEl.textContent = title;
      subEl.textContent = subtitle;
      subEl.classList.toggle("hidden", !subtitle);
      actionsEl.replaceChildren(...actions);
    },
    /** Show a count beside a nav item. */
    setNavCount(id, value) {
      const el = sidebar.querySelector(`[data-count="${id}"]`);
      if (!el) return;
      el.textContent = value;
      el.classList.toggle("hidden", value == null || value === "");
    },
    setActive(id) {
      sidebar.querySelectorAll(".nav-item").forEach((link, index) => {
        const match = items[index] && items[index].id === id;
        if (match) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
    },
  };
}

/* ---------------------------------------------------------- slide-over sheet */

let openSheetState = null;

/** A right-hand panel for forms. Escape closes it; focus returns where it started. */
function openSheet({ title, body, footer }) {
  closeSheet();
  const opener = document.activeElement;

  const panel = h("div", { class: "sheet", role: "dialog", "aria-modal": "true", "aria-label": title },
    h("div", { class: "sheet-head" },
      h("h2", { class: "section-title" }, title),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Close", onclick: () => closeSheet() },
        icon("close"))),
    h("div", { class: "sheet-body" }, body),
    footer ? h("div", { class: "sheet-foot" }, footer) : null);

  // The sheet has its own scrim. It must NOT set body.drawer-open: that class is what
  // slides the navigation drawer in on phones, so it would open behind the sheet.
  const scrim = h("div", { class: "scrim", onclick: () => closeSheet() });
  document.body.append(scrim, panel);
  requestAnimationFrame(() => scrim.classList.add("is-open"));

  const focusable = panel.querySelector("input, textarea, select, button");
  if (focusable) focusable.focus();

  function onKey(event) {
    if (event.key === "Escape") closeSheet();
  }
  document.addEventListener("keydown", onKey);

  openSheetState = { panel, scrim, opener, onKey };
  return panel;
}

function closeSheet() {
  if (!openSheetState) return;
  const { panel, scrim, opener, onKey } = openSheetState;
  openSheetState = null;
  document.removeEventListener("keydown", onKey);
  panel.remove();
  scrim.remove();
  if (opener && opener.focus) opener.focus();
}

/* ---------------------------------------------------------- empty & loading */

function emptyState({ icon: iconName = "folder", title, text, action } = {}) {
  return h("div", { class: "empty" },
    h("span", { class: "empty-icon" }, icon(iconName)),
    h("p", { class: "empty-title" }, title),
    text ? h("p", { class: "empty-text" }, text) : null,
    action || null);
}

function skeletonRows(count = 4) {
  return h("div", {}, Array.from({ length: count }, () =>
    h("div", { class: "sk-row" },
      h("span", { class: "skeleton", style: "width:28px;height:28px;border-radius:999px" }),
      h("span", { class: "skeleton sk-line", style: "flex:1" }),
      h("span", { class: "skeleton sk-line", style: "width:72px" }),
      h("span", { class: "skeleton sk-line", style: "width:56px" }))));
}

function skeletonStats(count = 4) {
  return h("div", { class: "stat-grid" }, Array.from({ length: count }, () =>
    h("div", { class: "stat" },
      h("span", { class: "skeleton sk-line", style: "width:70px" }),
      h("span", { class: "skeleton", style: "width:56px;height:30px;margin-top:10px;display:block" }))));
}

/* ---------------------------------------------------------- tables */

function tableFrom(headings, rows) {
  return h("div", { class: "table-wrap" },
    h("table", {},
      h("thead", {}, h("tr", {}, headings.map((cell) =>
        h("th", cell && cell.align === "right" ? { class: "col-actions" } : {},
          typeof cell === "string" ? cell : cell.label)))),
      h("tbody", {}, rows)));
}

/**
 * The ticket list. `action(ticket)` may return a trailing control.
 * Columns adapt to the role, but the status rail is always present.
 */
function ticketTable(tickets, { showCustomer = false, showAgent = false, action = null } = {}) {
  const headings = ["Ticket"];
  if (showCustomer) headings.push("Customer");
  if (showAgent) headings.push("Assigned to");
  headings.push("Priority", "Status", "Updated");
  if (action) headings.push({ label: "", align: "right" });

  const rows = tickets.map((ticket) => h("tr", { class: `ticket-row rail-${ticket.status}` },
    h("td", { class: "cell-subject" },
      h("a", { href: `ticket.html?id=${ticket.id}` }, ticket.title),
      h("span", { class: "meta" },
        h("span", { class: "tnum" }, `#${ticket.id}`),
        ticket.category ? ` · ${ticket.category.name}` : "",
        ticket.from_ai_handoff ? h("span", { class: "badge badge-plain ai-label handoff-badge" }, "AI handoff") : null)),
    showCustomer ? h("td", {}, identity(ticket.customer.full_name)) : null,
    showAgent ? h("td", {},
      ticket.assigned_agent
        ? identity(ticket.assigned_agent.user.full_name, ticket.assigned_agent.department)
        : h("span", { class: "muted" }, "Unassigned")) : null,
    h("td", {}, priorityBadge(ticket.priority)),
    h("td", {}, statusBadge(ticket.status)),
    h("td", { class: "meta", title: fmtDate(ticket.updated_at) }, fmtAgo(ticket.updated_at)),
    action ? h("td", { class: "col-actions" }, h("span", { class: "row-action" }, action(ticket))) : null));

  return tableFrom(headings, rows);
}

/* ---------------------------------------------------------- statistics */

function statTile(label, value, accent = false) {
  return h("div", { class: "stat" },
    h("p", { class: "stat-label" }, label),
    h("p", { class: `stat-value ${accent ? "stat-accent" : ""}` }, String(value)));
}

/** Horizontal distribution bars that reuse the status palette. */
function distribution(counts, total) {
  const entries = Object.entries(counts);
  if (entries.every(([, n]) => n === 0)) {
    return h("p", { class: "muted", style: "padding:var(--s2) 0" }, "No tickets yet.");
  }
  return h("div", { class: "dist" }, entries.map(([name, count]) => {
    const percent = total ? Math.round((count / total) * 100) : 0;
    return h("div", { class: "dist-row" },
      h("span", { class: "dist-label truncate", title: titleCase(name) }, titleCase(name)),
      h("span", { class: "dist-track" },
        h("span", { class: `dist-fill fill-${name}`, style: `width:${percent}%` })),
      h("span", { class: "dist-count" }, String(count)));
  }));
}

/* ---------------------------------------------------------- lifecycle pipeline */

const PIPE_STAGES = [
  { id: "OPEN", label: "Open" },
  { id: "IN_PROGRESS", label: "In progress" },
  { id: "RESOLVED", label: "Resolved" },
  { id: "CLOSED", label: "Closed" },
];

// Waiting and escalated are side states of the "in progress" stage, not stages of their own.
const STAGE_OF = {
  OPEN: 0,
  IN_PROGRESS: 1,
  WAITING_FOR_CUSTOMER: 1,
  ESCALATED: 1,
  RESOLVED: 2,
  CLOSED: 3,
};

const PIPE_NOTE = {
  WAITING_FOR_CUSTOMER: { icon: "clock", text: "Waiting for the customer to reply" },
  ESCALATED: { icon: "alert", text: "Escalated for review" },
};

function pipeline(status) {
  const current = STAGE_OF[status] ?? 0;
  const steps = PIPE_STAGES.map((stage, index) => {
    const state = index < current ? "is-done" : index === current ? "is-current" : "";
    return h("div", { class: `pipe-step ${state}` },
      h("div", { class: "pipe-node" },
        h("span", { class: "pipe-dot" }, index < current ? icon("check") : null),
        h("span", { class: "pipe-label" }, stage.label)),
      index < PIPE_STAGES.length - 1 ? h("span", { class: "pipe-line" }) : null);
  });

  const note = PIPE_NOTE[status];
  return h("div", {},
    h("div", { class: "pipeline", role: "img", "aria-label": `Lifecycle: ${titleCase(status)}` }, steps),
    note ? h("p", { class: `pipe-note pipe-note-${status}` }, icon(note.icon), note.text) : null);
}

/* ---------------------------------------------------------- misc */

function field(label, control, { hint } = {}) {
  if (!control.id) control.id = `f-${Math.random().toString(36).slice(2, 9)}`;
  return h("div", { class: "field" },
    h("label", { for: control.id }, label),
    control,
    hint ? h("p", { class: "field-hint" }, hint) : null);
}

function segmented(items, currentId, onSelect) {
  return h("div", { class: "segmented", role: "tablist" }, items.map((item) =>
    h("button", {
      type: "button",
      role: "tab",
      "aria-selected": String(item.id === currentId),
      onclick: () => onSelect(item.id),
    },
      h("span", {}, item.label),
      item.count != null ? h("span", { class: "count tnum" }, String(item.count)) : null)));
}
