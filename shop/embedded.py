"""A client-rendered shop whose initial data is embedded in its HTML."""

from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, request, send_from_directory, url_for

from .catalogue import PAGE_SIZE, product_record

embedded_blueprint = Blueprint("embedded", __name__)


def render_state(props, categories=()):
    return render_template("embedded.html", heading=props["title"],
                           initial_state={"schemaVersion": 1, "props": {"pageProps": props}},
                           categories=categories)


@embedded_blueprint.get("/assets/embedded.js")
def script():
    return send_from_directory(Path(__file__).parent / "assets", "embedded.js")


@embedded_blueprint.get("/embedded/")
@embedded_blueprint.get("/embedded/<section_slug>/")
@embedded_blueprint.get("/embedded/<section_slug>/<category_slug>/")
def listing(section_slug=None, category_slug=None):
    catalogue = current_app.extensions["catalogue"]
    title = "Embedded shop"
    items = catalogue.products
    sections = catalogue.sections
    if section_slug:
        section = catalogue.section(section_slug)
        if section is None:
            abort(404)
        title = section["name"]
        sections = [section]
        items = [p for p in items if p["section"] == section_slug]
    if category_slug:
        category = catalogue.category(section_slug, category_slug)
        if category is None:
            abort(404)
        title = category["name"]
        items = catalogue.in_category(section_slug, category_slug)
    try:
        page = int(request.args.get("page", "1"))
        if page < 1:
            raise ValueError
    except ValueError:
        abort(400)
    pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > pages:
        abort(404)

    def page_url(number):
        return url_for("embedded.listing", section_slug=section_slug,
                       category_slug=category_slug, page=number)

    start = (page - 1) * PAGE_SIZE
    return render_state({
        "kind": "listing", "title": title,
        "products": [product_record(p, prefix="/embedded/product/") for p in items[start:start + PAGE_SIZE]],
        "pagination": {"page": page, "pages": pages, "total": len(items),
                       "next": page_url(page + 1) if page < pages else None,
                       "previous": page_url(page - 1) if page > 1 else None},
    }, categories=[{"name": c["name"], "count": c["count"],
                    "url": url_for("embedded.listing", section_slug=s["slug"], category_slug=c["slug"])}
                   for s in sections for c in s["categories"]])


@embedded_blueprint.get("/embedded/product/<slug>")
def product(slug):
    catalogue = current_app.extensions["catalogue"]
    item = catalogue.by_slug.get(slug)
    if item is None:
        abort(404)
    return render_state({
        "kind": "product", "title": "Product details",
        "product": {**product_record(item, prefix="/embedded/product/"),
                    "description": item["description"], "specs": item["specs"],
                    "reviews": item["reviews"]},
        "category": {"name": item["category_name"],
                     "url": url_for("embedded.listing", section_slug=item["section"], category_slug=item["category"])},
    })
