"use strict";

/* ============================================================
   Behaviour: talking to the API, the login session and page guards.
   Presentation lives in ui.js. Nothing in this file was changed by
   the visual redesign except `guarded`, which now also drives the
   button's loading state.
   ============================================================ */

// FastAPI serves this interface at /app/, so whenever the page came from there the API
// is on the same origin — whatever port the backend runs on (8000, 8001, ...). Relative
// URLs then need no CORS at all. The absolute address below is only a fallback for
// opening these files outside the backend (a separate static server, or file://).
const API_BASE = location.pathname.startsWith("/app/") ? "" : "http://127.0.0.1:8001";

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

/** Build a query string from filters, skipping empty values. */
function queryString(params) {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "" && value != null && value !== false) q.set(key, value);
  }
  const text = q.toString();
  return text ? `?${text}` : "";
}

/** Run an async action: show the button as loading, surface errors as a toast. */
async function guarded(button, action) {
  setLoading(button, true);
  try {
    return await action();
  } catch (error) {
    notify(error.message);
  } finally {
    setLoading(button, false);
  }
}

/** Load data into a container, showing a skeleton first and an error state on failure. */
async function loadInto(container, placeholder, loader) {
  container.replaceChildren(placeholder);
  try {
    container.replaceChildren(await loader());
  } catch (error) {
    container.replaceChildren(emptyState({
      icon: "alert",
      title: "Could not load this",
      text: error.message,
    }));
  }
}
