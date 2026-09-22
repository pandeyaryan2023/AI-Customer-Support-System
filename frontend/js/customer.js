"use strict";

/* Customer workspace: a dashboard summary and the full complaint list. "Ask support" is the
   floating widget (support-widget.js); the complaint form is shared (complaint-form.js). */

const session = requireRole("CUSTOMER");
let shell = null;

if (session) init();

function init() {
  shell = mountShell(session, { active: currentView(), onNavigate: render });
  window.addEventListener("hashchange", () => {
    openWidgetIfAsked();
    render(currentView());
  });
  preloadComplaintCategories();
  render(currentView());
  openWidgetIfAsked();
}

// "Ask support" used to be a page (#/ask). Old links now open the floating widget instead.
function openWidgetIfAsked() {
  if (location.hash === "#/ask" && supportWidget) supportWidget.open();
}

function currentView() {
  const id = location.hash.replace("#/", "");
  return id === "tickets" ? "tickets" : "dashboard";
}

function newComplaintButton() {
  return h("button", { class: "btn", type: "button",
    onclick: () => openComplaintSheet({ onCreated: () => render(currentView()) }) },
    icon("plus"), "Raise a complaint");
}

function render(view) {
  shell.setActive(view);
  if (view === "tickets") renderTickets();
  else renderDashboard();
}

/* ---------------------------------------------------------- dashboard */

function renderDashboard() {
  const firstName = String(session.name).split(" ")[0];
  shell.setHeader(`Hello, ${firstName}`, {
    subtitle: "Here is where your complaints stand today.",
    actions: [newComplaintButton()],
  });

  const stats = h("div", {});
  const recent = h("section", { class: "card" },
    h("div", { class: "card-head" },
      h("h2", { class: "section-title" }, "Recent complaints"),
      h("a", { class: "btn btn-secondary btn-sm row-end", href: "#/tickets" }, "View all")),
    skeletonRows(3));

  shell.body.replaceChildren(h("div", { class: "stack" }, stats, recent));
  stats.replaceChildren(skeletonStats(4));

  (async () => {
    let tickets;
    try {
      tickets = await api("/tickets");
    } catch (error) {
      stats.replaceChildren();
      recent.replaceChildren(emptyState({ icon: "alert", title: "Could not load your complaints", text: error.message }));
      return;
    }

    const count = (status) => tickets.filter((t) => t.status === status).length;
    const openish = tickets.filter((t) => !["RESOLVED", "CLOSED"].includes(t.status)).length;

    stats.replaceChildren(h("div", { class: "stat-grid" },
      statTile("Open complaints", openish, true),
      statTile("In progress", count("IN_PROGRESS")),
      statTile("Waiting on you", count("WAITING_FOR_CUSTOMER")),
      statTile("Resolved", count("RESOLVED") + count("CLOSED"))));

    shell.setNavCount("tickets", tickets.length || "");

    recent.replaceChildren(
      h("div", { class: "card-head" },
        h("h2", { class: "section-title" }, "Recent complaints"),
        h("a", { class: "btn btn-secondary btn-sm row-end", href: "#/tickets" }, "View all")),
      tickets.length === 0 ? noComplaintsYet() : ticketTable(tickets.slice(0, 5)));
  })();
}

function noComplaintsYet() {
  return emptyState({
    icon: "message",
    title: "You don't have any complaints yet",
    text: "When something goes wrong, raise a complaint and the support team will pick it up.",
    action: newComplaintButton(),
  });
}

/* ---------------------------------------------------------- complaint list */

function renderTickets() {
  const statusSelect = h("select", {}, option("", "All statuses"),
    STATUSES.map((s) => option(s, titleCase(s))));

  const results = h("div", {});
  const panel = h("section", { class: "card" },
    h("div", { class: "toolbar" }, field("Status", statusSelect)),
    results);

  shell.setHeader("My complaints", {
    subtitle: "Every complaint you have raised.",
    actions: [newComplaintButton()],
  });
  shell.body.replaceChildren(panel);

  const load = () => loadInto(results, skeletonRows(4), async () => {
    const tickets = await api(`/tickets${queryString({ status: statusSelect.value })}`);
    shell.setNavCount("tickets", tickets.length || "");
    if (tickets.length === 0) {
      return statusSelect.value
        ? emptyState({
            icon: "search",
            title: "Nothing with that status",
            text: "Try a different status, or clear the filter to see everything.",
            action: h("button", {
              class: "btn btn-secondary", type: "button",
              onclick: () => { statusSelect.value = ""; load(); },
            }, "Clear filter"),
          })
        : noComplaintsYet();
    }
    return ticketTable(tickets);
  });

  statusSelect.addEventListener("change", load);
  load();
}
