"use strict";

import {card} from "/assets/product-cards.js";

const form = document.querySelector("#live-filters");
const grid = document.querySelector("#live-products");
const status = document.querySelector("#live-status");
const more = document.querySelector("#load-more");
let nextUrl = null;
let activeController = null;

async function load(url, reset) {
  if (activeController) activeController.abort();
  const controller = new AbortController();
  activeController = controller;
  grid.setAttribute("aria-busy", "true");
  more.disabled = true;
  if (reset) {
    grid.replaceChildren();
    nextUrl = null;
    more.hidden = true;
  }
  status.textContent = "Loading products…";
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    const data = await response.json();
    if (controller.signal.aborted) return;
    grid.append(...data.products.map(card));
    nextUrl = data.next;
    more.hidden = nextUrl === null;
    more.textContent = "Load more";
    status.textContent = data.total ? `Showing ${grid.children.length} of ${data.total} products.` : "No products found. Try another search.";
  } catch (error) {
    if (error.name !== "AbortError" && activeController === controller) {
      status.textContent = "Products could not be loaded. Please try again.";
      nextUrl = url;
      more.textContent = "Try again";
      more.hidden = false;
    }
  } finally {
    if (activeController === controller) {
      activeController = null;
      grid.setAttribute("aria-busy", "false");
      more.disabled = false;
    }
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const params = new URLSearchParams(new FormData(form));
  load(`/api/products?${params}`, true);
});
more.addEventListener("click", () => {
  if (nextUrl && !activeController) load(nextUrl, false);
});
load("/api/products", true);
