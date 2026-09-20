"use strict";

const session = requireRole("CUSTOMER");
if (session) init();

async function init() {
  renderNav(session);

  const statusFilter = document.getElementById("filter-status");
  STATUSES.forEach((s) => statusFilter.append(option(s, labelOf(s))));
  statusFilter.addEventListener("change", loadTickets);
  document.getElementById("new-ticket").addEventListener("submit", createTicket);

  await Promise.all([loadCategories(), loadTickets()]);
}

async function loadCategories() {
  try {
    const categories = await api("/categories");
    const select = document.getElementById("category");
    categories.forEach((c) => select.append(option(c.id, c.name)));
  } catch (error) {
    notify(error.message);
  }
}

async function loadTickets() {
  const status = document.getElementById("filter-status").value;
  try {
    const tickets = await api(`/tickets${queryString({ status })}`);
    document.getElementById("tickets").replaceChildren(ticketTable(tickets));
  } catch (error) {
    notify(error.message);
  }
}

function createTicket(event) {
  event.preventDefault();
  const form = event.target;
  const category = document.getElementById("category").value;

  guarded(event.submitter, async () => {
    const ticket = await api("/tickets", {
      method: "POST",
      json: {
        title: document.getElementById("title").value,
        description: document.getElementById("description").value,
        category_id: category ? Number(category) : null,
      },
    });
    form.reset();
    await loadTickets();
    notify(`Complaint #${ticket.id} submitted. Our team will respond soon.`, "success");
  });
}
