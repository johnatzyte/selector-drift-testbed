# Scrape Roasters — a shop that changes its selectors while you watch

A fake coffee retailer, 1000 products, whose CSS class names, tag names and value
placement can be rewritten at runtime over HTTP. Point a scraper at it, change a
selector, run the scraper again: it returns nulls. The page on screen does not move a
single pixel.

That is the whole point. The stylesheet renders from the same config dict as the
markup, so a rename carries the styling with it. The audience sees an unchanged shop;
the scraper sees a different document.

The same store now includes scraping labs and a JavaScript-powered Live Shop.
The original selector-change demo remains available at the original URLs.

## Scraping labs

After starting the app, open `/labs/` for the challenge directory:

| URL | Exercise |
| --- | --- |
| `/labs/classic/` | Fixed server-rendered shop: categories, pagination, product details, and specifications |
| `/labs/drift/` | Same catalogue with renamed titles/next-page links, extra wrappers, and split price text |
| `/live/` | JavaScript loads products through JSON; search, category filters, and load-more pagination |
| `/embedded/` | JavaScript renders products from initial JSON embedded in each HTML response; no product-data fetch |

The lab profiles have their own navigation and stylesheets. Product, category, and
pagination links stay within the selected profile. Updating `/api/selectors` changes
every part of the shop: the original pages, both labs, Live Shop and Embedded Shop.
The drift lab applies its own changes on top of the current config, so it always
differs from classic. Live Shop and Embedded Shop read the config from a
`<script id="__SELECTORS__">` tag and build their markup from it.

The robots policy now permits practice crawls and excludes the selector-control API.
The fictional catalogue still carries `X-Robots-Tag: noindex, nofollow`.

### Product JSON endpoint

`GET /api/products?page=1&page_size=25&category=beans&q=Ethiopia`

- `page`: positive integer, default 1.
- `page_size`: 1–100, default 25.
- `category`: optional category slug; unknown values return 400.
- `q`: optional case-insensitive substring of the product name.

The response includes `products`, `page`, `page_size`, `total`, and `next` (a relative
URL, or null at the end). Follow `next` until null. Unlike the original HTML paginator,
out-of-range API pages return an empty list instead of repeating the last page.
Filters and page size are preserved in next-page URLs.

Each product has SKU, name, brand, integer `price_minor` (pennies for GBP), currency,
stock, rating, category, image URL, and a link to its fixed classic detail page.
The committed catalogue and existing displayed prices have not been regenerated.

### Checks

`uv run --locked pytest -q` checks the original demo plus lab profiles, navigation,
concurrent rendering, CSS revisions, complete JSON pagination, filters, and API errors.
`bash scripts/smoke.sh` also builds/starts the container and checks HTTP lab routes.

For an optional real-browser check, start the shop, then run:

```bash
uv run --with playwright==1.62.0 playwright install chromium
uv run --with playwright==1.62.0 python scripts/browser_smoke.py
```

Pass `--base http://127.0.0.1:8812` for another port. This checks loading, pagination,
filters, failed-request retry, product images, mobile width, and drift navigation.
Screenshots are written to ignored `artifacts/`.

### Embedded-data exercise

The Embedded Shop has a 40-page catalogue, section/category listings, and product
details. Navigation stays under `/embedded/`, and its rendered markup follows admin
selector changes like the rest of the shop.

Raw HTML has an empty product container and an initial-state script:

```html
<script id="__SHOP_DATA__" type="application/json">…</script>
```

Parse that script as JSON, then read `props.pageProps`. Listing pages contain
`products` and `pagination` (`next`/`previous` URLs, null at the ends); detail pages
contain `product` with description and specifications. `schemaVersion` is 1.
Prices use the same integer `price_minor` values as Live Shop. Each response includes
only the current page's products. Invalid page numbers return 400; pages beyond the
last return 404. All 1,000 products can be collected directly from HTML, without a
browser or the Live Shop API.

This is framework-independent initial-state rendering: the browser constructs DOM
from JSON. It demonstrates the embedded-data discovery technique without claiming to
be a Next.js application or literal hydration of server-rendered product markup.
JSON uses template-safe serialization, and product values are rendered as text.

Optional browser check:

```bash
uv run --with playwright==1.62.0 python scripts/embedded_browser_smoke.py
```

It checks displayed values, next/previous/category/detail navigation, mobile width,
the no-JavaScript fallback, and that no fetch/XHR product requests occur.

Product configuration/shipping interactions and recording-run controls remain future work.

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

### Use the admin page

Open `/admin/` (also linked in the footer) and unlock it with `SHOP_API_KEY`.
Choose Rename titles, Split price text, Change next-page link, Change card structure,
or Combined changes. Each preset replaces previous changes. The applied-change summary
shows what changed, and the embedded original-shop preview reloads automatically.

For precise control, expand the advanced editor, change fields, and click Apply changes.
Reset defaults restores the original markup. Controls affect every part of the shop. Settings remain in memory and reset on restart.

The key is exchanged for a four-hour signed, HttpOnly browser session and is not kept
in browser local storage. Mutations require a session CSRF token or the existing API
key header. Lock controls signs out. The control page uses fixed styles so renaming
shop selectors does not break the editor itself.

Set `SHOP_SESSION_SECRET` for stable session signing across restarts and
`SHOP_SECURE_COOKIES=1` when serving over HTTPS. Keep `.env` private. For the current
LAN preview, the generated admin key is stored in the gitignored `.env` file.

Optional browser check against a test instance (changes live settings, then resets):

```bash
uv run --with playwright==1.62.0 python scripts/admin_browser_smoke.py --key-file .env
```

### Use the API

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
order can be placed. `/robots.txt` allows practice crawling while excluding selector
controls, and `X-Robots-Tag: noindex, nofollow` requests that search engines keep the
fictional catalogue out of results. Keep development crawls small and sensibly paced.

## Notes for the day

- Legacy selector config lives in memory. `docker compose restart` resets it, which is a
  feature, but know that a laptop sleep does the same.
- Fonts are checked into `shop/assets/fonts/`, so nothing is fetched from Google. The
  shop works with the wifi off.
- Product images are inline SVG generated from the sku. No image requests at all.
- The dev reloader is off on purpose — it would restart the process and wipe your
  config mid-demo.
- Present in a fresh browser window. The stylesheet is sent `no-store` and its URL
  carries a version counter. Each render uses request-local settings; legacy CSS URLs
  resolve their matching snapshot (the most recent 256 revisions, until restart).
  An expired revision returns 404. Fixed lab stylesheets do not use the legacy store.

## Licence

MIT — see [LICENSE](LICENSE).
