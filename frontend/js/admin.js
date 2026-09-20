"use strict";

const session = requireRole("ADMIN");

// Each tab is a function that fills the panel with its own content.
const TABS = {
  overview: showOverview,
  tickets: showTickets,
  users: showUsers,
  agents: showAgents,
  categories: showCategories,
};

if (session) init();

function init() {
  renderNav(session);
  document.querySelectorAll(".tab").forEach((tab) =>
    tab.addEventListener("click", () => openTab(tab.dataset.tab)));
  openTab("overview");
}

function openTab(name) {
  clearNotice();
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  // Clear at once: otherwise the previous tab stays on screen while the new data loads.
  panel(h("p", { class: "empty" }, "Loading…"));
  TABS[name]();
}

function panel(...content) {
  document.getElementById("panel").replaceChildren(...content);
}

let fieldCounter = 0;

/** A labelled form field. The label is linked to the control so clicking it focuses the input. */
function field(label, control) {
  fieldCounter += 1;
  control.id = `field-${fieldCounter}`;
  return h("div", { class: "field" }, h("label", { for: control.id }, label), control);
}

/** Run a load function; show the error banner if it fails. */
async function attempt(action) {
  try {
    await action();
  } catch (error) {
    notify(error.message);
  }
}

/* ---------- Overview ---------- */

function showOverview() {
  attempt(async () => {
    const stats = await api("/admin/stats");
    const cards = h("div", { class: "stat-cards" },
      statCard(stats.total_tickets, "Total tickets"),
      statCard(stats.unassigned_tickets, "Unassigned tickets"),
      statCard(stats.users_by_role.CUSTOMER, "Customers"),
      statCard(stats.users_by_role.AGENT, "Agents"));

    panel(cards,
      h("div", { class: "grid-halves" },
        h("section", { class: "card" }, h("h2", {}, "Tickets by status"), bars(stats.tickets_by_status, stats.total_tickets)),
        h("section", { class: "card" }, h("h2", {}, "Tickets by priority"), bars(stats.tickets_by_priority, stats.total_tickets))));
  });
}

function statCard(number, label) {
  return h("div", { class: "stat-card" }, h("div", { class: "num" }, String(number)), h("div", { class: "muted" }, label));
}

function bars(counts, total) {
  return h("div", {}, Object.entries(counts).map(([name, count]) => {
    const percent = total ? Math.round((count / total) * 100) : 0;
    return h("div", { class: "bar-row" },
      h("span", { class: "bar-label", title: labelOf(name) }, labelOf(name)),
      h("div", { class: "bar" }, h("span", { style: `width:${percent}%` })),
      h("span", { class: "bar-count" }, String(count)));
  }));
}

/* ---------- Tickets ---------- */

function showTickets() {
  const status = h("select", {}, option("", "All"), STATUSES.map((s) => option(s, labelOf(s))));
  const priority = h("select", {}, option("", "All"), PRIORITIES.map((p) => option(p, p)));
  const unassigned = h("input", { type: "checkbox" });
  const results = h("div", {});

  const reload = () => attempt(async () => {
    const tickets = await api(`/tickets${queryString({ status: status.value, priority: priority.value, unassigned: unassigned.checked })}`);
    results.replaceChildren(ticketTable(tickets, { showCustomer: true, showAgent: true }));
  });
  [status, priority, unassigned].forEach((control) => control.addEventListener("change", reload));

  panel(h("section", { class: "card" },
    h("div", { class: "filters" },
      field("Status", status), field("Priority", priority),
      h("label", { class: "check" }, unassigned, "Unassigned only")),
    results));
  reload();
}

/* ---------- Users ---------- */

function showUsers() {
  const role = h("select", {}, option("", "All roles"), ["CUSTOMER", "AGENT", "ADMIN"].map((r) => option(r, r)));
  const results = h("div", {});

  const reload = () => attempt(async () => {
    const users = await api(`/admin/users${queryString({ role: role.value })}`);
    results.replaceChildren(userTable(users, reload));
  });
  role.addEventListener("change", reload);

  panel(h("section", { class: "card" }, h("div", { class: "filters" }, field("Role", role)), results));
  reload();
}

