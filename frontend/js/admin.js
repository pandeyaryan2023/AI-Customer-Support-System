"use strict";

/* Administration workspace. Six views, one per sidebar item. */

const session = requireRole("ADMIN");
let shell = null;

const VIEWS = {
  dashboard: renderDashboard,
  tickets: renderTickets,
  users: renderUsers,
  agents: renderAgents,
  categories: renderCategories,
  documents: renderDocuments,
};

if (session) init();

function init() {
  shell = mountShell(session, { active: currentView(), onNavigate: render });
  window.addEventListener("hashchange", () => render(currentView()));
  render(currentView());
}

function currentView() {
  const id = location.hash.replace("#/", "");
  return VIEWS[id] ? id : "dashboard";
}

function render(view) {
  shell.setActive(view);
  VIEWS[view]();
}

function panelCard(title, body, action) {
  return h("section", { class: "card" },
    h("div", { class: "card-head" },
      h("h2", { class: "section-title" }, title),
      action ? h("span", { class: "row-end" }, action) : null),
    body);
}

function tableOrEmpty(rows, headings, empty) {
  return rows.length === 0 ? empty : tableFrom(headings, rows);
}

/* ---------------------------------------------------------- dashboard */

function renderDashboard() {
  shell.setHeader("Dashboard", { subtitle: "How the support desk is running right now." });

  const stats = h("div", {}, skeletonStats(4));
  const charts = h("div", {});
  const latest = h("div", {});
  shell.body.replaceChildren(h("div", { class: "stack" }, stats, charts, latest));

  (async () => {
    let summary, tickets;
    try {
      [summary, tickets] = await Promise.all([api("/admin/stats"), api("/tickets")]);
    } catch (error) {
      stats.replaceChildren(emptyState({ icon: "alert", title: "Could not load statistics", text: error.message }));
      return;
    }

    stats.replaceChildren(h("div", { class: "stat-grid" },
      statTile("Total tickets", summary.total_tickets, true),
      statTile("Unassigned", summary.unassigned_tickets),
      statTile("Customers", summary.users_by_role.CUSTOMER),
      statTile("Agents", summary.users_by_role.AGENT)));

    charts.replaceChildren(h("div", { class: "ticket-grid" },
      panelCard("Tickets by status",
        h("div", { class: "card-pad" }, distribution(summary.tickets_by_status, summary.total_tickets))),
      panelCard("Tickets by priority",
        h("div", { class: "card-pad" }, distribution(summary.tickets_by_priority, summary.total_tickets)))));

    latest.replaceChildren(panelCard("Latest tickets",
      tickets.length === 0
        ? emptyState({ icon: "folder", title: "No tickets yet", text: "Nothing has been raised on the system so far." })
        : ticketTable(tickets.slice(0, 5), { showCustomer: true, showAgent: true }),
      tickets.length ? h("a", { class: "btn btn-secondary btn-sm", href: "#/tickets" }, "View all") : null));
  })();
}

/* ---------------------------------------------------------- tickets */

function renderTickets() {
  shell.setHeader("Tickets", { subtitle: "Every ticket on the system." });

  const statusSelect = h("select", {}, option("", "All statuses"), STATUSES.map((s) => option(s, titleCase(s))));
  const prioritySelect = h("select", {}, option("", "All priorities"), PRIORITIES.map((p) => option(p, titleCase(p))));
  const unassigned = h("input", { type: "checkbox" });
  const results = h("div", {});

  const load = () => loadInto(results, skeletonRows(6), async () => {
    const tickets = await api(`/tickets${queryString({
      status: statusSelect.value,
      priority: prioritySelect.value,
      unassigned: unassigned.checked,
    })}`);
    shell.setNavCount("tickets", tickets.length || "");
    if (tickets.length === 0) {
      return emptyState({
        icon: "search",
        title: "No tickets match these filters",
        text: "Try clearing the filters to see everything.",
        action: h("button", {
          class: "btn btn-secondary", type: "button",
          onclick: () => {
            statusSelect.value = ""; prioritySelect.value = ""; unassigned.checked = false; load();
          },
        }, "Clear filters"),
      });
    }
    return ticketTable(tickets, { showCustomer: true, showAgent: true });
  });

  [statusSelect, prioritySelect, unassigned].forEach((c) => c.addEventListener("change", load));

  shell.body.replaceChildren(h("section", { class: "card" },
    h("div", { class: "toolbar" },
      field("Status", statusSelect),
      field("Priority", prioritySelect),
      h("label", { class: "checkbox", style: "padding-bottom:9px" }, unassigned, "Unassigned only")),
    results));
  load();
}

