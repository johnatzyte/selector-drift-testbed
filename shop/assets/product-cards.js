"use strict";

// The server's current selector config, so client-rendered markup follows admin changes too.
export const sel = JSON.parse(document.querySelector("#__SELECTORS__").textContent);

export function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function formatPrice(product) {
  return new Intl.NumberFormat("en-GB", {style: "currency", currency: product.currency})
    .format(product.price_minor / 100);
}

export function price(product) {
  const text = formatPrice(product);
  if (sel.price_in_attribute) {
    const node = element("span", sel.price_class);
    node.dataset.price = text;
    return node;
  }
  if (sel.price_split) {
    const node = element("span", sel.price_class);
    node.append(element("span", "currency", text.charAt(0)), element("span", "amount", text.slice(1)));
    return node;
  }
  return element("span", sel.price_class, text);
}

export function stock(product) {
  return element("span", sel.stock_class, product.stock ? `${product.stock} in stock` : "Out of stock");
}

export function card(product) {
  const article = element(sel.card_tag, sel.card_class);
  article.setAttribute(sel.sku_attribute, product.sku);
  const link = element("a", sel.link_class);
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
  const fields = {
    title: () => element(sel.title_tag, sel.title_class, product.name),
    price: () => price(product),
    stock: () => stock(product),
  };
  for (const name of sel.field_order.split(",")) if (fields[name]) body.append(fields[name]());
  link.append(body);
  if (sel.extra_wrapper) {
    const inner = element("div", "card-inner");
    inner.append(link);
    article.append(inner);
  } else {
    article.append(link);
  }
  return article;
}
