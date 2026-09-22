"use strict";

const existing = getSession();
if (existing) location.replace(DASHBOARD[existing.role]);

if (new URLSearchParams(location.search).get("registered")) {
  toast("Account created. Log in to continue.", "success");
}
if (new URLSearchParams(location.search).get("business_created")) {
  toast("Your business is ready. Log in as its admin to add agents and help articles.", "success");
}

document.getElementById("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  guarded(event.submitter, async () => {
    // 1. Log in: the backend checks the password and returns a JWT.
    const token = await api("/auth/login", { method: "POST", form: { username: email, password } });
    saveSession({ token: token.access_token, role: token.role, name: token.full_name,
      business: token.business_name });

    // 2. Ask who we are, to remember our user id (used for "is this my ticket?" checks).
    const me = await api("/auth/me");
    saveSession({ token: token.access_token, role: me.role, name: me.full_name, id: me.id,
      business: me.business.name, businessSlug: me.business.slug });

    location.replace(DASHBOARD[me.role]);
  });
});
