"use strict";

const session = requireRole();
const ticketId = new URLSearchParams(location.search).get("id");

// Only a hint so the drop-down shows sensible choices.
// The backend is the authority and rejects illegal changes (see ALLOWED_TRANSITIONS in ticket_service.py).
const NEXT_STATUSES = {
  OPEN: ["IN_PROGRESS", "WAITING_FOR_CUSTOMER", "ESCALATED", "RESOLVED"],
  IN_PROGRESS: ["WAITING_FOR_CUSTOMER", "ESCALATED", "RESOLVED"],
  WAITING_FOR_CUSTOMER: ["IN_PROGRESS", "ESCALATED", "RESOLVED"],
  ESCALATED: ["IN_PROGRESS", "RESOLVED"],
  RESOLVED: ["IN_PROGRESS", "CLOSED"],
  CLOSED: [],
};

let ticket = null;
let agents = [];

if (session) init();

async function init() {
  renderNav(session);
  document.getElementById("back-link").href = DASHBOARD[session.role];
  if (!ticketId) {
    notify("No ticket selected.");
    return;
  }
  await load();
}

async function load() {
  try {
    ticket = await api(`/tickets/${encodeURIComponent(ticketId)}`);
    if (session.role !== "CUSTOMER" && agents.length === 0) agents = await api("/agents");
  } catch (error) {
    document.getElementById("ticket").replaceChildren();
    notify(error.message);
    return;
  }
  render();
}

/** Run an action that changes the ticket, then reload it and show a success message. */
function change(button, action, successText) {
  return guarded(button, async () => {
    await action();
    await load();
    notify(successText, "success");
  });
}

/* ---------- who may do what (the backend enforces this too) ---------- */

const isStaff = () => session.role !== "CUSTOMER";
const isMine = () =>
  session.role === "AGENT" && ticket.assigned_agent && ticket.assigned_agent.user.id === session.id;
const canManage = () => session.role === "ADMIN" || isMine();
const isClosed = () => ticket.status === "CLOSED";

/* ---------- rendering ---------- */

function render() {
  const main = h("div", {}, detailsCard(), conversationCard());
  const layout = isStaff()
    ? h("div", { class: "ticket-layout" }, main, staffPanel())
    : main;
  document.getElementById("ticket").replaceChildren(layout);

  const list = document.getElementById("messages");
  if (list) list.scrollTop = list.scrollHeight;
}

function detailsCard() {
  const meta = h("dl", { class: "meta" },
    h("dt", {}, "Customer"), h("dd", {}, ticket.customer.full_name),
    h("dt", {}, "Category"), h("dd", {}, ticket.category ? ticket.category.name : "—"),
    h("dt", {}, "Assigned to"), h("dd", {}, ticket.assigned_agent ? agentLabel(ticket.assigned_agent) : "Not assigned yet"),
    h("dt", {}, "Created"), h("dd", {}, fmtDate(ticket.created_at)),
    h("dt", {}, "Last update"), h("dd", {}, fmtDate(ticket.updated_at)));

  return h("section", { class: "card" },
    h("div", { class: "ticket-title" },
      h("h1", {}, `#${ticket.id} ${ticket.title}`),
      statusBadge(ticket.status),
      priorityBadge(ticket.priority)),
    meta,
    h("h3", {}, "Description"),
    h("p", { class: "pre" }, ticket.description));
}

function conversationCard() {
  const messages = ticket.messages.length === 0
    ? h("p", { class: "empty" }, "No messages yet.")
    : ticket.messages.map((m) => h("div", { class: `msg ${m.sender.role === "CUSTOMER" ? "" : "msg-staff"}` },
        h("div", { class: "msg-head" },
          h("strong", {}, m.sender.full_name), ` · ${m.sender.role.toLowerCase()} · ${fmtDate(m.created_at)}`),
        h("div", { class: "pre" }, m.message)));

  return h("section", { class: "card" },
    h("h2", {}, "Conversation"),
    h("div", { id: "messages", class: "messages" }, messages),
    replyArea());
}

function replyArea() {
  if (isClosed()) return h("p", { class: "muted" }, "This ticket is closed. No further messages can be sent.");
  if (isStaff() && !canManage()) {
    return h("p", { class: "muted" }, "Claim this ticket to reply to the customer.");
  }

  const box = h("textarea", { placeholder: "Write a message…", maxlength: "5000", required: true });
  const form = h("form", {},
    h("div", { class: "field" }, box),
    h("button", { class: "btn", type: "submit" }, "Send message"));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    change(event.submitter, () => api(`/tickets/${ticket.id}/messages`, { method: "POST", json: { message: box.value } }), "Message sent.");
  });
  return form;
}

function staffPanel() {
  const panel = h("aside", { class: "card" }, h("h2", {}, "Manage ticket"));

  if (!canManage()) {
    // An agent looking at an unassigned ticket: the only action is to claim it.
    const claim = h("button", { class: "btn btn-block" }, "Assign to me");
    const me = agents.find((a) => a.user.id === session.id);
    claim.addEventListener("click", () =>
      change(claim, () => api(`/tickets/${ticket.id}/assign`, { method: "POST", json: { agent_id: me.id } }), "Ticket assigned to you."));
    panel.append(h("p", { class: "muted" }, "This ticket is unassigned. Assign it to yourself to work on it."), claim);
    return panel;
  }

  panel.append(statusControl(), priorityControl(), assignControl());
  if (NEXT_STATUSES[ticket.status].includes("ESCALATED")) panel.append(escalateControl());
  return panel;
}

function sideSection(title, ...content) {
  return h("div", { class: "side-section" }, h("h3", {}, title), ...content);
}

function statusControl() {
  const choices = NEXT_STATUSES[ticket.status];
  if (choices.length === 0) return sideSection("Status", h("p", { class: "muted small" }, "Closed tickets cannot be changed."));

  const select = h("select", {}, choices.map((s) => option(s, labelOf(s))));
  const button = h("button", { class: "btn" }, "Apply");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}`, { method: "PATCH", json: { status: select.value } }), "Status updated."));
  return sideSection("Change status", h("div", { class: "inline-form" }, select, button));
}

function priorityControl() {
  const select = h("select", {}, PRIORITIES.map((p) => option(p, p, p === ticket.priority)));
  const button = h("button", { class: "btn" }, "Save");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}`, { method: "PATCH", json: { priority: select.value } }), "Priority updated."));
  return sideSection("Priority", h("div", { class: "inline-form" }, select, button));
}

function assignControl() {
  const candidates = agents.filter((a) => a.id !== (ticket.assigned_agent && ticket.assigned_agent.id));
  if (candidates.length === 0) return sideSection("Assignment", h("p", { class: "muted small" }, "No other agents available."));

  const select = h("select", {}, candidates.map((a) => option(a.id, agentLabel(a))));
  const button = h("button", { class: "btn" }, ticket.assigned_agent ? "Reassign" : "Assign");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}/assign`, { method: "POST", json: { agent_id: Number(select.value) } }), "Ticket assigned."));
  return sideSection(ticket.assigned_agent ? "Reassign to" : "Assign to", h("div", { class: "inline-form" }, select, button));
}

function escalateControl() {
  const reason = h("textarea", { placeholder: "Why is this being escalated? (min 5 characters)", style: "min-height:70px" });
  const button = h("button", { class: "btn btn-danger btn-block" }, "Escalate");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}/escalate`, { method: "POST", json: { reason: reason.value } }), "Ticket escalated."));
  return sideSection("Escalate", h("div", { class: "field" }, reason), button);
}
