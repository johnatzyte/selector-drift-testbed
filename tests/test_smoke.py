import re
from html.parser import HTMLParser

import pytest

from shop.app import create_app
from shop.catalogue import load_catalogue
from shop.config import DEFAULTS

EXPECTED_COUNTS = {
    "beans": 300, "pods-capsules": 80, "decaf": 70,
    "espresso-machines": 120, "grinders": 100, "brewers": 90,
    "tampers-scales": 70, "filters": 60, "cleaning": 60, "kettles": 50,
}
EXPECTED_TOTAL = sum(EXPECTED_COUNTS.values())
LISTING = "/coffee/beans/"


API_KEY = "test-key-not-a-secret"


class Client:
    """Test client that signs mutating calls, so the tests read like the demo does."""

    def __init__(self, flask_client):
        self._c = flask_client

    def get(self, *args, **kwargs):
        return self._c.get(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._c.delete(*args, **kwargs)

    def patch(self, *args, **kwargs):
        return self._c.patch(*args, headers={"X-API-Key": API_KEY}, **kwargs)

    def post(self, *args, **kwargs):
        return self._c.post(*args, headers={"X-API-Key": API_KEY}, **kwargs)


@pytest.fixture
def raw_client():
    return create_app(api_key=API_KEY).test_client()


@pytest.fixture
def client(raw_client):
    return Client(raw_client)


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue()


def html_classes(markup):
    found = set()

    class Collector(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for name, value in attrs:
                if name == "class" and value:
                    found.update(value.split())

    Collector().feed(markup)
    return found


def css_classes(sheet):
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", re.sub(r"/\*.*?\*/", "", sheet, flags=re.S)))


def test_catalogue_shape(catalogue):
    assert len(catalogue.products) == EXPECTED_TOTAL
    assert len({p["slug"] for p in catalogue.products}) == EXPECTED_TOTAL
    assert len({p["sku"] for p in catalogue.products}) == EXPECTED_TOTAL
    counts = {}
    for product in catalogue.products:
        counts[product["category"]] = counts.get(product["category"], 0) + 1
    assert counts == EXPECTED_COUNTS


def test_every_product_reachable_by_crawling(client, catalogue):
    seen = set()
    for section in catalogue.sections:
        assert client.get(f"/{section['slug']}/").status_code == 200
        for category in section["categories"]:
            page, pages = 1, 1
            while page <= pages:
                response = client.get(f"/{section['slug']}/{category['slug']}/?page={page}")
                assert response.status_code == 200
                body = response.get_data(as_text=True)
                pages = int(re.search(r"page \d+ of (\d+)", body).group(1))
                seen.update(re.findall(r'href="/product/([a-z0-9-]+)"', body))
                page += 1
    assert set(catalogue.by_slug) <= seen


def test_default_listing_and_detail(client, catalogue):
    body = client.get(LISTING).get_data(as_text=True)
    assert body.count('class="product-card"') == 25
    assert body.count('class="product-title"') == 25
    slug = next(iter(catalogue.by_slug))
    assert client.get(f"/product/{slug}").status_code == 200
    assert client.get("/product/not-a-real-product").status_code == 404


def test_rename_moves_markup_and_stylesheet_together(client):
    client.patch("/api/selectors", json={"title_class": "item-name"})
    body = client.get(LISTING).get_data(as_text=True)
    sheet = client.get("/assets/site.css").get_data(as_text=True)

    assert 'class="item-name"' in body and 'class="product-title"' not in body
    assert ".item-name" in sheet and ".product-title" not in sheet


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"title_class": "item-name", "price_class": "cost", "card_class": "listing-item"},
        {"title_tag": "span", "card_tag": "li"},
        {"extra_wrapper": True},
        {"price_in_attribute": True},
        {"price_split": True},
        {"field_order": "price,stock,title,rating"},
        {"grid_class": "results", "next_page_class": "forward", "breadcrumb_class": "trail"},
        {"spec_class": "attribute", "spec_label_class": "attr-key", "spec_value_class": "attr-val"},
    ],
)
def test_every_rendered_class_is_styled(client, catalogue, patch):
    """The guard that keeps the page looking identical: no class reaches the browser
    without a matching rule in the stylesheet."""
    if patch:
        assert client.patch("/api/selectors", json=patch).status_code == 200
    styled = css_classes(client.get("/assets/site.css").get_data(as_text=True))
    slug = next(iter(catalogue.by_slug))
    for path in ("/", LISTING, f"/product/{slug}"):
        rendered = html_classes(client.get(path).get_data(as_text=True))
        assert rendered <= styled, f"unstyled on {path}: {sorted(rendered - styled)}"


@pytest.mark.parametrize("flag", ["extra_wrapper", "price_in_attribute", "price_split", "id_to_class"])
def test_structural_flags_keep_prices_and_valid_html(client, flag):
    client.patch("/api/selectors", json={flag: True})
    body = client.get(LISTING).get_data(as_text=True)
    HTMLParser().feed(body)
    # price_split wraps the currency and the amount in separate spans, so compare
    # against the text with tags removed plus whatever moved into data-price.
    visible = re.sub(r"<[^>]+>", "", body) + " ".join(re.findall(r'data-price="([^"]+)"', body))
    shown = len(re.findall(r"&pound;\s*\d+\.\d{2}", visible))
    assert shown == 25, f"{flag} lost prices: {shown}"


