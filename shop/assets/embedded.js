"use strict";

import {card, element} from "/assets/product-cards.js";

const content = document.querySelector("#embedded-content");
const status = document.querySelector("#embedded-status");

function link(text, href, className) {
  const anchor = element("a", className, text);
  anchor.href = href;
  return anchor;
}

function detail(product, category) {
  const article = element("article", "detail");
  article.dataset.sku = product.sku;
  const media = element("div", "detail-media");
  const image = element("img", "product-image");
  image.src = product.image_url;
  image.alt = "";
  media.append(image);
  const body = element("div", "detail-body");
  body.append(element("span", "card-eyebrow", product.brand));
  body.append(element("h2", "product-title", product.name));
  const meta = element("div", "detail-meta");
  const price = new Intl.NumberFormat("en-GB", {style: "currency", currency: product.currency})
    .format(product.price_minor / 100);
  meta.append(element("span", "price", price));
  meta.append(element("span", "rating", `${product.rating.toFixed(1)} (${product.reviews} reviews)`));
  meta.append(element("span", "stock", product.stock ? `${product.stock} in stock` : "Out of stock"));
  body.append(meta);
  body.append(element("p", "product-description", product.description));
  body.append(element("p", "sku-line", `SKU ${product.sku}`));
  body.append(link(`More ${category.name}`, category.url, "section-more"));
  article.append(media, body);
  const specs = element("section", "specs-block");
  specs.append(element("h2", "", "Specification"));
  const list = element("dl", "spec-list");
  for (const [name, value] of Object.entries(product.specs)) {
    const row = element("div", "spec");
    row.append(element("dt", "spec-label", name), element("dd", "spec-value", value));
    list.append(row);
  }
  specs.append(list);
  return [article, specs];
}

try {
  const props = JSON.parse(document.querySelector("#__SHOP_DATA__").textContent).props.pageProps;
  if (props.kind === "listing") {
    const grid = element("div", "product-grid");
    grid.append(...props.products.map(card));
    content.append(grid);
    const pagination = props.pagination;
    status.textContent = `${pagination.total} products — page ${pagination.page} of ${pagination.pages}.`;
    const pager = document.querySelector("#embedded-pager");
    if (pagination.previous) pager.append(link("← Previous", pagination.previous, "prev"));
    pager.append(element("span", "pager-state", `Page ${pagination.page} of ${pagination.pages}`));
    if (pagination.next) pager.append(link("Next →", pagination.next, "next"));
  } else if (props.kind === "product") {
    document.title = `${props.product.name} — Scrape Roasters`;
    content.append(...detail(props.product, props.category));
    status.textContent = "Product details loaded.";
  } else {
    throw new Error("Unknown page type");
  }
} catch (error) {
  status.textContent = "Products could not be displayed. Please reload the page.";
  console.error(error);
} finally {
  content.setAttribute("aria-busy", "false");
}
