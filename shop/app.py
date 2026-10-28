from datetime import timedelta
import os
import secrets
from pathlib import Path

from flask import Flask, Response, abort, g, jsonify, render_template, request, send_from_directory, url_for
from markupsafe import Markup

from .auth import require_key, resolve_key
from .catalogue import load_catalogue, paginate, product_record
from .config import DEFAULTS, SelectorStore, UnknownKeys, ValidationError
from .images import svg_for
from .admin import admin_blueprint
from .embedded import embedded_blueprint

SITE_NAME = "Scrape Roasters"
# Overrides applied on top of the live selector config, so admin changes reach every
# profile while drift still differs from classic.
PROFILES = {
    "classic": {},
    "drift": {"title_class": "item-name", "price_split": True,
              "extra_wrapper": True, "next_page_class": "forward"},
}

FONTS = Path(__file__).resolve().parent / "assets" / "fonts"


def register_jinja_globals(app, store):
    """Expose the selector config to templates.

    Nothing in a template or the stylesheet ever writes a class name literally — both
    go through these helpers against the same dict, so they cannot drift apart.
    """

    def sel(key):
        return g.selectors[key]

    # Values are allowlisted to ^[a-z][a-z0-9-]{0,39}$ in config.py, so nothing that
    # reaches Markup here can carry a quote, angle bracket, brace or semicolon.
    app.jinja_env.globals.update(
        sel=sel,
        cls=lambda key: Markup(f'class="{sel(key)}"'),
        css=lambda key: Markup(f".{sel(key)}"),
        tag=lambda key: Markup(sel(key)),
        svg_for=svg_for,
        site_name=SITE_NAME,
        selector_version=lambda: g.selector_version,
        shop_url=shop_url,
        stylesheet_url=lambda: (f"/labs/{g.profile}/assets/site.css?v={g.selector_version}" if g.profile
                                else url_for("stylesheet", v=g.selector_version)),
    )


def shop_url(path="/"):
    """Keep shop navigation inside a fixed lab profile."""
    if (request.endpoint or "").startswith("embedded."):
        return f"/embedded{path}"
    return f"/labs/{g.profile}{path}" if g.profile else path