/* ---------------------------------------------------------- users */

function renderUsers() {
  shell.setHeader("Users", { subtitle: "Everyone with an account on the system." });

  const roleSelect = h("select", {}, option("", "All roles"),
    ["CUSTOMER", "AGENT", "ADMIN"].map((r) => option(r, titleCase(r))));
  const results = h("div", {});

  const load = () => loadInto(results, skeletonRows(6), async () => {
    const users = await api(`/admin/users${queryString({ role: roleSelect.value })}`);
    shell.setNavCount("users", users.length || "");

    const rows = users.map((user) => {
      let action;
      if (user.id === session.id) {
        action = h("span", { class: "meta" }, "That's you");
      } else {
        action = h("button", {
          class: `btn btn-sm ${user.is_active ? "btn-danger" : "btn-secondary"}`,
          type: "button",
        }, user.is_active ? "Disable" : "Enable");
        action.addEventListener("click", () =>
          guarded(action, async () => {
            await api(`/admin/users/${user.id}`, { method: "PATCH", json: { is_active: !user.is_active } });
            toast(`${user.full_name} ${user.is_active ? "disabled" : "enabled"}.`, "success");
            await load();
          }));
      }
      return h("tr", {},
        h("td", {}, identity(user.full_name, user.email)),
        h("td", {}, roleBadge(user.role)),
        h("td", {}, activeBadge(user.is_active)),
        h("td", { class: "meta" }, fmtDay(user.created_at)),
        h("td", { class: "col-actions" }, h("span", { class: "row-action" }, action)));
    });

    return tableOrEmpty(rows,
      ["User", "Role", "Status", "Joined", { label: "", align: "right" }],
      emptyState({ icon: "users", title: "No users with that role", text: "Try a different role filter." }));
  });

  roleSelect.addEventListener("change", load);

  shell.body.replaceChildren(h("section", { class: "card" },
    h("div", { class: "toolbar" }, field("Role", roleSelect)),
    results));
  load();
}

/* ---------------------------------------------------------- agents */

function renderAgents() {
  const addButton = h("button", { class: "btn", type: "button", onclick: () => openAgentSheet(load) },
    icon("plus"), "Add agent");
  shell.setHeader("Agents", { subtitle: "Support staff who can be assigned tickets.", actions: [addButton] });

  const results = h("div", {});
  shell.body.replaceChildren(h("section", { class: "card" }, results));

  function load() {
    return loadInto(results, skeletonRows(4), async () => {
      const agents = await api("/admin/agents");
      shell.setNavCount("agents", agents.length || "");

      const rows = agents.map((agent) => h("tr", {},
        h("td", {}, identity(agent.user.full_name, agent.user.email)),
        h("td", {}, agent.department || h("span", { class: "muted" }, "—")),
        h("td", {}, activeBadge(agent.user.is_active)),
        h("td", { class: "meta" }, fmtDay(agent.user.created_at))));

      return tableOrEmpty(rows,
        ["Agent", "Department", "Status", "Joined"],
        emptyState({
          icon: "headset",
          title: "No agents yet",
          text: "Create an agent account so tickets can be assigned to someone.",
          action: h("button", { class: "btn", type: "button", onclick: () => openAgentSheet(load) }, "Add agent"),
        }));
    });
  }
  load();
}

function openAgentSheet(onDone) {
  const name = h("input", { type: "text", minlength: "2", maxlength: "100", placeholder: "Ravi Kumar", required: true });
  const email = h("input", { type: "email", placeholder: "ravi@example.com", required: true });
  const password = h("input", { type: "password", minlength: "8", autocomplete: "new-password", required: true });
  const department = h("input", { type: "text", maxlength: "100", placeholder: "Billing" });
  const submit = h("button", { class: "btn", type: "submit", form: "agent-form" }, "Create agent");

  const form = h("form", { id: "agent-form" },
    field("Full name", name),
    field("Email", email, { hint: "The agent signs in with this address." }),
    field("Temporary password", password, { hint: "At least 8 characters. Ask them to change it after first login." }),
    field("Department", department, { hint: "Optional — shown beside their name when assigning tickets." }));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(submit, async () => {
      const agent = await api("/admin/agents", {
        method: "POST",
        json: {
          full_name: name.value,
          email: email.value.trim(),
          password: password.value,
          department: department.value.trim() || null,
        },
      });
      closeSheet();
      toast(`${agent.user.full_name} can now sign in as an agent.`, "success");
      onDone();
    });
  });

  openSheet({
    title: "Add an agent",
    body: form,
    footer: [h("button", { class: "btn btn-secondary", type: "button", onclick: closeSheet }, "Cancel"), submit],
  });
}

