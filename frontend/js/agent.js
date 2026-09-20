"use strict";

/* Agent workspace: a dashboard, the agent's own tickets, and the unassigned queue.
   Uses the same two endpoints the old page used: GET /tickets and GET /tickets?unassigned=true. */

const session = requireRole("AGENT");
let shell = null;
let myAgentId = null;

if (session) init();

async function init() {
  shell = mountShell(session, { active: currentView(), onNavigate: render });
  window.addEventListener("hashchange", () => render(currentView()));

  try {
    const agents = await api("/agents");
    const me = agents.find((a) => a.user.id === session.id);
    myAgentId = me ? me.id : null;
  } catch (error) {
    notify(error.message);
  }

  render(currentView());
}

function currentView() {
  const id = location.hash.replace("#/", "");
  return ["mine", "queue"].includes(id) ? id : "dashboard";
}

function render(view) {
  shell.setActive(view);
  if (view === "mine") renderQueue("mine");
  else if (view === "queue") renderQueue("queue");
  else renderDashboard();
}

/** Claim button — unchanged behaviour: POST /tickets/{id}/assign with this agent's id. */
function claimButton(ticket, onDone) {
  const button = h("button", { class: "btn btn-secondary btn-sm", type: "button" }, "Claim");
  button.addEventListener("click", () =>
    guarded(button, async () => {
      await api(`/tickets/${ticket.id}/assign`, { method: "POST", json: { agent_id: myAgentId } });
      toast(`Ticket #${ticket.id} is yours now.`, "success");
      onDone();
    }));
  return button;
}

/* ---------------------------------------------------------- dashboard */

function renderDashboard() {
  const firstName = String(session.name).split(" ")[0];
  shell.setHeader(`Hello, ${firstName}`, { subtitle: "Your workload and what's waiting in the queue." });

  const stats = h("div", {}, skeletonStats(4));
  const recent = h("section", { class: "card" },
    h("div", { class: "card-head" }, h("h2", { class: "section-title" }, "Your active tickets")),
    skeletonRows(3));

  shell.body.replaceChildren(h("div", { class: "stack" }, stats, recent));

  (async () => {
    let mine, queue;
    try {
      [mine, queue] = await Promise.all([api("/tickets"), api("/tickets?unassigned=true")]);
    } catch (error) {
      stats.replaceChildren();
      recent.replaceChildren(emptyState({ icon: "alert", title: "Could not load your workspace", text: error.message }));
      return;
    }

    const count = (status) => mine.filter((t) => t.status === status).length;
    const active = mine.filter((t) => !["RESOLVED", "CLOSED"].includes(t.status));

    stats.replaceChildren(h("div", { class: "stat-grid" },
      statTile("Assigned to you", mine.length, true),
      statTile("Waiting in queue", queue.length),
      statTile("Escalated", count("ESCALATED")),
      statTile("Resolved by you", count("RESOLVED") + count("CLOSED"))));

    shell.setNavCount("mine", mine.length || "");
    shell.setNavCount("queue", queue.length || "");

    recent.replaceChildren(
      h("div", { class: "card-head" },
        h("h2", { class: "section-title" }, "Your active tickets"),
        h("a", { class: "btn btn-secondary btn-sm row-end", href: "#/mine" }, "View all")),
      active.length === 0
        ? emptyState({
            icon: "inbox",
            title: "Nothing is assigned to you yet",
            text: queue.length
              ? `There ${queue.length === 1 ? "is 1 ticket" : `are ${queue.length} tickets`} waiting to be claimed.`
              : "The unassigned queue is clear too.",
            action: queue.length
              ? h("a", { class: "btn", href: "#/queue" }, "View unassigned")
              : null,
          })
        : ticketTable(active.slice(0, 5), { showCustomer: true }));
  })();
}

/* ---------------------------------------------------------- ticket queues */

function renderQueue(which) {
  const statusSelect = h("select", {}, option("", "All statuses"),
    STATUSES.map((s) => option(s, titleCase(s))));
  const prioritySelect = h("select", {}, option("", "All priorities"),
    PRIORITIES.map((p) => option(p, titleCase(p))));

  const results = h("div", {});
  const tabs = h("div", {});

  const panel = h("section", { class: "card" },
    h("div", { class: "toolbar" },
      field("Status", statusSelect),
      field("Priority", prioritySelect)),
    results);

  shell.setHeader(which === "mine" ? "My tickets" : "Unassigned queue", {
    subtitle: which === "mine"
      ? "Tickets assigned to you."
      : "Tickets nobody has picked up yet. Claim one to start working on it.",
  });
  shell.body.replaceChildren(h("div", { class: "stack" }, tabs, panel));

  function renderTabs(mineCount, queueCount) {
    tabs.replaceChildren(segmented(
      [
        { id: "mine", label: "My tickets", count: mineCount },
        { id: "queue", label: "Unassigned", count: queueCount },
      ],
      which,
      (id) => { location.hash = `#/${id}`; }));
  }
  renderTabs(null, null);

  const load = () => loadInto(results, skeletonRows(5), async () => {
    const query = queryString({
      status: statusSelect.value,
      priority: prioritySelect.value,
      unassigned: which === "queue",
    });
    const tickets = await api(`/tickets${query}`);
    const isFiltered = statusSelect.value || prioritySelect.value;

    shell.setNavCount(which, tickets.length || "");
    renderTabs(which === "mine" ? tickets.length : null, which === "queue" ? tickets.length : null);

    if (tickets.length === 0) {
      if (isFiltered) {
        return emptyState({
          icon: "search",
          title: "No tickets match these filters",
          text: "Try widening the status or priority filter.",
          action: h("button", {
            class: "btn btn-secondary", type: "button",
            onclick: () => { statusSelect.value = ""; prioritySelect.value = ""; load(); },
          }, "Clear filters"),
        });
      }
      return which === "mine"
        ? emptyState({
            icon: "inbox",
            title: "Nothing is assigned to you yet",
            text: "Pick up a ticket from the unassigned queue to get started.",
            action: h("a", { class: "btn", href: "#/queue" }, "View unassigned"),
          })
        : emptyState({
            icon: "check",
            title: "Queue is clear",
            text: "Every ticket has an owner. Nothing is waiting to be picked up.",
          });
    }

    return ticketTable(tickets, {
      showCustomer: true,
      action: which === "queue" && myAgentId ? (ticket) => claimButton(ticket, load) : null,
    });
  });

  statusSelect.addEventListener("change", load);
  prioritySelect.addEventListener("change", load);
  load();
}
