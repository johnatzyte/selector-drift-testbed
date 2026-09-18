# Scrape Roasters — a shop that changes its selectors while you watch

A fake coffee retailer, 1000 products, whose CSS class names, tag names and value
placement can be rewritten at runtime over HTTP. Point a scraper at it, change a
selector, run the scraper again: it returns nulls. The page on screen does not move a
single pixel.

That is the whole point. The stylesheet renders from the same config dict as the
markup, so a rename carries the styling with it. The audience sees an unchanged shop;
the scraper sees a different document.

## Run it

```bash
docker compose up
```

Then open http://localhost:8811. Set `PORT` to use a different port.

Without Docker:

```bash
uv sync
./scripts/demo.sh
```

### Deploying it to a droplet

```bash
cp .env.example .env          # set SHOP_API_KEY to something from `openssl rand -base64 24`
docker compose up -d --build
```

The container runs **gunicorn** (`shop.wsgi:app`, config in `gunicorn.conf.py`), with
`forwarded_allow_ips = "*"` so it trusts the `X-Forwarded-*` headers Caddy sets. The
Flask dev server is only used by `./scripts/demo.sh` for local work.

> **`workers` must stay at 1.**
>
> The selector config lives in process memory. Two workers means two independent
> copies: a `PATCH` lands in one of them, and page loads then alternate between old and
> new markup at random. It is intermittent, it logs nothing, and you would find out
> about it on stage. Concurrency comes from threads instead (`THREADS`, default 8),
> which share the one config.

Two other things for a public IP: terminate TLS in front of it, because the API key
crosses the network in cleartext over plain HTTP; and do not open 8811 to the world when
a proxy is already fronting it.

### Viewing it from another machine

Both paths bind `0.0.0.0`, so if you are SSH'd into the box you can just open it from
your laptop — no tunnel, no config change:

```
http://<host-lan-ip>:8811
```

Set `HOST=127.0.0.1` to keep it on the loopback instead. Changing selectors needs the
API key either way — see [Break it](#break-it).

## Break it

Changing selectors needs an API key in an `X-API-Key` header. Reads do not — the class
names are in the page source anyway.

```bash
export SHOP_API_KEY=...   # printed at startup if you did not set one

# what has drifted from the defaults (no key needed)
curl -s localhost:8811/api/selectors | jq .changed

# rename a class — the shop looks identical, the scraper does not
curl -s -X PATCH localhost:8811/api/selectors \
  -H "X-API-Key: $SHOP_API_KEY" \
  -H 'content-type: application/json' \
  -d '{"title_class": "item-name"}'

# put it back
curl -s -X POST localhost:8811/api/selectors/reset -H "X-API-Key: $SHOP_API_KEY"
```

`POST` works the same as `PATCH` if that is easier to type on stage.

**There is no unauthenticated mode.** If `SHOP_API_KEY` is unset the app generates a
random key at boot and prints it, rather than running open — so a forgotten environment
variable can never leave a public box writable by strangers. A generated key changes on
every restart, so set your own before deploying anywhere.

## What you can change

Rename any of these classes: `grid_class`, `card_class`, `title_class`, `price_class`,
`link_class`, `rating_class`, `stock_class`, `next_page_class`, `breadcrumb_class`,
`subnav_class`, `spec_class`, `spec_label_class`, `spec_value_class`.

Values must match `^[a-z][a-z0-9-]{0,39}$`. Anything else is a `400`, and so is an
unknown key — a typo that silently did nothing would be the worst thing that could
happen mid-talk.

Structural changes:

| key | effect | what it breaks |
|---|---|---|
| `title_tag` | `h2` `h3` `h4` `div` `span` `p` | `h3.product-title` |
| `card_tag` | `article` `div` `li` `section` | `article.product-card` |
| `extra_wrapper` | inserts a `div` inside each card | any `>` child combinator |
| `price_in_attribute` | price moves to `data-price`, CSS paints it back | `.price::text` |
| `price_split` | price splits into currency + amount spans | `.price::text` returns `£` only |
| `id_to_class` | detail page `id="product-description"` becomes a class | `#product-description` |
| `sku_attribute` | renames `data-sku` | `[data-sku]` |
| `field_order` | reorders title/price/rating/stock in the card | positional selectors, `nth-child` |

`next_page_class`, `breadcrumb_class` and `subnav_class` are the interesting ones:
renaming those breaks *crawling*, not just parsing, so the scraper quietly collects one
page instead of twelve.

## The shop

1000 products over two levels:

```
Coffee       beans 300 · pods-capsules 80 · decaf 70
Equipment    espresso-machines 120 · grinders 100 · brewers 90
Accessories  tampers-scales 70 · filters 60 · cleaning 60 · kettles 50
```

Listings paginate 25 to a page, so Beans runs to 12. Fields differ by category — beans carry origin, roast
and process; machines carry wattage, boiler and warranty — so a scraper needs different
selectors per category, and one drift can break a category while the rest keep working.

`shop/data/catalogue.json` is committed and is the only source of products. Regenerate
it with `uv run python tools/generate_catalogue.py`; it is seeded, so the output is
identical every time.

## Checks before you present

```bash
bash scripts/smoke.sh
```

Runs the test suite, builds the image, boots it, renames a class over HTTP, confirms the
change landed in both the markup and the stylesheet, resets, and tears down.

The test that matters most is `test_every_rendered_class_is_styled`: every class that
reaches the browser must have a rule in the stylesheet, under every drift setting. That
is what guarantees the page never *looks* broken — which is the only reason the demo
lands.

## Not a real shop

Every product, price, brand and review count is invented. Nothing is for sale and no
order can be placed. The site serves `Disallow: /` at `/robots.txt` and sends
`X-Robots-Tag: noindex, nofollow` on every response, so a fictional catalogue does not
end up in anyone's search results.

Your own scrapers will ignore `robots.txt` unless you configure them to respect it, so
this does not get in the way of the demo.

## Notes for the day

- Selector config lives in memory. `docker compose restart` resets it, which is a
  feature, but know that a laptop sleep does the same.
- Fonts are checked into `shop/assets/fonts/`, so nothing is fetched from Google. The
  shop works with the wifi off.
- Product images are inline SVG generated from the sku. No image requests at all.
- The dev reloader is off on purpose — it would restart the process and wipe your
  config mid-demo.
- Present in a fresh browser window. The stylesheet is sent `no-store` and its URL
  carries a version counter, but a window left open since rehearsal is still the most
  likely thing to confuse you.

## Licence

MIT — see [LICENSE](LICENSE).