def create_app(catalogue=None, store=None, api_key=None):
    app = Flask(__name__)
    app.secret_key = os.environ.get("SHOP_SESSION_SECRET") or secrets.token_urlsafe(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      SESSION_COOKIE_SECURE=os.environ.get("SHOP_SECURE_COOKIES") == "1",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=4))
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    catalogue = catalogue or load_catalogue()
    store = store or SelectorStore()
    key, configured = (api_key, True) if api_key else resolve_key()
    app.extensions["store"] = store
    app.extensions["catalogue"] = catalogue
    app.extensions["api_key"] = key
    app.extensions["api_key_configured"] = configured
    if not configured:
        # Printed here rather than in __main__ so it also reaches the container logs
        # under gunicorn, which never imports __main__.
        print(
            f"\n  SHOP_API_KEY was not set, so this run generated one:\n\n"
            f"    export SHOP_API_KEY={key}\n\n"
            f"  It changes on every restart. Set it yourself before deploying.\n",
            flush=True,
        )
    register_jinja_globals(app, store)

    @app.before_request
    def _snapshot_selectors():
        # One snapshot per request, so a mutation mid-render cannot split a page
        # between two configs.
        g.selectors, g.selector_version, g.profile = dict(DEFAULTS), 0, None
        profile = (request.view_args or {}).get("profile")
        if profile and profile not in PROFILES:
            abort(404)
        g.profile = profile
        if (request.endpoint or "").startswith("admin."):
            # The control page keeps fixed styles so renaming selectors cannot break it.
            g.selectors, g.selector_version, g.profile = dict(DEFAULTS), 1, "classic"
            return
        if request.endpoint in {"live", "labs", "live_script", "products_api"} or (request.endpoint or "").startswith("embedded."):
            g.profile = "classic"
        try:
            version = request.args.get("v", type=int) if request.endpoint == "stylesheet" else None
            g.selectors, g.selector_version = store.capture(version)
        except KeyError:
            abort(404)
        g.selectors.update(PROFILES[g.profile] if g.profile else {})

    @app.context_processor
    def _nav():
        return {"sections_nav": catalogue.sections}

    @app.after_request
    def _no_store(response):
        if response.mimetype in ("text/html", "text/css"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
        # A fictional shop with invented prices has no business in search results.
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.get("/robots.txt")
    def robots():
        return Response("User-agent: *\nAllow: /\nDisallow: /api/selectors\nDisallow: /admin/\nDisallow: /api/admin/\n", mimetype="text/plain")

    @app.get("/")
    @app.get("/labs/<profile>/")
    def landing(profile=None):
        featured = {s["slug"]: catalogue.in_category(s["slug"], s["categories"][0]["slug"])[:4] for s in catalogue.sections}
        return render_template("landing.html", sections=catalogue.sections, featured=featured, total=len(catalogue.products))

    @app.get("/product/<slug>")
    @app.get("/labs/<profile>/product/<slug>")
    def product(slug, profile=None):
        item = catalogue.by_slug.get(slug)
        if item is None:
            abort(404)
        section = catalogue.section(item["section"])
        category = catalogue.category(item["section"], item["category"])
        related = [p for p in catalogue.in_category(item["section"], item["category"]) if p["slug"] != slug][:4]
        return render_template("product.html", product=item, section=section, category=category, related=related)

    @app.get("/<section_slug>/")
    @app.get("/labs/<profile>/<section_slug>/")
    def section(section_slug, profile=None):
        found = catalogue.section(section_slug)
        if found is None:
            abort(404)
        samples = {c["slug"]: catalogue.in_category(section_slug, c["slug"])[:3] for c in found["categories"]}
        return render_template("section.html", section=found, samples=samples)

    @app.get("/<section_slug>/<category_slug>/")
    @app.get("/labs/<profile>/<section_slug>/<category_slug>/")
    def listing(section_slug, category_slug, profile=None):
        found = catalogue.category(section_slug, category_slug)
        if found is None:
            abort(404)
        try:
            requested = int(request.args.get("page", 1))
        except ValueError:
            requested = 1
        items, page, total_pages = paginate(catalogue.in_category(section_slug, category_slug), requested)
        return render_template(
            "listing.html",
            section=catalogue.section(section_slug),
            category=found,
            products=items,
            page=page,
            total_pages=total_pages,
        )

    @app.get("/assets/site.css")
    @app.get("/labs/<profile>/assets/site.css")
    def stylesheet(profile=None):
        return Response(render_template("site.css.j2"), mimetype="text/css")

    @app.get("/labs/")
    def labs():
        return render_template("labs.html")

    @app.get("/live/")
    def live():
        return render_template("live.html", categories=[
            {"slug": c["slug"], "name": c["name"]}
            for section in catalogue.sections for c in section["categories"]
        ])

    @app.get("/assets/product-cards.js")
    def product_cards_script():
        return send_from_directory(Path(__file__).parent / "assets", "product-cards.js")

    @app.get("/assets/live.js")
    def live_script():
        return send_from_directory(Path(__file__).parent / "assets", "live.js")

    @app.get("/assets/products/<slug>.svg")
    def product_image(slug):
        item = catalogue.by_slug.get(slug)
        if item is None:
            abort(404)
        return Response(str(svg_for(item)).replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1),
                        mimetype="image/svg+xml")

    @app.get("/api/products")
    def products_api():
        try:
            page = int(request.args.get("page", "1"))
            size = int(request.args.get("page_size", "25"))
            if page < 1 or not 1 <= size <= 100:
                raise ValueError
        except ValueError:
            return jsonify(error="invalid_pagination", reason="page must be positive; page_size must be 1–100"), 400
        category = request.args.get("category", "")
        if category and not any(category == c["slug"] for section in catalogue.sections for c in section["categories"]):
            return jsonify(error="unknown_category"), 400
        query = request.args.get("q", "").strip().casefold()
        items = [p for p in catalogue.products
                 if (not category or p["category"] == category)
                 and (not query or query in p["name"].casefold())]
        total = len(items)
        start = (page - 1) * size
        products = [product_record(p) for p in items[start:start + size]]
        next_url = (url_for("products_api", page=page + 1, page_size=size,
                            category=category, q=request.args.get("q", ""))
                    if start + size < total else None)
        response = jsonify(products=products, page=page, page_size=size,
                           total=total, next=next_url)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/assets/fonts/<path:filename>")
    def font(filename):
        return send_from_directory(FONTS, filename, max_age=86400)

    @app.get("/api/selectors")
    def read_selectors():
        return _state(store)

    @app.route("/api/selectors", methods=["PATCH", "POST"])
    @require_key
    def patch_selectors():
        store.patch(request.get_json(force=True, silent=False))
        return _state(store)

    @app.post("/api/selectors/reset")
    @require_key
    def reset_selectors():
        store.reset()
        return _state(store)

    app.register_blueprint(admin_blueprint)
    app.register_blueprint(embedded_blueprint)
    _register_errors(app)
    return app


def _state(store):
    config, version = store.capture()
    defaults = store.defaults()
    return jsonify(version=version, config=config, defaults=defaults, changed={
        key: {"from": defaults[key], "to": value}
        for key, value in config.items() if value != defaults[key]
    })


def _register_errors(app):
    @app.errorhandler(ValidationError)
    def _invalid(error):
        return jsonify(error="invalid_value", key=error.key, reason=error.reason), 400

    @app.errorhandler(UnknownKeys)
    def _unknown(error):
        return jsonify(error="unknown_key", keys=error.keys), 400

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(500)
    def _http_error(error):
        code = getattr(error, "code", 500)
        if request.path.startswith("/api/"):
            return jsonify(error=error.name.lower().replace(" ", "_"), status=code), code
        return render_template("error.html", code=code, message=error.name), code
