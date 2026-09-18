"""Reads the committed catalogue and indexes it for the routes."""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "catalogue.json"
PAGE_SIZE = 25


class Catalogue:
    def __init__(self, products):
        self.products = products
        self.by_slug = {p["slug"]: p for p in products}
        self.sections = []
        self._categories = {}
        for product in products:
            section = self._section(product)
            category = self._category(section, product)
            category["count"] += 1
            self._categories.setdefault((product["section"], product["category"]), []).append(product)

    def _section(self, product):
        for section in self.sections:
            if section["slug"] == product["section"]:
                return section
        section = {"slug": product["section"], "name": product["section_name"], "categories": [], "count": 0}
        self.sections.append(section)
        return section

    def _category(self, section, product):
        section["count"] += 1
        for category in section["categories"]:
            if category["slug"] == product["category"]:
                return category
        category = {"slug": product["category"], "name": product["category_name"], "count": 0, "section": section["slug"]}
        section["categories"].append(category)
        return category

    def section(self, slug):
        return next((s for s in self.sections if s["slug"] == slug), None)

    def category(self, section_slug, category_slug):
        section = self.section(section_slug)
        if not section:
            return None
        return next((c for c in section["categories"] if c["slug"] == category_slug), None)

    def in_category(self, section_slug, category_slug):
        return self._categories.get((section_slug, category_slug), [])


def paginate(items, page, size=PAGE_SIZE):
    """Return (page_items, page_number, total_pages). Page numbers are 1-based and clamped."""
    total_pages = max(1, -(-len(items) // size))
    page = max(1, min(page, total_pages))
    start = (page - 1) * size
    return items[start : start + size], page, total_pages


def load_catalogue(path=DATA):
    return Catalogue(json.loads(Path(path).read_text()))
