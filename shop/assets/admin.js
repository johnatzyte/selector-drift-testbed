"use strict";

const login = document.querySelector("#admin-login");
const controls = document.querySelector("#admin-controls");
const editor = document.querySelector("#selector-editor");
const status = document.querySelector("#admin-status");
let csrf = null;

function lock() {
  csrf = null;
  login.hidden = false;
  controls.hidden = true;
  document.querySelector("#shop-preview").removeAttribute("src");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options, headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf || "", ...options.headers},
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) lock();
    throw new Error(data.key ? `${data.key}: ${data.reason}` : data.reason || data.error || "Request failed");
  }
  return data;
}

function display(state) {
  for (const [name, value] of Object.entries(state.config)) {
    const input = editor.elements.namedItem(name);
    if (input.type === "checkbox") input.checked = value;
    else input.value = value;
  }
  document.querySelector("#admin-revision").textContent = `Revision ${state.version}`;
  document.querySelector("#admin-diff").textContent = Object.entries(state.changed)
    .map(([name, change]) => `${name}: ${JSON.stringify(change.from)} → ${JSON.stringify(change.to)}`)
    .join("\n") || "Default markup. No changes applied.";
  document.querySelector("#shop-preview").src = `/coffee/beans/?preview=${state.version}`;
  status.textContent = "Shop updated. Run your scraper to check the result.";
}

async function unlock(session) {
  csrf = session.csrf;
  display(await api("/api/selectors"));
  login.hidden = true;
  controls.hidden = false;
  status.textContent = "Controls unlocked. Changes affect the original shop.";
}

async function busy(action) {
  const buttons = document.querySelectorAll("#admin-controls button, #admin-login button");
  buttons.forEach(button => { button.disabled = true; });
  try { await action(); }
  catch (error) { status.textContent = error.message; }
  finally { buttons.forEach(button => { button.disabled = false; }); }
}

login.addEventListener("submit", event => {
  event.preventDefault();
  busy(async () => {
    const key = login.elements.key.value;
    login.elements.key.value = "";
    const session = await api("/api/admin/login", {method: "POST", headers: {"X-API-Key": key}});
    await unlock(session);
  });
});

editor.addEventListener("submit", event => {
  event.preventDefault();
  busy(async () => {
    const config = {};
    for (const input of editor.elements) {
      if (input.name) config[input.name] = input.type === "checkbox" ? input.checked : input.value;
    }
    display(await api("/api/selectors", {method: "PATCH", body: JSON.stringify(config)}));
  });
});

document.querySelectorAll("[data-preset]").forEach(button => {
  button.addEventListener("click", () => busy(async () => {
    display(await api("/api/admin/preset", {method: "POST", body: JSON.stringify({name: button.dataset.preset})}));
  }));
});
document.querySelector("#admin-reset").addEventListener("click", () => busy(async () => {
  display(await api("/api/selectors/reset", {method: "POST"}));
}));
document.querySelector("#admin-logout").addEventListener("click", () => busy(async () => {
  await api("/api/admin/logout", {method: "POST"});
  lock();
  status.textContent = "Controls locked.";
}));

busy(async () => {
  const session = await api("/api/admin/session");
  if (session.authenticated) await unlock(session);
  else { lock(); status.textContent = "Enter your SHOP_API_KEY to unlock the controls."; }
});
