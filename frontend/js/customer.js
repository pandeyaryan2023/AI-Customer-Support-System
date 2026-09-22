"use strict";

/* Customer workspace: a dashboard summary, the full complaint list, and "Ask support",
   which answers questions from the company's help articles (POST /ai/ask). */

const session = requireRole("CUSTOMER");
let shell = null;
let categories = [];

if (session) init();

function init() {
  shell = mountShell(session, { active: currentView(), onNavigate: render });
  window.addEventListener("hashchange", () => render(currentView()));
  loadCategories();
  render(currentView());
}

function currentView() {
  const id = location.hash.replace("#/", "");
  return ["tickets", "ask"].includes(id) ? id : "dashboard";
}

async function loadCategories() {
  try {
    categories = await api("/categories");
  } catch {
    categories = []; // the complaint form still works without a category
  }
}

function newComplaintButton() {
  return h("button", { class: "btn", type: "button", onclick: openComplaintSheet },
    icon("plus"), "Raise a complaint");
}

function render(view) {
  shell.setActive(view);
  if (view === "tickets") renderTickets();
  else if (view === "ask") renderAsk();
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

/* ---------------------------------------------------------- raise a complaint */

function openComplaintSheet() {
  const title = h("input", { type: "text", minlength: "5", maxlength: "200",
    placeholder: "e.g. Charged twice for the same order", required: true });
  const category = h("select", {}, option("", "Not sure / other"),
    categories.map((c) => option(c.id, c.name)));
  const description = h("textarea", { minlength: "10", maxlength: "5000",
    placeholder: "What happened? Include any order or reference numbers.", required: true });

  const submit = h("button", { class: "btn", type: "submit", form: "complaint-form" }, "Submit complaint");

  const form = h("form", { id: "complaint-form" },
    field("Title", title, { hint: "A short summary — at least 5 characters." }),
    field("Category", category, { hint: "Optional. It helps us route your complaint faster." }),
    field("What went wrong", description, { hint: "At least 10 characters." }));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(submit, async () => {
      const ticket = await api("/tickets", {
        method: "POST",
        json: {
          title: title.value,
          description: description.value,
          category_id: category.value ? Number(category.value) : null,
        },
      });
      closeSheet();
      toast(`Complaint #${ticket.id} submitted. We'll be in touch.`, "success");
      render(currentView());
    });
  });

  openSheet({
    title: "Raise a complaint",
    body: form,
    footer: [h("button", { class: "btn btn-secondary", type: "button", onclick: closeSheet }, "Cancel"), submit],
  });
}

/* ---------------------------------------------------------- ask support */

function renderAsk() {
  shell.setHeader("Ask support", {
    subtitle: "Get an answer from our help articles, any time.",
  });

  const question = h("textarea", { id: "ask-question", minlength: "2", maxlength: "500", rows: "3",
    placeholder: "e.g. Can I get my money back after 20 days?", required: true });
  const submit = h("button", { class: "btn", type: "submit", form: "ask-form" }, icon("message"), "Ask");
  const result = h("div", {});

  const form = h("form", { id: "ask-form", class: "card card-pad" },
    field("Your question", question, {
      hint: "Answers come only from our help articles. It can take up to a minute.",
    }),
    h("div", { class: "row ask-actions" }, submit));

  // Enter asks; Shift+Enter starts a new line.
  question.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = question.value.trim();
    if (text.length < 2) { notify("Type a question first."); return; }

    result.replaceChildren(askLoading());
    setLoading(submit, true);
    try {
      const reply = await api("/ai/ask", { method: "POST", json: { question: text } });
      result.replaceChildren(reply.status === "ANSWERED" ? answerCard(reply) : notFoundCard(reply));
    } catch (error) {
      result.replaceChildren(h("section", { class: "card" }, emptyState({
        icon: "alert", title: "The assistant is unavailable right now", text: error.message })));
    } finally {
      setLoading(submit, false);
    }
  });

  shell.body.replaceChildren(h("div", { class: "stack ask" }, form, result));
  question.focus();
}

function askLoading() {
  return h("section", { class: "card card-pad", "aria-busy": "true" },
    h("p", { class: "meta" }, "Searching our help articles and writing an answer…"),
    h("div", { class: "ask-skeleton" },
      h("span", { class: "skeleton sk-line", style: "width:92%" }),
      h("span", { class: "skeleton sk-line", style: "width:78%" }),
      h("span", { class: "skeleton sk-line", style: "width:54%" })));
}

function answerCard(reply) {
  return h("section", { class: "card card-pad", "aria-live": "polite" },
    h("span", { class: "badge badge-plain ai-label" }, icon("info"),
      "AI-generated answer based on company knowledge"),
    h("p", { class: "ask-answer" }, reply.answer),
    h("h3", { class: "label ask-sources-title" }, "Sources"),
    h("ul", { class: "source-list" }, reply.sources.map((source) =>
      h("li", { class: "source-item" },
        icon("file"),
        h("span", { class: "strong" }, source.document_title),
        h("span", { class: "meta" }, `Part ${source.chunk_index + 1}`),
        h("span", { class: "meta source-score", title: "How closely this passage matched your question (0 to 1)" },
          `Relevance ${source.similarity.toFixed(2)}`)))),
    h("p", { class: "meta ask-note" },
      "This answer was written by AI from the sources above. If something looks wrong, contact our support team."));
}

function notFoundCard(reply) {
  return h("section", { class: "card", "aria-live": "polite" }, emptyState({
    icon: "search",
    title: "Our help articles don't cover this",
    text: `${reply.answer} Try rephrasing your question, or raise a complaint from My complaints so our team can help.`,
  }));
}
