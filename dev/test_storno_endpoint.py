"""
Intercepts the storno/cancel API call WITHOUT completing it.
Your appointment is NOT cancelled.

Usage (from dev/ folder):
    uv run python test_storno_endpoint.py
"""

import asyncio
from playwright.async_api import async_playwright

VORGANGSNR = "CA-5250317A"
ZUGANGSCODE = "8638"
MANAGE_URL = f"https://karlsruhe.konsentas.de/form/1/manage/{VORGANGSNR}?code={ZUGANGSCODE}"


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()

        intercepted: list[dict] = []

        async def handle_route(route):
            req = route.request
            if req.method == "POST" and req.resource_type in ("xhr", "fetch"):
                intercepted.append({
                    "url": req.url,
                    "body": req.post_data or "",
                    "headers": {k: v for k, v in req.headers.items()
                                if k.lower() in ("authorization", "content-type")},
                })
                print(f"\n[INTERCEPTED POST] {req.url}")
                print(f"  body: {(req.post_data or '')[:400]}")
                await route.abort()
                return
            await route.continue_()

        print(f"Loading: {MANAGE_URL}")
        await page.goto(MANAGE_URL, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(1_500)

        # Dump all buttons/links on the page to find the storno option
        elements = await page.evaluate("""
            () => Array.from(document.querySelectorAll('button, a, [data-action]')).map(e => ({
                tag: e.tagName,
                text: e.textContent.trim().slice(0, 60),
                dataAction: e.getAttribute('data-action'),
                href: e.getAttribute('href'),
                classes: e.className.slice(0, 80),
            })).filter(e => e.text.length > 0)
        """)
        print("\nAll buttons/links on manage page:")
        for e in elements:
            print(f"  {e}")

        # Try to find and click the storno/cancel button
        for label in ["Stornieren", "Absagen", "Abmelden", "Löschen", "Cancel", "Storno"]:
            btn = page.get_by_role("button", name=label)
            if await btn.count() > 0:
                print(f"\nFound storno button: '{label}' — enabling interception and clicking...")
                await page.route("**/*", handle_route)
                await btn.click()
                await page.wait_for_timeout(2_000)
                await page.unroute("**/*")
                break

        # Also try data-action attribute
        for action in ["signup_init_storno", "storno", "cancel", "signup_storno"]:
            el = page.locator(f'[data-action="{action}"]')
            if await el.count() > 0:
                print(f"\nFound element with data-action='{action}' — enabling interception and clicking...")
                await page.route("**/*", handle_route)
                await el.click()
                await page.wait_for_timeout(2_000)
                await page.unroute("**/*")
                break

        print("\n--- Intercepted calls ---")
        for c in intercepted:
            print(f"\n  URL: {c['url']}")
            print(f"  BODY: {c['body'][:400]}")
            print(f"  HEADERS: {c['headers']}")

        if not intercepted:
            print("  Nothing intercepted — storno button may need a different label.")

        print("\nBrowser stays open for 20s.")
        await page.wait_for_timeout(20_000)
        await browser.close()


asyncio.run(main())
