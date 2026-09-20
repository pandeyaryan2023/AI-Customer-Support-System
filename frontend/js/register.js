"use strict";

document.getElementById("register-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const password = document.getElementById("password").value;

  if (password !== document.getElementById("confirm").value) {
    clearNotice();
    notify("The two passwords do not match.");
    return;
  }

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
