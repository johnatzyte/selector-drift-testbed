from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory
from markupsafe import Markup

from .auth import require_key, resolve_key
from .catalogue import load_catalogue, paginate
from .config import SelectorStore, UnknownKeys, ValidationError
from .images import svg_for

SITE_NAME = "Scrape Roasters"
FONTS = Path(__file__).resolve().parent / "assets" / "fonts"


def register_jinja_globals(app, store):
    """Expose the selector config to templates.

    Nothing in a template or the stylesheet ever writes a class name literally — both
    go through these helpers against the same dict, so they cannot drift apart.
    """

    def sel(key):
        return app.config["SELECTORS"][key]

    # Values are allowlisted to ^[a-z][a-z0-9-]{0,39}$ in config.py, so nothing that
    # reaches Markup here can carry a quote, angle bracket, brace or semicolon.
    app.jinja_env.globals.update(
        sel=sel,
        cls=lambda key: Markup(f'class="{sel(key)}"'),
        css=lambda key: Markup(f".{sel(key)}"),
        tag=lambda key: Markup(sel(key)),
        svg_for=svg_for,
        site_name=SITE_NAME,
        selector_version=lambda: store.version,
    )


def create_app(catalogue=None, store=None, api_key=None):
    app = Flask(__name__)
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
        app.config["SELECTORS"] = store.snapshot()

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
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

    @app.get("/")
    def landing():
        featured = {s["slug"]: catalogue.in_category(s["slug"], s["categories"][0]["slug"])[:4] for s in catalogue.sections}
        return render_template("landing.html", sections=catalogue.sections, featured=featured, total=len(catalogue.products))

    @app.get("/product/<slug>")
    def product(slug):
        item = catalogue.by_slug.get(slug)
        if item is None:
            abort(404)
        section = catalogue.section(item["section"])
        category = catalogue.category(item["section"], item["category"])
        related = [p for p in catalogue.in_category(item["section"], item["category"]) if p["slug"] != slug][:4]
        return render_template("product.html", product=item, section=section, category=category, related=related)

    @app.get("/<section_slug>/")
    def section(section_slug):
        found = catalogue.section(section_slug)
        if found is None:
            abort(404)
        samples = {c["slug"]: catalogue.in_category(section_slug, c["slug"])[:3] for c in found["categories"]}
        return render_template("section.html", section=found, samples=samples)

    @app.get("/<section_slug>/<category_slug>/")
    def listing(section_slug, category_slug):
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
    def stylesheet():
        return Response(render_template("site.css.j2"), mimetype="text/css")

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

    _register_errors(app)
    return app


def _state(store):
    return jsonify(version=store.version, config=store.snapshot(), defaults=store.defaults(), changed=store.diff())


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
