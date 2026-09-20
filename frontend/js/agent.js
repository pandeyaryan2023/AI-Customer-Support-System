"use strict";

const session = requireRole("AGENT");
let queue = "mine"; // "mine" = tickets assigned to me, "unassigned" = tickets nobody has claimed
let myAgentId = null;

if (session) init();

async function init() {
  renderNav(session);

  STATUSES.forEach((s) => document.getElementById("filter-status").append(option(s, labelOf(s))));
  PRIORITIES.forEach((p) => document.getElementById("filter-priority").append(option(p, p)));
  document.getElementById("filter-status").addEventListener("change", loadTickets);
  document.getElementById("filter-priority").addEventListener("change", loadTickets);

  document.querySelectorAll(".tab").forEach((tab) =>
    tab.addEventListener("click", () => {
      queue = tab.dataset.queue;
      document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
      loadTickets();
    }));

  try {
    const agents = await api("/agents");
    const me = agents.find((a) => a.user.id === session.id);
    myAgentId = me ? me.id : null;
  } catch (error) {
    notify(error.message);
  }
  await loadTickets();
}

async function loadTickets() {
  const query = queryString({
    status: document.getElementById("filter-status").value,
    priority: document.getElementById("filter-priority").value,
    unassigned: queue === "unassigned",
  });
  try {
    const tickets = await api(`/tickets${query}`);
    const claimButton = queue === "unassigned" ? claimAction : null;
    document.getElementById("tickets").replaceChildren(
      ticketTable(tickets, { showCustomer: true, action: claimButton }));
  } catch (error) {
    notify(error.message);
  }
}

function claimAction(ticket) {
  const button = h("button", { class: "btn btn-small btn-secondary" }, "Claim");
  button.addEventListener("click", () =>
    guarded(button, async () => {
      await api(`/tickets/${ticket.id}/assign`, { method: "POST", json: { agent_id: myAgentId } });
      await loadTickets();
      notify(`Ticket #${ticket.id} is now assigned to you.`, "success");
    }));
  return button;
}