function userTable(users, reload) {
  const rows = users.map((u) => {
    let action = h("span", { class: "muted small" }, "(you)");
    if (u.id !== session.id) {
      action = h("button", { class: `btn btn-small ${u.is_active ? "btn-danger" : "btn-secondary"}` }, u.is_active ? "Disable" : "Enable");
      action.addEventListener("click", () =>
        guarded(action, async () => {
          await api(`/admin/users/${u.id}`, { method: "PATCH", json: { is_active: !u.is_active } });
          await reload();
        }));
    }
    return h("tr", {},
      h("td", {}, String(u.id)), h("td", {}, u.full_name), h("td", {}, u.email), h("td", {}, u.role),
      h("td", {}, h("span", { class: `badge ${u.is_active ? "state-active" : "state-disabled"}` }, u.is_active ? "Active" : "Disabled")),
      h("td", { class: "small muted" }, fmtDate(u.created_at)),
      h("td", {}, action));
  });
  return simpleTable(["ID", "Name", "Email", "Role", "Status", "Joined", ""], rows);
}

function simpleTable(headings, rows) {
  if (rows.length === 0) return h("p", { class: "empty" }, "Nothing to show yet.");
  return h("div", { class: "table-wrap" },
    h("table", {}, h("thead", {}, h("tr", {}, headings.map((t) => h("th", {}, t)))), h("tbody", {}, rows)));
}

/* ---------- Agents ---------- */

function showAgents() {
  const name = h("input", { type: "text", minlength: "2", required: true });
  const email = h("input", { type: "email", required: true });
  const password = h("input", { type: "password", minlength: "8", autocomplete: "new-password", required: true });
  const department = h("input", { type: "text", maxlength: "100", placeholder: "e.g. Billing" });
  const form = h("form", { class: "card" },
    h("h2", {}, "Add an agent"),
    field("Full name", name), field("Email", email), field("Temporary password", password), field("Department (optional)", department),
    h("button", { class: "btn btn-block", type: "submit" }, "Create agent"));
  const results = h("div", {});

  const reload = () => attempt(async () => {
    const agents = await api("/admin/agents");
    results.replaceChildren(simpleTable(["ID", "Name", "Email", "Department", "Status"], agents.map((a) => h("tr", {},
      h("td", {}, String(a.id)), h("td", {}, a.user.full_name), h("td", {}, a.user.email), h("td", {}, a.department || "—"),
      h("td", {}, h("span", { class: `badge ${a.user.is_active ? "state-active" : "state-disabled"}` }, a.user.is_active ? "Active" : "Disabled"))))));
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(event.submitter, async () => {
      const agent = await api("/admin/agents", {
        method: "POST",
        json: { full_name: name.value, email: email.value.trim(), password: password.value, department: department.value.trim() || null },
      });
      form.reset();
      await reload();
      notify(`Agent ${agent.user.full_name} created.`, "success");
    });
  });

  panel(h("div", { class: "grid-2" }, form, h("section", { class: "card" }, h("h2", {}, "Agents"), results)));
  reload();
}

/* ---------- Categories ---------- */

function showCategories() {
  const name = h("input", { type: "text", minlength: "2", maxlength: "100", required: true });
  const description = h("input", { type: "text", maxlength: "255" });
  const form = h("form", { class: "card" },
    h("h2", {}, "Add a category"),
    field("Name", name), field("Description (optional)", description),
    h("button", { class: "btn btn-block", type: "submit" }, "Create category"));
  const results = h("div", {});

  const reload = () => attempt(async () => {
    const categories = await api("/admin/categories");
    results.replaceChildren(simpleTable(["Name", "Description", "Status", ""], categories.map((c) => {
      const toggle = h("button", { class: `btn btn-small ${c.is_active ? "btn-danger" : "btn-secondary"}` }, c.is_active ? "Deactivate" : "Activate");
      toggle.addEventListener("click", () =>
        guarded(toggle, async () => {
          await api(`/admin/categories/${c.id}`, { method: "PATCH", json: { is_active: !c.is_active } });
          await reload();
        }));
      return h("tr", {},
        h("td", {}, c.name), h("td", { class: "muted" }, c.description || "—"),
        h("td", {}, h("span", { class: `badge ${c.is_active ? "state-active" : "state-disabled"}` }, c.is_active ? "Active" : "Inactive")),
        h("td", {}, toggle));
    })));
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(event.submitter, async () => {
      await api("/admin/categories", { method: "POST", json: { name: name.value, description: description.value.trim() || null } });
      form.reset();
      await reload();
      notify("Category created.", "success");
    });
  });

  panel(h("div", { class: "grid-2" }, form, h("section", { class: "card" }, h("h2", {}, "Categories"), results)));
  reload();
}
