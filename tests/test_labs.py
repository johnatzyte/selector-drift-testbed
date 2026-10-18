from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from html.parser import HTMLParser
from threading import Barrier, Event

import pytest

import shop.app as app_module
from shop.app import create_app
from shop.catalogue import load_catalogue


@pytest.fixture
def app():
    return create_app(api_key="test-key")


def test_profiles_and_live_shop_ignore_legacy_changes(app):
    client = app.test_client()
    client.patch("/api/selectors", json={"title_class": "legacy-title", "grid_class": "legacy-grid"},
                 headers={"X-API-Key": "test-key"})
    classic = client.get("/labs/classic/coffee/beans/").text
    drift = client.get("/labs/drift/coffee/beans/").text
    assert 'class="legacy-title"' in client.get("/coffee/beans/").text
    assert 'class="product-title"' in classic
    assert 'class="item-name"' in drift
    assert 'class="currency"' in drift
    assert 'class="forward"' in drift
    for profile, body in (("classic", classic), ("drift", drift)):
        assert f'href="/labs/{profile}/product/' in body
        assert f'href="/labs/{profile}/coffee/beans/?page=2"' in body
        css_path = f"/labs/{profile}/assets/site.css?v=1"
        assert css_path in body
        css = client.get(css_path).text
        assert ".legacy-title" not in css
        assert (".item-name" in css) == (profile == "drift")
    live = client.get("/live/").text
    assert "/labs/classic/assets/site.css?v=1" in live
    assert 'id="live-products" class="product-grid"' in live
    assert "legacy-grid" not in live


def test_profile_navigation_stays_inside_profile(app):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.links.extend(value for key, value in attrs if key == "href")

    client = app.test_client()
    slug = load_catalogue().products[0]["slug"]
    for suffix in ("", "coffee/", "coffee/beans/", f"product/{slug}"):
        response = client.get(f"/labs/drift/{suffix}")
        assert response.status_code == 200
        parser = Links()
        parser.feed(response.text)
        assert all(link.startswith("/labs/drift/") or link in {"/labs/", "/live/", "/embedded/", "/admin/"}
                   for link in parser.links)
    assert client.get("/labs/nonexistent/").status_code == 404
    assert client.get("/labs/drift/product/missing").status_code == 404


def test_concurrent_profiles_use_separate_request_contexts(app, monkeypatch):
    original = app_module.render_template
    barrier = Barrier(2)

    def render(name, **context):
        if name == "listing.html":
            barrier.wait(timeout=5)
        return original(name, **context)

    monkeypatch.setattr(app_module, "render_template", render)

    def fetch(profile):
        with app.test_client() as client:
            return client.get(f"/labs/{profile}/coffee/beans/").text

    with ThreadPoolExecutor(max_workers=2) as pool:
        classic, drift = list(pool.map(fetch, ("classic", "drift")))
    assert 'class="product-title"' in classic and 'class="item-name"' not in classic
    assert 'class="item-name"' in drift and 'class="product-title"' not in drift


def test_legacy_request_snapshot_and_css_survive_mid_render_mutation(app, monkeypatch):
    original = app_module.render_template
    ready, changed = Event(), Event()

    def render(name, **context):
        if name == "listing.html":
            ready.set()
            assert changed.wait(timeout=5)
        return original(name, **context)

    monkeypatch.setattr(app_module, "render_template", render)

    def fetch():
        with app.test_client() as client:
            return client.get("/coffee/beans/").text

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(fetch)
        try:
            assert ready.wait(timeout=5)
            with app.test_client() as client:
                response = client.patch("/api/selectors", json={"title_class": "new-title"},
                                        headers={"X-API-Key": "test-key"})
                assert response.status_code == 200
        finally:
            changed.set()
        body = pending.result(timeout=5)
    assert 'class="product-title"' in body and 'class="new-title"' not in body
    assert "/assets/site.css?v=0" in body
    client = app.test_client()
    assert ".new-title" not in client.get("/assets/site.css?v=0").text
    assert ".new-title" in client.get("/assets/site.css?v=1").text
    assert client.get("/assets/site.css?v=999").status_code == 404


def test_api_complete_catalogue_and_explicit_end(app):
    client = app.test_client()
    url, records = "/api/products?page_size=100", []
    pages = 0
    while url:
        response = client.get(url)
        assert response.status_code == 200
        data = response.get_json()
        records.extend(data["products"])
        url = data["next"]
        pages += 1
        assert pages <= 10
    expected = load_catalogue().products
    assert pages == 10
    assert len(records) == len({p["sku"] for p in records}) == 1000
    assert [p["sku"] for p in records] == [p["sku"] for p in expected]
    for actual, product in zip(records, expected):
        assert actual["price_minor"] == int(Decimal(str(product["price"])) * 100)
        assert actual["name"] == product["name"]
        assert actual["currency"] == product["currency"]
    assert client.get(records[0]["url"]).status_code == 200
    image = client.get(records[0]["image_url"])
    assert image.status_code == 200 and image.mimetype == "image/svg+xml"
    assert 'xmlns="http://www.w3.org/2000/svg"' in image.text
    beyond = client.get("/api/products?page=1000").get_json()
    assert beyond["products"] == [] and beyond["next"] is None


def test_filters_persist_across_pages_and_empty_results(app):
    client = app.test_client()
    url = "/api/products?category=beans&q=ETHIOPIA&page_size=3"
    records = []
    while url:
        data = client.get(url).get_json()
        records.extend(data["products"])
        url = data["next"]
        if url:
            assert "category=beans" in url and "q=ETHIOPIA" in url
    expected = [p["sku"] for p in load_catalogue().products
                if p["category"] == "beans" and "ethiopia" in p["name"].casefold()]
    assert expected and [p["sku"] for p in records] == expected
    empty = client.get("/api/products?q=no-such-product").get_json()
    assert empty["total"] == 0 and empty["products"] == [] and empty["next"] is None


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=no", "page_size=0", "page_size=101", "page_size=x", "category=missing"])
def test_api_rejects_invalid_queries(app, query):
    response = app.test_client().get(f"/api/products?{query}")
    assert response.status_code == 400 and response.is_json


def test_live_html_is_shell_and_lab_directory_links_work(app):
    client = app.test_client()
    live = client.get("/live/").text
    assert load_catalogue().products[0]["name"] not in live
    assert "/assets/live.js" in live and "<noscript>" in live
    assert client.get("/assets/live.js").status_code == 200
    directory = client.get("/labs/")
    assert directory.status_code == 200
    for target in ("/labs/classic/", "/labs/drift/", "/live/"):
        assert f'href="{target}"' in directory.text
        assert client.get(target).status_code == 200