/* ---------------------------------------------------------- categories */

function renderCategories() {
  const addButton = h("button", { class: "btn", type: "button", onclick: () => openCategorySheet(load) },
    icon("plus"), "Add category");
  shell.setHeader("Categories", {
    subtitle: "What customers can file a complaint under.",
    actions: [addButton],
  });

  const results = h("div", {});
  shell.body.replaceChildren(h("section", { class: "card" }, results));

  function load() {
    return loadInto(results, skeletonRows(4), async () => {
      const categories = await api("/admin/categories");
      shell.setNavCount("categories", categories.length || "");

      const rows = categories.map((category) => {
        const toggle = h("button", {
          class: `btn btn-sm ${category.is_active ? "btn-danger" : "btn-secondary"}`,
          type: "button",
        }, category.is_active ? "Deactivate" : "Activate");
        toggle.addEventListener("click", () =>
          guarded(toggle, async () => {
            await api(`/admin/categories/${category.id}`, {
              method: "PATCH", json: { is_active: !category.is_active },
            });
            toast(`${category.name} ${category.is_active ? "deactivated" : "activated"}.`, "success");
            await load();
          }));

        return h("tr", {},
          h("td", { class: "strong" }, category.name),
          h("td", { class: "muted" }, category.description || "—"),
          h("td", {}, h("span", { class: `badge ${category.is_active ? "state-active" : "state-disabled"}` },
            category.is_active ? "Active" : "Inactive")),
          h("td", { class: "col-actions" }, h("span", { class: "row-action" }, toggle)));
      });

      return tableOrEmpty(rows,
        ["Category", "Description", "Status", { label: "", align: "right" }],
        emptyState({
          icon: "tags",
          title: "No categories yet",
          text: "Add a category so complaints can be sorted by type.",
          action: h("button", { class: "btn", type: "button", onclick: () => openCategorySheet(load) }, "Add category"),
        }));
    });
  }
  load();
}

function openCategorySheet(onDone) {
  const name = h("input", { type: "text", minlength: "2", maxlength: "100", placeholder: "Billing", required: true });
  const description = h("input", { type: "text", maxlength: "255", placeholder: "Payments, refunds and invoices" });
  const submit = h("button", { class: "btn", type: "submit", form: "category-form" }, "Create category");

  const form = h("form", { id: "category-form" },
    field("Name", name),
    field("Description", description, { hint: "Optional — helps customers pick the right one." }));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(submit, async () => {
      await api("/admin/categories", {
        method: "POST",
        json: { name: name.value, description: description.value.trim() || null },
      });
      closeSheet();
      toast("Category created.", "success");
      onDone();
    });
  });

  openSheet({
    title: "Add a category",
    body: form,
    footer: [h("button", { class: "btn btn-secondary", type: "button", onclick: closeSheet }, "Cancel"), submit],
  });
}

/* ---------------------------------------------------------- knowledge base */

// Mirrors the backend's max_upload_mb and allow-list. These checks only save the admin
// a slow, doomed upload — the server re-checks everything and is the real authority.
const MAX_UPLOAD_MB = 10;
const UPLOAD_TYPES = { ".pdf": "PDF", ".txt": "Text" };

function extensionOf(filename) {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
}

/**
 * A document goes through two steps: text extraction, then indexing (chunks + embeddings).
 * One badge shows how far it got, and the line under it says what was found or what failed.
 */
