"""Exercise the admin UI against a local/test shop; resets live selectors afterwards."""

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8811")
    parser.add_argument("--key-file", default=".env")
    args = parser.parse_args()
    settings = dict(line.split("=", 1) for line in Path(args.key_file).read_text().splitlines()
                    if line and not line.startswith("#") and "=" in line)
    key = settings["SHOP_API_KEY"]
    artifacts = Path(__file__).resolve().parents[1] / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(f"{args.base}/admin/")
            expect(page.get_by_role("button", name="Unlock controls")).to_be_visible()
            page.get_by_label("Admin key").fill("incorrect")
            page.get_by_role("button", name="Unlock controls").click()
            expect(page.locator("#admin-status")).to_contain_text("set the X-API-Key")
            page.get_by_label("Admin key").fill(key)
            page.get_by_role("button", name="Unlock controls").click()
            expect(page.locator("#admin-controls")).to_be_visible()
            page.get_by_role("button", name="Combined changes", exact=True).click()
            expect(page.locator("#admin-diff")).to_contain_text("title_class")
            expect(page.frame_locator("#shop-preview").locator(".item-name")).to_have_count(25)
            page.reload()
            expect(page.locator("#admin-controls")).to_be_visible()
            page.get_by_role("button", name="Rename titles", exact=True).click()
            expect(page.locator("#admin-diff")).not_to_contain_text("price_split")
            page.get_by_text("Advanced: edit individual selectors", exact=True).click()
            page.get_by_label("Title class", exact=True).fill("recording-title")
            page.get_by_role("button", name="Apply changes", exact=True).click()
            expect(page.frame_locator("#shop-preview").locator(".recording-title")).to_have_count(25)
            page.get_by_label("Field order", exact=True).fill("title,price")
            page.get_by_role("button", name="Apply changes", exact=True).click()
            expect(page.locator("#admin-status")).to_contain_text("field_order")
            page.get_by_label("Field order", exact=True).fill("title,price,rating,stock")
            page.get_by_role("button", name="Apply changes", exact=True).click()
            expect(page.locator("#admin-status")).to_contain_text("Shop updated")
            page.get_by_text("Advanced: edit individual selectors", exact=True).click()
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(artifacts / "admin-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(artifacts / "admin-mobile.png"), full_page=True)
            page.get_by_role("button", name="Reset defaults", exact=True).click()
            expect(page.locator("#admin-diff")).to_have_text("Default markup. No changes applied.")
            expect(page.frame_locator("#shop-preview").locator(".product-title")).to_have_count(25)
            page.get_by_role("button", name="Lock controls", exact=True).click()
            expect(page.get_by_role("button", name="Unlock controls")).to_be_visible()
            page.reload()
            expect(page.get_by_role("button", name="Unlock controls")).to_be_visible()
            assert not errors, errors
        finally:
            # API-key cleanup also works if the browser test failed or logged out.
            page.request.post(f"{args.base}/api/selectors/reset", headers={"X-API-Key": key})
            browser.close()
    print("Admin browser smoke passed: login, session, presets, edits, validation, preview, mobile, reset, logout.")


if __name__ == "__main__":
    main()
