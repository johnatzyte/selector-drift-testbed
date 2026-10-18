"""Optional browser check. Start the shop first; requires Playwright + Chromium."""

import argparse
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
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{args.base}/live/")
        expect(page.locator("#live-products article")).to_have_count(25)
        expect(page.locator("#live-status")).to_have_text("Showing 25 of 1000 products.")
        page.get_by_role("button", name="Load more").click()
        expect(page.locator("#live-products article")).to_have_count(50)
        page.get_by_label("Category").select_option("beans")
        page.get_by_role("button", name="Find products").click()
        expect(page.locator("#live-status")).to_have_text("Showing 25 of 300 products.")
        # A deliberately failed request should offer a retry without duplicating cards.
        page.route("**/api/products?**", lambda route: route.abort(), times=1)
        page.get_by_role("button", name="Load more").click()
        expect(page.locator("#live-status")).to_contain_text("could not be loaded")
        page.get_by_role("button", name="Try again").click()
        expect(page.locator("#live-products article")).to_have_count(50)
        expect(page.locator("#live-status")).to_have_text("Showing 50 of 300 products.")
        page.get_by_label("Search products").fill("no-such-product")
        page.get_by_role("button", name="Find products").click()
        expect(page.locator("#live-status")).to_contain_text("No products found")
        expect(page.locator("#live-products article")).to_have_count(0)
        expect(page.locator("#load-more")).to_be_hidden()
        page.get_by_label("Search products").fill("Ethiopia")
        page.get_by_role("button", name="Find products").click()
        expect(page.locator("#live-products article")).to_have_count(25)
        expect(page.locator("#live-products article").first).to_contain_text("Ethiopia")
        page.locator(".product-image").first.wait_for()
        page.wait_for_function("document.querySelector('.product-image').naturalWidth > 0")
        page.screenshot(path=str(artifacts / "live-shop-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(artifacts / "live-shop-mobile.png"), full_page=True)
        page.goto(f"{args.base}/labs/")
        expect(page.get_by_role("heading", name="Scraping labs", exact=True)).to_be_visible()
        page.get_by_role("link", name="Investigate the changes").click()
        expect(page.locator(".item-name")).to_have_count(12)
        assert "/labs/drift/" in page.url
        page.get_by_role("link", name="Browse the beans").click()
        expect(page.locator(".item-name")).to_have_count(25)
        page.locator("a.forward").click()
        expect(page.locator(".pager-state")).to_have_text("Page 2 of 12")
        page.locator("a.product-link").first.click()
        assert "/labs/drift/product/" in page.url
        expect(page.locator(".detail .item-name")).to_have_count(1)
        assert not errors, errors
        browser.close()
    print("Browser smoke passed: loading, pagination, filters, retry, images, mobile layout, lab navigation.")


if __name__ == "__main__":
    main()
