"use strict";

/* Ticket detail. The permission rules below are unchanged from the original
   page — the backend enforces them too, this only decides what to draw. */

const session = requireRole();
const ticketId = new URLSearchParams(location.search).get("id");

// Only a hint so the drop-down offers sensible choices.
// The backend is the authority (ALLOWED_TRANSITIONS in ticket_service.py).
const NEXT_STATUSES = {
  OPEN: ["IN_PROGRESS", "WAITING_FOR_CUSTOMER", "ESCALATED", "RESOLVED"],
  IN_PROGRESS: ["WAITING_FOR_CUSTOMER", "ESCALATED", "RESOLVED"],
  WAITING_FOR_CUSTOMER: ["IN_PROGRESS", "ESCALATED", "RESOLVED"],
  ESCALATED: ["IN_PROGRESS", "RESOLVED"],
  RESOLVED: ["IN_PROGRESS", "CLOSED"],
  CLOSED: [],
};

const NAV_FOR_ROLE = { CUSTOMER: "tickets", AGENT: "mine", ADMIN: "tickets" };

let ticket = null;
let agents = [];
let shell = null;
let analysis = null; // the latest AI suggestions for this ticket, kept only in this page

if (session) init();

function init() {
  shell = mountShell(session, { active: NAV_FOR_ROLE[session.role] });
  if (!ticketId) {
    shell.setHeader("Ticket");
    shell.body.replaceChildren(emptyState({
      icon: "alert",
      title: "No ticket selected",
      text: "Open a ticket from your list to see its details.",
      action: h("a", { class: "btn", href: DASHBOARD[session.role] }, "Back to dashboard"),
    }));
    return;
  }
  shell.setHeader("Ticket", { actions: [backButton()] });
  shell.body.replaceChildren(h("div", { class: "stack" }, skeletonDetail()));
  load();
}

function backButton() {
  return h("a", { class: "btn btn-secondary", href: DASHBOARD[session.role] }, "Back to list");
}

function skeletonDetail() {
  return h("div", { class: "card card-pad" },
    h("span", { class: "skeleton sk-line", style: "width:90px" }),
    h("span", { class: "skeleton", style: "width:60%;height:22px;margin-top:12px;display:block" }),
    h("span", { class: "skeleton", style: "width:100%;height:46px;margin-top:24px;display:block" }));
}

async function load() {
  try {
    ticket = await api(`/tickets/${encodeURIComponent(ticketId)}`);
    if (session.role !== "CUSTOMER" && agents.length === 0) agents = await api("/agents");
  } catch (error) {
    shell.setHeader("Ticket", { actions: [backButton()] });
    shell.body.replaceChildren(emptyState({
      icon: error.status === 404 ? "lock" : "alert",
      title: error.status === 404 ? "Ticket not found" : "Could not load this ticket",
      text: error.status === 404
        ? "It may have been removed, or it belongs to someone else."
        : error.message,
      action: h("a", { class: "btn", href: DASHBOARD[session.role] }, "Back to dashboard"),
    }));
    return;
  }
  render();
}

/** Run an action, reload the ticket, then confirm with a toast. */
function change(button, action, successText) {
  return guarded(button, async () => {
    await action();
    await load();
    toast(successText, "success");
  });
}

/* ---------- who may do what (the backend enforces this too) ---------- */

const isStaff = () => session.role !== "CUSTOMER";
const isMine = () =>
  session.role === "AGENT" && ticket.assigned_agent && ticket.assigned_agent.user.id === session.id;
const canManage = () => session.role === "ADMIN" || isMine();
const isClosed = () => ticket.status === "CLOSED";

/* ---------------------------------------------------------- render */

function render() {
  shell.setHeader(`Ticket #${ticket.id}`, {
    subtitle: ticket.category ? ticket.category.name : "Uncategorised",
    actions: [backButton()],
  });

  // Re-rendering rebuilds the reply box; keep whatever the agent had typed (or a used draft).
  const typed = document.querySelector(".composer textarea")?.value || "";

  const main = h("div", { class: "stack" }, detailCard(), isStaff() ? aiCard() : null, conversationCard());
  shell.body.replaceChildren(
    isStaff() ? h("div", { class: "ticket-grid" }, main, managePanel()) : main);

  const box = document.querySelector(".composer textarea");
  if (box && typed) box.value = typed;

  const thread = document.getElementById("thread");
  if (thread) thread.scrollTop = thread.scrollHeight;
}

