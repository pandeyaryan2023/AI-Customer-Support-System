"use strict";

/* The one complaint form, shared by the customer pages and the support widget.
   "Talk to Human Support" opens it too: prefilled from the question the assistant could not
   answer, and sending the handoff token so the team sees that context. */

let complaintCategories = null; // loaded once, the first time they are needed

/** Load the categories ahead of time, so the form opens instantly. */
async function preloadComplaintCategories() {
  if (complaintCategories !== null) return;
  try {
    complaintCategories = await api("/categories");
  } catch {
    complaintCategories = []; // the complaint form still works without a category
  }
}

async function openComplaintSheet({ question = "", handoffToken = null, onCreated = null } = {}) {
  await preloadComplaintCategories();
  const fromAssistant = Boolean(handoffToken);
  const title = h("input", { type: "text", minlength: "5", maxlength: "200",
    placeholder: "e.g. Charged twice for the same order", required: true });
  const category = h("select", {}, option("", "Not sure / other"),
    complaintCategories.map((c) => option(c.id, c.name)));
  const description = h("textarea", { minlength: "10", maxlength: "5000",
    placeholder: "What happened? Include any order or reference numbers.", required: true });

  if (fromAssistant) {
    title.value = complaintTitleFrom(question);
    description.value = `I asked the support assistant: "${question}"\n\n`;
  }

  const submit = h("button", { class: "btn", type: "submit", form: "complaint-form" }, "Submit complaint");

  const form = h("form", { id: "complaint-form" },
    fromAssistant ? h("p", { class: "meta handoff-note" }, icon("info"),
      "Your question and what the assistant found are attached, so our team sees them straight away.") : null,
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
          handoff_token: handoffToken || undefined,
        },
      });
      closeSheet();
      // From the assistant: open the new ticket, which shows its number and status.
      if (fromAssistant) { location.href = `ticket.html?id=${ticket.id}`; return; }
      toast(`Complaint #${ticket.id} submitted. We'll be in touch.`, "success");
      if (onCreated) onCreated(ticket);
    });
  });

  openSheet({
    title: fromAssistant ? "Talk to human support" : "Raise a complaint",
    body: form,
    footer: [h("button", { class: "btn btn-secondary", type: "button", onclick: closeSheet }, "Cancel"), submit],
  });
}

function complaintTitleFrom(question) {
  const text = question.replace(/\s+/g, " ").trim();
  if (text.length < 5) return `Question: ${text}`;  // titles need at least 5 characters
  return text.length <= 200 ? text : `${text.slice(0, 197)}…`;
}
