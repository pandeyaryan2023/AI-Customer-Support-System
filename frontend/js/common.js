"use strict";

/* Shared helpers used by every page: talking to the API, the login session,
   building HTML safely, the top navigation bar and small UI pieces. */

// When the page is served by FastAPI (port 8000) the API is on the same origin.
const API_BASE = location.port === "8000" ? "" : "http://127.0.0.1:8000";

const DASHBOARD = { CUSTOMER: "customer.html", AGENT: "agent.html", ADMIN: "admin.html" };
const STATUSES = ["OPEN", "IN_PROGRESS", "WAITING_FOR_CUSTOMER", "ESCALATED", "RESOLVED", "CLOSED"];
const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"];

/* ---------- login session (kept in the browser's localStorage) ---------- */

function getSession() {
  try {
    return JSON.parse(localStorage.getItem("session"));
  } catch {
    return null;
  }
}

function saveSession(session) {
  localStorage.setItem("session", JSON.stringify(session));
}

function logout() {
  localStorage.removeItem("session");
  location.href = "login.html";
}

/** Page guard: send visitors to login, or to their own dashboard if the role is wrong. */
function requireRole(role) {
  const session = getSession();
  if (!session) {
    location.replace("login.html");
    return null;
  }
  if (role && session.role !== role) {
    location.replace(DASHBOARD[session.role]);
    return null;
  }
  return session;
}

/* ---------- talking to the backend ---------- */

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function errorText(data, status) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: ["body", "title"], msg: "..."}]
    return detail.map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ");
  }
  return `Request failed (${status})`;
}

/** Call the API. Adds the JWT automatically. Throws ApiError with a readable message. */
async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  const session = getSession();
  if (session) headers.Authorization = `Bearer ${session.token}`;

  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = new URLSearchParams(form); // login expects form fields, not JSON
  }

  let response;
  try {
    response = await fetch(API_BASE + path, { method, headers, body });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }

  const data = await response.json().catch(() => null);
  if (response.status === 401 && session && path !== "/auth/login") {
    logout(); // token expired or account disabled
    throw new ApiError(401, "Your session has expired. Please log in again.");
  }
  if (!response.ok) throw new ApiError(response.status, errorText(data, response.status));
  return data;
}

/* ---------- building HTML safely ---------- */

/** h("p", {class: "x"}, "text", childNode). Text is always inserted as text, never as HTML,
    so user-written content (ticket titles, messages) cannot inject scripts (XSS). */
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

function fmtDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function labelOf(value) {
  return value.replaceAll("_", " ");
}

function statusBadge(status) {
  return h("span", { class: `badge status-${status}` }, labelOf(status));
}

function priorityBadge(priority) {
  return h("span", { class: `badge priority-${priority}` }, priority);
}

function agentLabel(agent) {
  return agent.department ? `${agent.user.full_name} (${agent.department})` : agent.user.full_name;
}

function option(value, text, selected = false) {
  return h("option", { value, selected }, text);
}

/* ---------- notices (success / error banner at the top of the page) ---------- */

function notify(text, kind = "error") {
  const box = document.getElementById("notice");
  box.className = `notice notice-${kind}`;
  box.textContent = text;
  box.hidden = false;
}

function clearNotice() {
  const box = document.getElementById("notice");
  box.hidden = true;
  box.textContent = "";
}

/** Run an async action: disable the button meanwhile, show errors in the notice banner. */
async function guarded(button, action) {
  clearNotice();
  if (button) button.disabled = true;
  try {
    return await action();
  } catch (error) {
    notify(error.message);
  } finally {
    if (button) button.disabled = false;
  }
}

/* ---------- page pieces ---------- */

function renderNav(session) {
  document.getElementById("topbar").replaceChildren(
    h("div", { class: "topbar-inner" },
      h("a", { class: "brand", href: DASHBOARD[session.role] }, "Support Desk"),
      h("div", { class: "topbar-user" },
        h("span", {}, session.name),
        h("span", { class: "role-tag" }, session.role),
        h("button", { class: "btn btn-ghost", onclick: logout }, "Log out"))));
}

/** A table of tickets. Each title links to the ticket page. `action(ticket)` may add a last column. */
function ticketTable(tickets, { showCustomer = false, showAgent = false, action = null } = {}) {
  if (tickets.length === 0) return h("p", { class: "empty" }, "No tickets found.");

  const head = ["ID", "Title", "Status", "Priority"];
  if (showCustomer) head.push("Customer");
  if (showAgent) head.push("Agent");
  head.push("Updated");
  if (action) head.push("");

  const rows = tickets.map((t) => h("tr", {},
    h("td", {}, `#${t.id}`),
    h("td", {}, h("a", { href: `ticket.html?id=${t.id}` }, t.title)),
    h("td", {}, statusBadge(t.status)),
    h("td", {}, priorityBadge(t.priority)),
    showCustomer ? h("td", {}, t.customer.full_name) : null,
    showAgent ? h("td", {}, t.assigned_agent ? t.assigned_agent.user.full_name : h("span", { class: "muted" }, "Unassigned")) : null,
    h("td", { class: "small muted" }, fmtDate(t.updated_at)),
    action ? h("td", {}, action(t)) : null));

  return h("div", { class: "table-wrap" },
    h("table", {},
      h("thead", {}, h("tr", {}, head.map((text) => h("th", {}, text)))),
      h("tbody", {}, rows)));
}

/** Build a query string from filters, skipping empty values. */
function queryString(params) {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "" && value != null && value !== false) q.set(key, value);
  }
  const text = q.toString();
  return text ? `?${text}` : "";
}