function detailCard() {
  return h("section", { class: "card card-raised" },
    h("div", { class: "ticket-head" },
      h("div", { class: "ticket-head-top" },
        h("div", { style: "flex:1;min-width:0" },
          h("p", { class: "ticket-id" }, `#${ticket.id}`),
          h("h2", { class: "ticket-subject" }, ticket.title)),
        h("div", { class: "row" },
          ticket.from_ai_handoff ? h("span", { class: "badge badge-plain ai-label" }, "AI handoff") : null,
          statusBadge(ticket.status), priorityBadge(ticket.priority))),
      pipeline(ticket.status)),

    h("dl", { class: "facts" },
      fact("Customer", ticket.customer.full_name),
      fact("Category", ticket.category ? ticket.category.name : "—"),
      fact("Assigned to", ticket.assigned_agent ? agentLabel(ticket.assigned_agent) : "Not assigned yet"),
      fact("Raised", fmtDay(ticket.created_at)),
      fact("Last update", fmtAgo(ticket.updated_at))),

    h("div", { class: "description" },
      h("h3", { class: "section-title" }, "What the customer reported"),
      h("p", {}, ticket.description)),
    ticket.ai_handoff ? handoffSection(ticket.ai_handoff) : null);
}

/* What the AI assistant knew when the customer asked for a person (Phase 6 handoff). */
function handoffSection(handoff) {
  return h("div", { class: "description handoff" },
    h("h3", { class: "section-title" }, "Handed over from the AI assistant"),
    h("p", { class: "handoff-question" }, `“${handoff.question}”`),
    h("p", { class: "meta" }, `${handoff.reason} Asked ${fmtDate(handoff.asked_at)}.`),
    handoff.sources.length
      ? h("div", {},
          h("h4", { class: "label ask-sources-title" }, "Articles the assistant checked"),
          h("ul", { class: "source-list" }, handoff.sources.map((source) =>
            h("li", { class: "source-item" }, icon("file"),
              h("span", { class: "strong" }, source.document_title),
              h("span", { class: "meta" }, `Part ${source.chunk_index + 1}`),
              h("span", { class: "meta source-score" }, `Relevance ${source.similarity.toFixed(2)}`)))))
      : h("p", { class: "meta" }, "This may be a gap in the knowledge base."));
}

function fact(label, value) {
  return h("div", { class: "fact" }, h("dt", {}, label), h("dd", {}, value));
}

/* ---------------------------------------------------------- AI ticket analysis */

/* Suggestions from the local model. Nothing is changed or sent here: category and priority
   use the normal update (so the usual permission rules apply), and the draft only fills
   the reply box. Sending is always the agent's own click. */
function aiCard() {
  const run = h("button", { class: "btn btn-secondary btn-sm", type: "button" },
    analysis ? "Analyse again" : "Analyse ticket");
  const body = h("div", { class: "ai-body" }, analysis ? aiResult() : h("p", { class: "meta" },
    "Suggests a category, priority, customer sentiment, a short summary and a draft reply. "
    + "Nothing changes on the ticket until you apply it."));
  const card = h("section", { class: "card ai-card" },
    h("div", { class: "card-head" },
      h("h2", { class: "section-title" }, "AI ticket analysis"),
      h("span", { class: "badge badge-plain ai-label" }, "Suggestions"),
      run),
    body);

  run.addEventListener("click", async () => {
    setLoading(run, true);
    body.replaceChildren(h("div", { "aria-busy": "true" },
      h("p", { class: "meta" }, "Reading the ticket… this can take up to a minute."),
      h("div", { class: "ask-skeleton" },
        h("span", { class: "skeleton sk-line", style: "width:70%" }),
        h("span", { class: "skeleton sk-line", style: "width:90%" }),
        h("span", { class: "skeleton sk-line", style: "width:50%" }))));
    try {
      analysis = await api(`/tickets/${ticket.id}/ai-analysis`, { method: "POST" });
      card.replaceWith(aiCard());
    } catch (error) {
      body.replaceChildren(h("p", { class: "field-error" }, error.message));
      setLoading(run, false);
    }
  });
  return card;
}

