import json
from html.parser import HTMLParser

import pytest

from shop.app import create_app
from shop.catalogue import Catalogue, load_catalogue, product_record


class EmbeddedHTML(HTMLParser):
    """Extract initial state from raw HTML without executing JavaScript."""

    def __init__(self, html):
        super().__init__()
        self.in_state = False
        self.state_text = []
        self.product_tags = []
        self.feed(html)
        self.props = json.loads("".join(self.state_text))["props"]["pageProps"]

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("id") == "__SHOP_DATA__":
            assert attributes.get("type") == "application/json"
            self.in_state = True
        if "product-card" in attributes.get("class", "").split():
            self.product_tags.append(tag)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_state = False

    def handle_data(self, data):
        if self.in_state:
            self.state_text.append(data)


@pytest.fixture
def client():
    return create_app(api_key="test-key").test_client()


def test_raw_html_contains_data_but_no_rendered_cards(client):
    response = client.get("/embedded/")
    assert response.status_code == 200
    html = EmbeddedHTML(response.text)
    assert html.product_tags == []
    assert len(html.props["products"]) == 25
    assert html.props["products"][0] == product_record(load_catalogue().products[0], prefix="/embedded/product/")
    assert "/assets/embedded.js" in response.text
    assert "/labs/classic/assets/site.css" in response.text


def test_all_products_extractable_from_html_with_explicit_end(client):
    url, products, visited = "/embedded/", [], set()
    while url:
        assert url not in visited
        visited.add(url)
        response = client.get(url)
        assert response.status_code == 200
        props = EmbeddedHTML(response.text).props
        assert props["pagination"]["page"] == len(visited)
        products.extend(props["products"])
        url = props["pagination"]["next"]
        assert len(visited) <= 40
    expected = load_catalogue().products
    assert len(visited) == 40
    assert len(products) == len({p["sku"] for p in products}) == 1000
    assert products == [product_record(p, prefix="/embedded/product/") for p in expected]


def test_section_category_and_detail_stay_in_embedded_shop(client):
    section = EmbeddedHTML(client.get("/embedded/coffee/").text).props
    assert section["pagination"]["total"] == 450
    beans = EmbeddedHTML(client.get("/embedded/coffee/beans/?page=2").text).props
    assert beans["pagination"]["total"] == 300
    assert beans["pagination"]["previous"] == "/embedded/coffee/beans/?page=1"
    assert beans["pagination"]["next"] == "/embedded/coffee/beans/?page=3"
    assert all(p["category"] == "beans" for p in beans["products"])
    for section in load_catalogue().sections:
        for category in section["categories"]:
            original = load_catalogue().in_category(section["slug"], category["slug"])[0]
            response = client.get(f"/embedded/product/{original['slug']}")
            assert response.status_code == 200
            props = EmbeddedHTML(response.text).props
            assert props["kind"] == "product"
            assert props["product"]["description"] == original["description"]
            assert props["product"]["specs"] == original["specs"]
            assert props["category"]["url"] == f"/embedded/{section['slug']}/{category['slug']}/"
    assert 'href="/embedded/coffee/"' in client.get("/embedded/").text


@pytest.mark.parametrize("path, status", [
    ("/embedded/?page=0", 400), ("/embedded/?page=no", 400),
    ("/embedded/?page=41", 404), ("/embedded/missing/", 404),
    ("/embedded/coffee/missing/", 404), ("/embedded/product/missing", 404),
])
def test_invalid_embedded_requests(client, path, status):
    assert client.get(path).status_code == status


def test_embedded_json_escapes_script_delimiters_without_corrupting_values():
    product = dict(load_catalogue().products[0])
    product["name"] = '</script><script>window.injected = true</script> & "Coffee"'
    product["description"] = "<img src=x onerror=alert(1)>"
    client = create_app(catalogue=Catalogue([product]), api_key="test").test_client()
    response = client.get("/embedded/")
    assert product["name"] not in response.text
    assert EmbeddedHTML(response.text).props["products"][0]["name"] == product["name"]
    detail = client.get(f"/embedded/product/{product['slug']}")
    assert EmbeddedHTML(detail.text).props["product"]["description"] == product["description"]


def test_embedded_shop_follows_live_selector_changes(client):
    client.patch("/api/selectors", json={"title_class": "renamed", "grid_class": "renamed-grid"},
                 headers={"X-API-Key": "test-key"})
    response = client.get("/embedded/")
    assert "/labs/classic/assets/site.css?v=1" in response.text
    assert '"title_class": "renamed"' in response.text
    assert len(EmbeddedHTML(response.text).props["products"]) == 25
    assert 'href="/embedded/"' in client.get("/labs/").text
