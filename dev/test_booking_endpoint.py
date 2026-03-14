"""
Intercepts the booking API call WITHOUT actually completing it.
Aborts the final save request so your appointment is NOT changed.

Usage (from dev/ folder):
    uv run playwright install chromium
    uv run python test_booking_endpoint.py
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

        # Intercept all POST requests — abort any that look like a save/confirm
        # so nothing actually gets booked
        save_calls: list[dict] = []

        async def handle_route(route):
            req = route.request
            if req.method == "POST" and req.resource_type in ("xhr", "fetch"):
                url = req.url
                body = req.post_data or ""
                save_calls.append({"url": url, "body": body, "headers": dict(req.headers)})
                print(f"\n[INTERCEPTED POST] {url}")
                print(f"  body: {body[:400]}")
                # Abort the request — nothing gets saved
                await route.abort()
                return
            await route.continue_()

        # Only intercept after we've navigated past the calendar
        # (we'll enable interception just before clicking the time slot confirm button)

        api_calls: list[dict] = []

        async def on_request(req):
            if req.resource_type in ("xhr", "fetch"):
                api_calls.append({"method": req.method, "url": req.url, "body": req.post_data})

        page.on("request", on_request)

        print(f"Loading: {MANAGE_URL}")
        await page.goto(MANAGE_URL, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(1_500)

        # Click Ändern
        print("Clicking Ändern...")
        await page.locator('[data-action="signup_init_change"]').click()
        await page.wait_for_timeout(3_000)

        # Click first available weekday
        first_day = page.locator('td[data-date]').filter(
            has=page.locator(':scope.fc-day-future:not(.termin-booked-out):not(.fc-day-sat):not(.fc-day-sun)')
        ).first
        if await first_day.count() == 0:
            # Fallback: just click any future non-booked-out day
            days = page.locator('td[data-date]')
            count = await days.count()
            for i in range(count):
                day = days.nth(i)
                cls = await day.get_attribute("class") or ""
                if "fc-day-future" in cls and "termin-booked-out" not in cls and "fc-day-sat" not in cls and "fc-day-sun" not in cls:
                    first_day = day
                    break

        date_val = await first_day.get_attribute("data-date")
        print(f"Clicking day: {date_val}")
        await first_day.click()
        await page.wait_for_timeout(2_000)

        # Click the first time slot
        slot = page.locator('tr.fc-list-event').first
        slot_text = await slot.locator('td').first.text_content()
        print(f"Clicking time slot: {slot_text.strip()}")
        await slot.click()
        await page.wait_for_timeout(2_000)

        # Now enable route interception before clicking confirm
        await page.route("**/*", handle_route)

        # Find and click the confirm/save button
        # Common labels: Speichern, Bestätigen, Weiter, Buchen
        for label in ["Speichern", "Bestätigen", "Weiter", "Buchen", "save", "confirm"]:
            btn = page.get_by_role("button", name=label)
            if await btn.count() > 0:
                print(f"Clicking confirm button: '{label}'")
                await btn.click()
                await page.wait_for_timeout(2_000)
                break
        else:
            print("No confirm button found — dumping all buttons:")
            buttons = await page.evaluate("""
                () => Array.from(document.querySelectorAll('button')).map(b => ({
                    text: b.textContent.trim(),
                    classes: b.className,
                    dataAction: b.getAttribute('data-action'),
                }))
            """)
            for b in buttons:
                print(f"  {b}")

        await page.unroute("**/*")

        print("\n--- All intercepted POST calls ---")
        for c in save_calls:
            print(f"\n  URL: {c['url']}")
            print(f"  BODY: {c['body'][:400]}")
            relevant_headers = {k: v for k, v in c["headers"].items()
                                if k.lower() in ("authorization", "content-type")}
            print(f"  HEADERS: {relevant_headers}")

        if not save_calls:
            print("  No POST calls intercepted after clicking confirm.")
            print("  All POSTs seen during session:")
            for c in api_calls:
                if c["method"] == "POST":
                    print(f"    {c['url']}  body={str(c['body'])[:100]}")

        print("\nBrowser stays open for 20s for inspection.")
        await page.wait_for_timeout(20_000)
        await browser.close()


asyncio.run(main())
