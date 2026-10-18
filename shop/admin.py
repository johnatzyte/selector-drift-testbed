"""Browser controls for the original selector-change demo."""

from pathlib import Path
import secrets

from flask import Blueprint, current_app, jsonify, render_template, request, send_from_directory, session

from .auth import require_key
from .config import DEFAULTS

admin_blueprint = Blueprint("admin", __name__)
PRESETS = {
    "titles": {"title_class": "item-name"},
    "prices": {"price_split": True},
    "pagination": {"next_page_class": "forward"},
    "structure": {"extra_wrapper": True, "card_tag": "section", "field_order": "stock,title,price,rating"},
    "combined": {"title_class": "item-name", "price_split": True, "extra_wrapper": True, "next_page_class": "forward"},
}
OPTIONS = {
    "title_tag": ["h2", "h3", "h4", "div", "span", "p"],
    "card_tag": ["article", "div", "li", "section"],
}


@admin_blueprint.get("/admin/")
def page():
    return render_template("admin.html", fields=DEFAULTS, options=OPTIONS)


@admin_blueprint.get("/assets/admin.js")
def script():
    return send_from_directory(Path(__file__).parent / "assets", "admin.js")


@admin_blueprint.get("/api/admin/session")
def session_state():
    response = jsonify(authenticated=session.get("admin") is True, csrf=session.get("csrf"))
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_blueprint.post("/api/admin/login")
@require_key
def login():
    session.clear()
    session.permanent = True
    session["admin"] = True
    session["csrf"] = secrets.token_urlsafe(32)
    response = jsonify(authenticated=True, csrf=session["csrf"])
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_blueprint.post("/api/admin/logout")
@require_key
def logout():
    session.clear()
    return jsonify(authenticated=False)


@admin_blueprint.post("/api/admin/preset")
@require_key
def preset():
    body = request.get_json(silent=True)
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(name, str) or name not in PRESETS:
        return jsonify(error="unknown_preset"), 400
    store = current_app.extensions["store"]
    store.patch(PRESETS[name], replace=True)
    from .app import _state

    return _state(store)