function docState(doc) {
  if (doc.status === "PENDING") return { key: "PENDING", label: "Not extracted", note: "Text not extracted yet" };
  if (doc.status === "FAILED") return { key: "FAILED", label: "Failed", note: doc.extraction_error };
  if (doc.index_status === "INDEXED") {
    return { key: "INDEXED", label: "Indexed", note: `${textSummary(doc)} · ${plural(doc.chunk_count, "chunk")}` };
  }
  if (doc.index_status === "FAILED") return { key: "INDEX_FAILED", label: "Not indexed", note: doc.index_error };
  return { key: "EXTRACTED", label: "Text ready", note: `${textSummary(doc)} · not indexed yet` };
}

function docStatusBadge(state) {
  return h("span", { class: `badge doc-${state.key}` }, state.label);
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/** Server messages may or may not end with punctuation; a toast sentence should, once. */
function sentence(text) {
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

/** One line under the badge: how much text was found, or why there is none. */
function textSummary(doc) {
  if (doc.status === "FAILED") return doc.extraction_error;
  if (doc.status !== "EXTRACTED") return "Text not extracted yet";
  const chars = `${doc.char_count.toLocaleString()} characters`;
  if (!doc.page_count) return chars;
  return `${doc.page_count} ${doc.page_count === 1 ? "page" : "pages"} · ${chars}`;
}

function announceProcessing(doc, uploaded) {
  const lead = uploaded ? `${doc.title} added.` : `${doc.title}:`;
  if (doc.status !== "EXTRACTED") {
    const failLead = uploaded ? `${doc.title} was uploaded, but its` : `${doc.title}: the`;
    toast(`${failLead} text could not be extracted. ${sentence(doc.extraction_error)}`, "info");
  } else if (doc.index_status === "INDEXED") {
    toast(`${lead} ${doc.char_count.toLocaleString()} characters extracted, ` +
      `${plural(doc.chunk_count, "chunk")} indexed.`, "success");
  } else {
    toast(`${lead} Text extracted, but indexing failed. ${sentence(doc.index_error)}`, "info");
  }
}

function renderDocuments() {
  const addButton = h("button", { class: "btn", type: "button", onclick: () => openDocumentSheet(load) },
    icon("upload"), "Upload document");
  shell.setHeader("Knowledge base", {
    subtitle: "Policies and guides that support answers are based on.",
    actions: [addButton],
  });

  const results = h("div", {});
  shell.body.replaceChildren(h("section", { class: "card" }, results));

  function load() {
    return loadInto(results, skeletonRows(4), async () => {
      const documents = await api("/admin/documents");
      shell.setNavCount("documents", documents.length || "");

      const rows = documents.map((doc) => {
        const remove = h("button", { class: "btn btn-sm btn-danger", type: "button" }, "Delete");
        remove.addEventListener("click", () => {
          if (!confirm(`Delete "${doc.title}"? The file is removed permanently.`)) return;
          guarded(remove, async () => {
            await api(`/admin/documents/${doc.id}`, { method: "DELETE" });
            toast(`${doc.title} deleted.`, "success");
            await load();
          });
        });

        // A button that runs a processing step on the server, then reloads the table.
        const stepButton = (label, path) => {
          const button = h("button", { class: "btn btn-sm btn-secondary", type: "button" }, label);
          button.addEventListener("click", () => guarded(button, async () => {
            const result = await api(`/admin/documents/${doc.id}/${path}`, { method: "POST" });
            announceProcessing(result, false);
            await load();
          }));
          return button;
        };

        // Extracted: view it, and (re)index it if indexing is not done. Otherwise: extract (again).
        const actions = [];
        if (doc.status === "EXTRACTED") {
          actions.push(h("button", { class: "btn btn-sm btn-secondary", type: "button",
            onclick: () => openDocumentViewer(doc) }, "View"));
          if (doc.index_status !== "INDEXED") {
            actions.push(stepButton(doc.index_status === "FAILED" ? "Retry indexing" : "Index", "index"));
          }
        } else {
          actions.push(stepButton(doc.status === "FAILED" ? "Retry" : "Extract text", "extract"));
        }
        const state = docState(doc);

        return h("tr", {},
          h("td", { class: "cell-subject" },
            h("span", { class: "strong", style: "display:block" }, doc.title),
            h("span", { class: "meta" }, doc.original_filename)),
          h("td", {}, h("span", { class: "badge badge-plain badge-neutral" },
            UPLOAD_TYPES[extensionOf(doc.original_filename)] || doc.content_type)),
          h("td", { class: "col-num" }, formatBytes(doc.size_bytes)),
          h("td", {}, docStatusBadge(state),
            h("span", { class: "meta doc-summary" }, state.note)),
          h("td", {}, identity(doc.uploaded_by.full_name)),
          h("td", { class: "meta" }, fmtDay(doc.created_at)),
          h("td", { class: "col-actions" }, h("span", { class: "row-action doc-actions" }, ...actions, remove)));
      });

      return tableOrEmpty(rows,
        ["Document", "Type", "Size", "Status", "Uploaded by", "Added", { label: "", align: "right" }],
        emptyState({
          icon: "file",
          title: "No documents yet",
          text: "Upload the policies your support team works from — refunds, shipping, warranty and product guides.",
          action: h("button", { class: "btn", type: "button", onclick: () => openDocumentSheet(load) },
            "Upload document"),
        }));
    });
  }
  load();
}

function openDocumentSheet(onDone) {
  const title = h("input", { type: "text", minlength: "2", maxlength: "200",
    placeholder: "Refund policy", required: true });
  const fileInput = h("input", { type: "file", accept: ".pdf,.txt,application/pdf,text/plain", required: true });
  const submit = h("button", { class: "btn", type: "submit", form: "document-form" }, "Upload");

  // Picking a file fills in an empty title from its name, which is usually what you want.
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file && !title.value.trim()) title.value = file.name.replace(/\.[^.]+$/, "");
  });

  const form = h("form", { id: "document-form" },
    field("File", fileInput, { hint: `PDF or plain-text file, up to ${MAX_UPLOAD_MB} MB.` }),
    field("Title", title, { hint: "How the document appears in the knowledge base." }));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file) { notify("Choose a file to upload."); return; }
    if (!UPLOAD_TYPES[extensionOf(file.name)]) { notify("Only PDF and .txt files can be uploaded."); return; }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) { notify(`That file is over the ${MAX_UPLOAD_MB} MB limit.`); return; }

    const body = new FormData();
    body.append("title", title.value);
    body.append("file", file);

    guarded(submit, async () => {
      const doc = await api("/admin/documents", { method: "POST", upload: body });
      closeSheet();
      announceProcessing(doc, true);
      onDone();
    });
  });

  openSheet({
    title: "Upload a document",
    body: form,
    footer: [h("button", { class: "btn btn-secondary", type: "button", onclick: closeSheet }, "Cancel"), submit],
  });
}

