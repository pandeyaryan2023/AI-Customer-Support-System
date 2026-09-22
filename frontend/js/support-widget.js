"use strict";

/* Customer support widget: a floating button (bottom-right) that opens a small chat panel.
   It uses the same POST /ai/ask as before: a grounded answer with its sources, or
   "not enough information" with the existing human handoff (the shared complaint form).
   Only customers get it; agents and admins keep their own interface. */

const supportWidget = createSupportWidget();

function createSupportWidget() {
  const session = getSession();
  if (!session || session.role !== "CUSTOMER") return null;

  const title = `${session.business || "Customer"} Support`;
  let busy = false;

  const launcher = h("button", {
    class: "sw-launcher", type: "button", "aria-label": `Open ${title} chat`,
    "aria-expanded": "false", "aria-controls": "support-widget",
  }, icon("message"));

  const log = h("div", { class: "sw-log", role: "log", "aria-live": "polite", "aria-label": "Conversation" },
    botMessage(h("p", {}, "Hi! Ask a question and I'll answer from our help articles. "
      + "If they don't cover it, you can reach our support team.")));

  const input = h("textarea", {
    id: "sw-question", class: "sw-input", rows: "1", maxlength: "500",
    placeholder: "Ask a question…", "aria-label": "Your question",
  });
  const send = h("button", { class: "btn sw-send", type: "submit" }, icon("send"), "Ask");
  const form = h("form", { class: "sw-form" }, input, send);

  const panel = h("section", {
    id: "support-widget", class: "sw-panel", role: "dialog", "aria-modal": "false", "aria-labelledby": "sw-title",
  },
    h("header", { class: "sw-head on-ink" },
      h("span", { class: "sw-avatar", "aria-hidden": "true" }, icon("headset")),
      h("div", { class: "sw-head-text" },
        h("h2", { id: "sw-title", class: "sw-title" }, title),
        h("p", { class: "sw-sub" }, "AI answers from our help articles")),
      h("button", { class: "icon-btn sw-close", type: "button", "aria-label": "Close support chat", onclick: () => close() },
        icon("close"))),
    log,
    form,
    h("p", { class: "sw-foot" }, "Answers come only from our help articles. It can take up to a minute."));
  panel.hidden = true;

  document.body.classList.add("has-support-widget");
  document.body.append(panel, launcher);

  function open() {
    panel.hidden = false;
    launcher.setAttribute("aria-expanded", "true");
    document.body.classList.add("sw-open");
    scrollToEnd();
    input.focus();
  }

  function close({ returnFocus = true } = {}) {
    panel.hidden = true;
    launcher.setAttribute("aria-expanded", "false");
    document.body.classList.remove("sw-open");
    if (returnFocus) launcher.focus();
  }

  launcher.addEventListener("click", () => (panel.hidden ? open() : close()));
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close();
    }
  });

  // Enter asks; Shift+Enter starts a new line. The box grows with the text, up to a limit.
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", resizeInput);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (busy) return;
    if (question.length < 2) { input.focus(); return; }

    busy = true;
    input.value = "";
    resizeInput();
    append(h("div", { class: "sw-msg sw-user" }, h("p", {}, question)));
    const typing = append(botMessage(
      h("span", { class: "sw-dots", "aria-hidden": "true" }, h("span", {}), h("span", {}), h("span", {})),
      h("span", { class: "sw-typing-text" }, "Searching our help articles…")));
    typing.classList.add("sw-typing");
    typing.setAttribute("aria-busy", "true");
    setLoading(send, true);
    input.disabled = true;
    try {
      const reply = await api("/ai/ask", { method: "POST", json: { question } });
      typing.replaceWith(reply.status === "ANSWERED" ? answerMessage(reply) : notFoundMessage(reply, question));
    } catch (error) {
      typing.replaceWith(botMessage(h("p", { class: "sw-error" }, icon("alert"), error.message)));
    } finally {
      busy = false;
      setLoading(send, false);
      input.disabled = false;
      scrollToEnd();
      input.focus();
    }
  });

  function answerMessage(reply) {
    return botMessage(
      h("span", { class: "badge badge-plain ai-label" }, icon("info"), "AI-generated answer based on company knowledge"),
      h("p", { class: "sw-answer" }, reply.answer),
      h("p", { class: "sw-sources-title" }, "Sources"),
      h("ul", { class: "source-list" }, reply.sources.map((source) =>
        h("li", { class: "source-item" },
          icon("file"),
          h("span", { class: "strong" }, source.document_title),
          h("span", { class: "meta" }, `Part ${source.chunk_index + 1}`),
          h("span", { class: "meta source-score", title: "How closely this passage matched your question (0 to 1)" },
            `Relevance ${source.similarity.toFixed(2)}`)))),
      h("p", { class: "meta" },
        "This answer was written by AI from the sources above. If something looks wrong, contact our support team."));
  }

  /* Nothing is created here: the customer decides whether to hand the question to a person. */
  function notFoundMessage(reply, question) {
    const talk = reply.handoff_token
      ? h("button", { class: "btn btn-sm sw-talk", type: "button" }, icon("headset"), "Talk to Human Support")
      : null;
    if (talk) {
      talk.addEventListener("click", () => {
        close({ returnFocus: false }); // the complaint form takes over
        openComplaintSheet({ question, handoffToken: reply.handoff_token });
      });
    }
    return botMessage(
      h("p", { class: "sw-notfound-title" }, icon("search"), "Our help articles don't cover this"),
      h("p", {}, talk ? `${reply.answer} Our support team can help you with it.`
        : `${reply.answer} Try rephrasing your question.`),
      talk);
  }

  function botMessage(...children) {
    return h("div", { class: "sw-msg sw-bot" }, ...children);
  }

  function append(node) {
    log.append(node);
    scrollToEnd();
    return node;
  }

  function scrollToEnd() {
    log.scrollTop = log.scrollHeight;
  }

  function resizeInput() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }

  return { open, close };
}