def test_price_in_attribute_leaves_the_text_node(client):
    client.patch("/api/selectors", json={"price_in_attribute": True})
    body = client.get(LISTING).get_data(as_text=True)
    sheet = client.get("/assets/site.css").get_data(as_text=True)
    assert body.count("data-price=") == 25
    assert re.search(r'class="price"[^>]*>\s*</span>', body)
    assert "content: attr(data-price)" in sheet


def test_specs_render_for_each_category(client, catalogue):
    for category in EXPECTED_COUNTS:
        product = next(p for p in catalogue.products if p["category"] == category)
        body = client.get(f"/product/{product['slug']}").get_data(as_text=True)
        for label in product["specs"]:
            assert label in body, f"{category} missing spec {label}"


def test_sku_attribute_renames(client, catalogue):
    client.patch("/api/selectors", json={"sku_attribute": "data-item-ref"})
    body = client.get(LISTING).get_data(as_text=True)
    assert body.count("data-item-ref=") == 25 and "data-sku=" not in body


def test_id_to_class_moves_the_description(client, catalogue):
    slug = next(iter(catalogue.by_slug))
    assert 'id="product-description"' in client.get(f"/product/{slug}").get_data(as_text=True)
    client.patch("/api/selectors", json={"id_to_class": True})
    body = client.get(f"/product/{slug}").get_data(as_text=True)
    assert 'id="product-description"' not in body and 'class="product-description"' in body


def test_not_indexable(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /" in robots.get_data(as_text=True)
    assert client.get(LISTING).headers["X-Robots-Tag"] == "noindex, nofollow"


def test_no_store_headers_and_version_bump(client):
    assert "no-store" in client.get(LISTING).headers["Cache-Control"]
    assert "no-store" in client.get("/assets/site.css").headers["Cache-Control"]
    before = client.get("/api/selectors").get_json()["version"]
    client.patch("/api/selectors", json={"price_class": "cost"})
    after = client.get("/api/selectors").get_json()["version"]
    assert after > before
    assert f"/assets/site.css?v={after}" in client.get(LISTING).get_data(as_text=True)


@pytest.mark.parametrize(
    "patch",
    [
        {"title_class": 'x"><script>'},
        {"title_class": "Bad-Caps"},
        {"title_class": "a{color:red}"},
        {"card_tag": "script"},
        {"extra_wrapper": "yes"},
        {"sku_attribute": "onclick"},
        {"field_order": "title,price"},
    ],
)
def test_invalid_values_rejected_without_changing_config(client, patch):
    before = client.get("/api/selectors").get_json()["config"]
    response = client.patch("/api/selectors", json=patch)
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_value"
    assert client.get("/api/selectors").get_json()["config"] == before


def test_unknown_key_is_loud(client):
    response = client.patch("/api/selectors", json={"produkt_title": "x"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "unknown_key", "keys": ["produkt_title"]}


def test_api_errors_are_json_not_html(client):
    response = client.get("/api/nope", follow_redirects=True)
    assert response.status_code == 404
    assert response.mimetype == "application/json"
    assert client.delete("/api/selectors").mimetype == "application/json"


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-API-Key": ""}, {"X-API-Key": "wrong"}, {"X-API-Key": API_KEY + "x"}],
)
def test_mutations_require_the_api_key(raw_client, headers):
    for call, path in ((raw_client.patch, "/api/selectors"), (raw_client.post, "/api/selectors/reset")):
        response = call(path, json={"title_class": "item-name"}, headers=headers)
        assert response.status_code == 401
        assert response.get_json()["error"] == "unauthorized"
    assert 'class="product-title"' in raw_client.get(LISTING).get_data(as_text=True)


def test_reads_stay_public(raw_client):
    """The class names are in the page source anyway, so GET needs no key."""
    assert raw_client.get("/api/selectors").status_code == 200
    assert raw_client.get(LISTING).status_code == 200
    assert raw_client.get("/assets/site.css").status_code == 200


def test_correct_key_is_accepted(raw_client):
    response = raw_client.patch("/api/selectors", json={"title_class": "item-name"}, headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    assert 'class="item-name"' in raw_client.get(LISTING).get_data(as_text=True)


def test_generated_key_when_env_unset(monkeypatch):
    monkeypatch.delenv("SHOP_API_KEY", raising=False)
    app = create_app()
    assert app.extensions["api_key_configured"] is False
    assert len(app.extensions["api_key"]) >= 24
    # Generated, not absent: the API is never open.
    assert app.test_client().patch("/api/selectors", json={"title_class": "x"}).status_code == 401


def test_reset_restores_defaults(client):
    client.patch("/api/selectors", json={"title_class": "item-name", "card_tag": "li"})
    assert client.get("/api/selectors").get_json()["changed"]
    state = client.post("/api/selectors/reset").get_json()
    assert state["changed"] == {} and state["config"] == DEFAULTS
