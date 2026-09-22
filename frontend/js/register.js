"use strict";

const form = document.getElementById("register-form");
const confirmField = document.getElementById("confirm-field");
const confirmError = document.getElementById("confirm-error");
const passwordInput = document.getElementById("password");
const confirmInput = document.getElementById("confirm");
const businessInput = document.getElementById("business");
const businessHint = document.getElementById("business-hint");

// The sign-up link a company shares looks like register.html?business=acme
businessInput.value = new URLSearchParams(location.search).get("business") || "";

/** Show which company this account will belong to, so nobody joins the wrong one. */
async function describeBusiness() {
  const code = businessInput.value.trim().toLowerCase();
  if (!code) return;
  try {
    const business = await api(`/businesses/${encodeURIComponent(code)}`);
    businessHint.textContent = `You are joining ${business.name}'s support portal.`;
    businessHint.classList.remove("field-error");
  } catch {
    businessHint.textContent = "No business uses this code. Check the link you were given.";
    businessHint.classList.add("field-error");
  }
}
businessInput.addEventListener("change", describeBusiness);
describeBusiness();

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
        business: businessInput.value.trim(),
      },
    });
    location.href = "login.html?registered=1";
  });
});
