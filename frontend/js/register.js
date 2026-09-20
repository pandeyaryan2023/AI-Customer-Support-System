"use strict";

const form = document.getElementById("register-form");
const confirmField = document.getElementById("confirm-field");
const confirmError = document.getElementById("confirm-error");
const passwordInput = document.getElementById("password");
const confirmInput = document.getElementById("confirm");

/** Inline error under the confirm field — shown on submit, cleared as soon as it matches. */
function showMismatch(show) {
  confirmField.classList.toggle("has-error", show);
  confirmError.classList.toggle("hidden", !show);
}

confirmInput.addEventListener("input", () => {
  if (!confirmError.classList.contains("hidden")) showMismatch(false);
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const password = passwordInput.value;

  if (password !== confirmInput.value) {
    showMismatch(true);
    confirmInput.focus();
    return;
  }
  showMismatch(false);

  guarded(event.submitter, async () => {
    await api("/auth/register", {
      method: "POST",
      json: {
        full_name: document.getElementById("full-name").value,
        email: document.getElementById("email").value.trim(),
        password,
      },
    });
    location.href = "login.html?registered=1";
  });
});
