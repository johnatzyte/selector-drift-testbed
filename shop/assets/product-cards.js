"use strict";

export function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function card(product) {
  const article = element("article", "product-card");
  article.dataset.sku = product.sku;
  const link = element("a", "product-link");
  link.href = product.url;
  const thumb = element("div", "thumb");
  const image = element("img", "product-image");
  image.src = product.image_url;
  image.alt = "";
  image.loading = "lazy";
  thumb.append(image);
  link.append(thumb);
  const body = element("div", "card-body");
  body.append(element("span", "card-eyebrow", product.brand));
  body.append(element("h3", "product-title", product.name));
  body.append(element("span", "price", new Intl.NumberFormat("en-GB", {
    style: "currency", currency: product.currency,
  }).format(product.price_minor / 100)));
  body.append(element("span", "stock", product.stock ? `${product.stock} in stock` : "Out of stock"));
  link.append(body);
  article.append(link);
  return article;
}