/** The extracted text, and the chunks made from it. Each is fetched only when shown. */
function openDocumentViewer(doc) {
  const tabs = h("div", {});
  const content = h("div", {});

  async function loadText() {
    const result = await api(`/admin/documents/${doc.id}/text`);
    return h("pre", { class: "doc-text" }, result.extracted_text);
  }

  async function loadChunks() {
    const chunks = await api(`/admin/documents/${doc.id}/chunks`);
    if (!chunks.length) {
      return emptyState({ icon: "file", title: "No chunks",
        text: doc.index_error || "This document has not been indexed yet." });
    }
    return h("div", { class: "chunk-list" }, chunks.map((chunk) =>
      h("article", { class: "chunk" },
        h("p", { class: "chunk-head" },
          `Chunk ${chunk.chunk_index} · ${chunk.word_count} words · ` +
          `${chunk.embedding_dimension} numbers from ${chunk.embedding_model}`),
        h("pre", { class: "doc-text" }, chunk.text),
        // Only the first few numbers of the vector, to show it exists and looks sane.
        h("p", { class: "meta chunk-vector" },
          `[${chunk.embedding_preview.map((x) => x.toFixed(4)).join(", ")}, …]`))));
  }

  function show(tab) {
    tabs.replaceChildren(segmented(
      [{ id: "text", label: "Text" }, { id: "chunks", label: "Chunks", count: doc.chunk_count || 0 }],
      tab, show));
    loadInto(content, skeletonRows(6), tab === "text" ? loadText : loadChunks);
  }

  openSheet({
    title: doc.title,
    body: h("div", {},
      h("p", { class: "meta" }, `${docState(doc).note} · from ${doc.original_filename}`),
      tabs,
      content),
    footer: [h("button", { class: "btn btn-secondary", type: "button", onclick: closeSheet }, "Close")],
  });
  show("text");
}
