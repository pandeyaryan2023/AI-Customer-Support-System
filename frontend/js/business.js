"use strict";

/* Create a business (a tenant) and its first admin: POST /businesses. */

const form = document.getElementById("business-form");
const nameInput = document.getElementById("business-name");
const slugInput = document.getElementById("business-slug");
const confirmField = document.getElementById("confirm-field");
const confirmError = document.getElementById("confirm-error");
const passwordInput = document.getElementById("password");
const confirmInput = document.getElementById("confirm");

/** "Acme Store Ltd." -> "acme-store-ltd": a suggestion the user can still change. */
function slugFrom(name) {
  return name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 50);
}

let slugEdited = false;
slugInput.addEventListener("input", () => { slugEdited = true; });
nameInput.addEventListener("input", () => {
  if (!slugEdited) slugInput.value = slugFrom(nameInput.value);
});

function showMismatch(show) {
  confirmField.classList.toggle("has-error", show);
  confirmError.classList.toggle("hidden", !show);
}

confirmInput.addEventListener("input", () => {
  if (!confirmError.classList.contains("hidden")) showMismatch(false);
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (passwordInput.value !== confirmInput.value) {
    showMismatch(true);
    confirmInput.focus();
    return;
  }
  showMismatch(false);

  guarded(event.submitter, async () => {
    await api("/businesses", {
      method: "POST",
      json: {
        business_name: nameInput.value,
        business_slug: slugInput.value.trim(),
        full_name: document.getElementById("full-name").value,
        email: document.getElementById("email").value.trim(),
        password: passwordInput.value,
      },
    });
    location.href = "login.html?business_created=1";
  });
});
