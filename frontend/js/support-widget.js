"use strict";

/* Customer support widget: a floating button (bottom-right) that opens a small chat panel.
   It uses the same POST /ai/ask as before. The reply says which kind of message it was
   (`intent`), and each kind looks different: a company answer carries the help articles it came
   from, a general answer says plainly that it is not company information, a complaint or a
   request for a person offers the support team instead (the existing handoff + complaint form),
   and hello, thanks, goodbye and small talk are plain chat, with nothing attached.
   Only customers get it; agents and admins keep their own interface. */

const supportWidget = createSupportWidget();

/* Replies that are simply conversation: no badge, no sources, no next step. */
const CHAT_INTENTS = ["GREETING", "THANKS", "FAREWELL", "ACKNOWLEDGEMENT", "CASUAL_CONVERSATION"];

function createSupportWidget() {
  const session = getSession();
  if (!session || session.role !== "CUSTOMER") return null;

  const title = `${session.business || "Customer"} Support`;
  // The signed-in customer's own first name, as the server sent it at login.
  const firstName = /^[\p{L}][\p{L}'\-.]{0,19}$/u.test((session.name || "").trim().split(" ")[0] || "")
    ? session.name.trim().split(" ")[0]
    : null;
  let busy = false;

  const launcher = h("button", {
    class: "sw-launcher", type: "button", "aria-label": `Open ${title} chat`,
    "aria-expanded": "false", "aria-controls": "support-widget",
  }, icon("message"));

  const log = h("div", { class: "sw-log", role: "log", "aria-live": "polite", "aria-label": "Conversation" },
    botMessage(h("p", {}, `${firstName ? `Hi ${firstName}!` : "Hi there!"} 👋 Ask me about our policies, `
      + "orders or products and I'll answer from our help articles. If something has gone wrong, "
      + "our support team can take it on.")));

  const input = h("textarea", {
    id: "sw-question", class: "sw-input", rows: "1", maxlength: "500",
    placeholder: "Type a message…", "aria-label": "Your message",
  });
  const send = h("button", { class: "btn sw-send", type: "submit" }, icon("send"), "Send");
  const form = h("form", { class: "sw-form" }, input, send);

  const panel = h("section", {
    id: "support-widget", class: "sw-panel", role: "dialog", "aria-modal": "false", "aria-labelledby": "sw-title",
  },
    h("header", { class: "sw-head on-ink" },
      h("span", { class: "sw-avatar", "aria-hidden": "true" }, icon("headset")),
      h("div", { class: "sw-head-text" },
        h("h2", { id: "sw-title", class: "sw-title" }, title),
        h("p", { class: "sw-sub" }, "AI answers, with a person when you need one")),
      h("button", { class: "icon-btn sw-close", type: "button", "aria-label": "Close support chat", onclick: () => close() },
        icon("close"))),
    log,
    form,
    h("p", { class: "sw-foot" }, "Questions about us are answered only from our help articles. "
      + "It can take up to a minute."));
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
      h("span", { class: "sw-typing-text" }, "Reading your message…")));
    typing.classList.add("sw-typing");
    typing.setAttribute("aria-busy", "true");
    setLoading(send, true);
    input.disabled = true;
    try {
      const reply = await api("/ai/ask", { method: "POST", json: { question } });
      typing.replaceWith(replyMessage(reply, question));
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

  /* One message per kind of reply. An intent we don't know is shown as a company answer, which is
     the careful one: it only repeats our own articles, and says so. */
  function replyMessage(reply, question) {
    if (CHAT_INTENTS.includes(reply.intent) && reply.status === "ANSWERED") return chatMessage(reply);
    if (reply.intent === "GENERAL" && reply.status === "ANSWERED") return generalMessage(reply);
    if (reply.intent === "COMPLAINT") {
      return requestMessage(reply, question, "ticket", "Support request", "Raise a Complaint");
    }
    if (reply.intent === "HUMAN_HANDOFF") {
      return requestMessage(reply, question, "headset", "Our support team", "Talk to Human Support");
    }
    return reply.status === "ANSWERED" ? answerMessage(reply) : notFoundMessage(reply, question);
  }

  function answerMessage(reply) {
    return botMessage(
      h("span", { class: "badge badge-plain ai-label" }, icon("info"), "AI Support · answered from our help articles"),
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

  /* Hello, thanks, goodbye and small talk: just what was said, like a person would reply. */
  function chatMessage(reply) {
    return botMessage(h("p", { class: "sw-answer" }, reply.answer));
  }

  /* A general answer, with no company article behind it. It must not look like one: no sources,
     and a plain note that it is general information. */
  function generalMessage(reply) {
    return botMessage(
      h("span", { class: "badge badge-plain sw-general-label" }, icon("message"), "AI Assistant · general question"),
      h("p", { class: "sw-answer" }, reply.answer),
      h("p", { class: "meta" }, "General information, not from our help articles. "
        + "Ask about us and I'll answer from them instead."));
  }

  /* A complaint, or a request for a person. Nothing is created here: the customer chooses. */
  function requestMessage(reply, question, glyph, title, label) {
    return botMessage(
      h("p", { class: "sw-msg-title" }, icon(glyph), title),
      h("p", {}, reply.answer),
      handoffButton(reply, question, label));
  }

  function notFoundMessage(reply, question) {
    const talk = handoffButton(reply, question, "Talk to Human Support");
    return botMessage(
      h("p", { class: "sw-msg-title" }, icon("search"), "Our help articles don't cover this"),
      h("p", {}, talk ? `${reply.answer} Our support team can help you with it.`
        : `${reply.answer} Try rephrasing your question.`),
      talk);
  }

  /* Hands the message to the existing complaint form; the ticket is created only from there. */
  function handoffButton(reply, question, label) {
    if (!reply.handoff_token) return null;
    const talk = h("button", { class: "btn btn-sm sw-talk", type: "button" }, icon("headset"), label);
    talk.addEventListener("click", () => {
      close({ returnFocus: false }); // the complaint form takes over
      openComplaintSheet({ question, handoffToken: reply.handoff_token });
    });
    return talk;
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