function aiResult() {
  const a = analysis;
  const currentCategory = ticket.category ? ticket.category.id : null;
  return h("div", {},
    h("dl", { class: "ai-grid" },
      aiRow("Category", a.category ? `AI suggests: ${a.category.name}` : "No suggestion",
        a.category ? applyButton(a.category.id === currentCategory, { category_id: a.category.id },
          "Category updated.") : null),
      aiRow("Priority", a.priority ? `AI suggests: ${titleCase(a.priority)}` : "No suggestion",
        a.priority ? applyButton(a.priority === ticket.priority, { priority: a.priority },
          "Priority updated.") : null),
      aiRow("Customer sentiment", a.sentiment
        ? h("span", { class: `badge sentiment-${a.sentiment}` }, titleCase(a.sentiment))
        : "Not clear", null)),
    a.ignored_instructions ? h("p", { class: "ai-warning" }, icon("alert"),
      "This ticket contains text addressed to the AI (such as \"ignore your instructions\"). "
      + "It was left out of the analysis. Read the ticket yourself before acting.") : null,
    h("div", { class: "ai-block" },
      h("h3", { class: "label" }, "Summary"),
      h("p", {}, a.summary || "No summary was produced.")),
    a.suggested_reply ? draftBlock(a.suggested_reply) : null,
    h("p", { class: "meta ai-foot" },
      `Suggested by ${a.model} from this ticket's text. Suggestions can be wrong: check them before acting.`));
}

function aiRow(label, value, action) {
  return h("div", { class: "ai-row" }, h("dt", {}, label), h("dd", {}, value), action);
}

/** Apply one suggestion through the normal ticket update. */
function applyButton(isCurrent, change_, successText) {
  if (isCurrent) return h("span", { class: "meta" }, "Already set");
  if (isClosed()) return h("span", { class: "meta" }, "Ticket closed");
  if (!canManage()) return h("span", { class: "meta" }, "Assign to yourself to apply");
  const button = h("button", { class: "btn btn-secondary btn-sm", type: "button" }, "Apply");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}`, { method: "PATCH", json: change_ }), successText));
  return button;
}

function draftBlock(text) {
  const canReply = canManage() && !isClosed();
  const use = h("button", { class: "btn btn-sm", type: "button" }, "Use draft");
  use.addEventListener("click", () => {
    const box = document.querySelector(".composer textarea");
    if (!box) return;
    if (box.value.trim() && box.value !== text
        && !confirm("Replace what is in your reply box with the AI draft?")) return;
    box.value = text;  // placed in the editor only: nothing is sent
    box.focus();
    box.scrollIntoView({ behavior: "smooth", block: "center" });
    toast("Draft placed in your reply. Review and edit it before sending.", "info");
  });
  return h("div", { class: "ai-block" },
    h("h3", { class: "label" }, "Suggested reply ", h("span", { class: "badge badge-plain ai-label" }, "AI draft")),
    h("p", { class: "ai-draft" }, text),
    h("div", { class: "ai-draft-actions" },
      canReply ? use : null,
      h("span", { class: "meta" }, canReply
        ? "Review and edit it before sending. It is never sent automatically."
        : "Assign this ticket to yourself to reply.")));
}

function conversationCard() {
  const messages = ticket.messages.length === 0
    ? emptyState({
        icon: "message",
        title: "No replies yet",
        text: isStaff()
          ? "Send the first reply to let the customer know it is being looked at."
          : "The support team will reply here. You'll see their messages on this page.",
      })
    : ticket.messages.map(messageBubble);

  return h("section", { class: "card" },
    h("div", { class: "card-head" },
      h("h2", { class: "section-title" }, "Conversation"),
      h("span", { class: "meta row-end" },
        `${ticket.messages.length} ${ticket.messages.length === 1 ? "message" : "messages"}`)),
    h("div", { class: "thread", id: "thread" }, messages),
    composer());
}

function messageBubble(message) {
  const fromStaff = message.sender.role !== "CUSTOMER";
  const isSystem = message.message.startsWith("[Escalated]");
  return h("div", { class: `msg ${fromStaff ? "msg-staff" : ""} ${isSystem ? "msg-system" : ""}` },
    avatar(message.sender.full_name, "avatar-sm"),
    h("div", { class: "msg-body" },
      h("div", { class: "msg-head" },
        h("span", { class: "msg-author" }, message.sender.full_name),
        h("span", { class: "meta" }, `${titleCase(message.sender.role)} · ${fmtAgo(message.created_at)}`)),
      h("div", { class: "msg-bubble", title: fmtDate(message.created_at) }, message.message)));
}

function composer() {
  if (isClosed()) {
    return h("div", { class: "composer-locked" }, icon("lock"),
      "This ticket is closed. No further messages can be sent.");
  }
  if (isStaff() && !canManage()) {
    return h("div", { class: "composer-locked" }, icon("lock"),
      "Assign this ticket to yourself to reply to the customer.");
  }

  const box = h("textarea", {
    maxlength: "5000",
    required: true,
    placeholder: isStaff() ? "Reply to the customer…" : "Add a message for the support team…",
  });
  const send = h("button", { class: "btn", type: "submit" }, "Send message");

  const form = h("form", { class: "composer" },
    field(isStaff() ? "Your reply" : "Your message", box),
    h("div", { class: "composer-actions" }, send));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!box.value.trim()) { box.focus(); return; }
    change(send, () => api(`/tickets/${ticket.id}/messages`, {
      method: "POST", json: { message: box.value },
    }), "Message sent.");
  });
  return form;
}

/* ---------------------------------------------------------- manage panel */

function managePanel() {
  const panel = h("aside", { class: "card card-raised" },
    h("div", { class: "card-head" }, h("h2", { class: "section-title" }, "Manage ticket")));

  if (!canManage()) {
    // An agent looking at an unassigned ticket: the only action is to claim it.
    const me = agents.find((a) => a.user.id === session.id);
    const claim = h("button", { class: "btn btn-block", type: "button" }, "Assign to me");
    claim.addEventListener("click", () =>
      change(claim, () => api(`/tickets/${ticket.id}/assign`, {
        method: "POST", json: { agent_id: me.id },
      }), "Ticket assigned to you."));

    panel.append(h("div", { class: "panel-section" },
      h("p", { class: "muted", style: "margin-bottom:var(--s3)" },
        "This ticket is unassigned. Take ownership to reply and change its status."),
      me ? claim : h("p", { class: "meta" }, "No agent profile found for your account.")));
    return panel;
  }

  panel.append(statusControl(), priorityControl());
  // The backend refuses to assign a closed ticket, so don't offer a control that can only fail.
  if (!isClosed()) panel.append(assignControl());
  if (NEXT_STATUSES[ticket.status].includes("ESCALATED")) panel.append(escalateControl());
  return panel;
}

function panelSection(label, ...content) {
  return h("div", { class: "panel-section" },
    h("span", { class: "label" }, label),
    h("div", { class: "panel-control" }, ...content));
}

function statusControl() {
  const choices = NEXT_STATUSES[ticket.status];
  if (choices.length === 0) {
    return panelSection("Status", h("p", { class: "meta" }, "Closed tickets cannot be changed."));
  }
  const select = h("select", { "aria-label": "New status" }, choices.map((s) => option(s, titleCase(s))));
  const button = h("button", { class: "btn", type: "button" }, "Update status");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}`, {
      method: "PATCH", json: { status: select.value },
    }), "Status updated."));
  return panelSection("Move to", select, button);
}

