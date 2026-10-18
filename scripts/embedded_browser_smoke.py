"""Verify embedded-state rendering without product API requests. Requires Playwright."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8811")
    args = parser.parse_args()
    artifacts = Path(__file__).resolve().parents[1] / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors, data_requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: data_requests.append(request.url)
                if request.resource_type in {"fetch", "xhr"} else None)
        page.goto(f"{args.base}/labs/")
        page.get_by_role("link", name="Find the embedded data", exact=True).click()
        expect(page.locator("#embedded-content .product-card")).to_have_count(25)
        props = json.loads(page.locator("#__SHOP_DATA__").text_content())["props"]["pageProps"]
        first = props["products"][0]
        expect(page.locator(".product-card").first).to_contain_text(first["name"])
        expect(page.locator(".product-card .price").first).to_have_text(f"£{first['price_minor'] / 100:,.2f}")
        expect(page.locator(".pager-state")).to_have_text("Page 1 of 40")
        page.locator("a.next").click()
        expect(page.locator(".pager-state")).to_have_text("Page 2 of 40")
        page.locator("a.prev").click()
        expect(page.locator(".pager-state")).to_have_text("Page 1 of 40")
        page.get_by_role("navigation", name="Product categories").get_by_role("link", name="Beans 300", exact=True).click()
        expect(page.locator(".pager-state")).to_have_text("Page 1 of 12")
        assert "/embedded/coffee/beans/" in page.url
        page.wait_for_function("document.querySelector('.product-image').naturalWidth > 0")
        page.screenshot(path=str(artifacts / "embedded-shop-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(artifacts / "embedded-shop-mobile.png"), full_page=True)
        page.locator("a.product-link").first.click()
        expect(page.locator(".detail .product-title")).to_have_text(first["name"])
        expect(page.locator(".product-description")).not_to_be_empty()
        expect(page.locator(".spec-list .spec")).to_have_count(5)
        assert "/embedded/product/" in page.url
        page.get_by_role("link", name="More Beans", exact=True).click()
        expect(page.locator(".pager-state")).to_have_text("Page 1 of 12")
        page.goto(f"{args.base}/embedded/?page=40")
        expect(page.locator(".product-card")).to_have_count(25)
        expect(page.locator("a.next")).to_have_count(0)
        assert not data_requests, data_requests
        assert not errors, errors
        no_js = browser.new_context(java_script_enabled=False)
        raw = no_js.new_page()
        raw.goto(f"{args.base}/embedded/")
        expect(raw.locator(".product-card")).to_have_count(0)
        state = json.loads(raw.locator("#__SHOP_DATA__").text_content())
        assert len(state["props"]["pageProps"]["products"]) == 25
        expect(raw.get_by_role("link", name="classic shop", exact=True)).to_be_visible()
        browser.close()
    print("Embedded browser smoke passed: rendering, pagination, categories, details, mobile, no data fetches, and no-JS state.")


if __name__ == "__main__":
    main()