function priorityControl() {
  const select = h("select", { "aria-label": "Priority" },
    PRIORITIES.map((p) => option(p, titleCase(p), p === ticket.priority)));
  const button = h("button", { class: "btn btn-secondary", type: "button" }, "Save priority");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}`, {
      method: "PATCH", json: { priority: select.value },
    }), "Priority updated."));
  return panelSection("Priority", select, button);
}

function assignControl() {
  const current = ticket.assigned_agent && ticket.assigned_agent.id;
  const candidates = agents.filter((a) => a.id !== current);
  if (candidates.length === 0) {
    return panelSection("Assignment", h("p", { class: "meta" }, "No other agents available."));
  }
  const select = h("select", { "aria-label": "Assign to agent" },
    candidates.map((a) => option(a.id, agentLabel(a))));
  const button = h("button", { class: "btn btn-secondary", type: "button" },
    ticket.assigned_agent ? "Reassign" : "Assign");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}/assign`, {
      method: "POST", json: { agent_id: Number(select.value) },
    }), "Ticket assigned."));
  return panelSection(ticket.assigned_agent ? "Reassign to" : "Assign to", select, button);
}

function escalateControl() {
  const reason = h("textarea", {
    style: "min-height:76px",
    placeholder: "Why does this need escalating? (at least 5 characters)",
    "aria-label": "Escalation reason",
  });
  const button = h("button", { class: "btn btn-danger", type: "button" }, "Escalate ticket");
  button.addEventListener("click", () =>
    change(button, () => api(`/tickets/${ticket.id}/escalate`, {
      method: "POST", json: { reason: reason.value },
    }), "Ticket escalated."));
  return panelSection("Escalate", reason, button);
}
