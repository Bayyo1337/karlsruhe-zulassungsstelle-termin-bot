"""
Standalone test — run this to verify the scraper works against the live site.

Usage:
    pip install playwright
    playwright install chromium
    python test_scraper.py
"""

import asyncio
from playwright.async_api import async_playwright

VORGANGSNR = "CA-5250317A"
ZUGANGSCODE = "8638"
MANAGE_URL = f"https://karlsruhe.konsentas.de/form/1/manage/{VORGANGSNR}?code={ZUGANGSCODE}"


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # headless=False so you can watch
        page = await browser.new_page()

        # Intercept all XHR/fetch requests
        api_calls: list[dict] = []

        async def on_request(request):
            if request.resource_type in ("xhr", "fetch"):
                api_calls.append({
                    "method": request.method,
                    "url": request.url,
                    "post_data": request.post_data,
                    "headers": {
                        k: v for k, v in request.headers.items()
                        if k.lower() in ("authorization", "x-requested-with", "content-type", "cookie", "x-jwt", "x-auth")
                    },
                })

        async def on_response(response):
            if response.request.resource_type in ("xhr", "fetch"):
                try:
                    body = await response.text()
                    for call in reversed(api_calls):
                        if call["url"] == response.url and "response" not in call:
                            call["status"] = response.status
                            call["response"] = body[:800]
                            break
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"Opening: {MANAGE_URL}")
        await page.goto(MANAGE_URL, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(2_000)

        # Dump page title so we know we landed on the right page
        print(f"Page title: {await page.title()}")

        # --- Step 1: find current appointment date ---
        current = await page.evaluate(r"""
            () => {
                const cells = Array.from(document.querySelectorAll('td'));
                const dates = cells
                    .map(c => c.textContent.trim())
                    .filter(t => /^\d{1,2}\.\d{1,2}\.\d{4}/.test(t));
                console.log('td texts with dates:', dates);
                return dates;
            }
        """)
        print(f"\n[Step 1] Dates found in <td> elements: {current}")

        # --- Step 2: find the Ändern button ---
        btn = page.locator('[data-action="signup_init_change"]')
        btn_count = await btn.count()
        print(f"\n[Step 2] 'Ändern' button count: {btn_count}")

        if btn_count == 0:
            # Dump all buttons so we can find the right selector
            buttons = await page.evaluate("""
                () => Array.from(document.querySelectorAll('button, [type=button], a')).map(el => ({
                    tag: el.tagName,
                    text: el.textContent.trim().slice(0, 60),
                    dataAction: el.getAttribute('data-action'),
                    id: el.id,
                    classes: el.className,
                }))
            """)
            print("  All clickable elements found:")
            for b in buttons:
                print(f"    {b}")
        else:
            print("  Clicking 'Ändern'...")
            await btn.click()
            await page.wait_for_timeout(3_000)

            # --- Step 3: find available slots ---
            available = await page.evaluate(
                """
                () => {
                    const tds = document.querySelectorAll('td[data-date]');
                    const available = [];
                    tds.forEach(td => {
                        const cls = td.className;
                        if (!cls.includes('fc-day-future')) return;
                        if (cls.includes('termin-booked-out')) return;
                        if (cls.includes('fc-day-sat') || cls.includes('fc-day-sun')) return;
                        const [y, m, d] = td.getAttribute('data-date').split('-');
                        available.push(`${d}.${m}.${y}`);
                    });
                    available.sort((a, b) => {
                        const [ad, am, ay] = a.split('.').map(Number);
                        const [bd, bm, by] = b.split('.').map(Number);
                        return new Date(ay, am - 1, ad) - new Date(by, bm - 1, bd);
                    });
                    return available;
                }
                """
            )

            current_date = current[0] if isinstance(current, list) else current
            print(f"\n[Step 3] Current appointment : {current_date}")
            print(f"         Available slots      : {available}")
            if available and current_date:
                from datetime import datetime
                def parse(s): return datetime.strptime(s, "%d.%m.%Y")
                earlier = [d for d in available if parse(d) < parse(current_date)]
                print(f"         Earlier than current : {earlier}")

        # --- Step 4: click the first available future weekday and dump time slots ---
        if available:
            first = available[0]
            y, m, d = first.split('.')[::-1]  # DD.MM.YYYY -> YYYY, MM, DD
            iso = f"{y}-{m}-{d}"
            print(f"\n[Step 4] Clicking first available day: {first} (data-date={iso})")
            await page.locator(f'td[data-date="{iso}"]').click()
            await page.wait_for_timeout(2_000)

            time_slots = await page.evaluate(
                r"""
                () => {
                    const rows = document.querySelectorAll('tr.fc-list-event');
                    const slots = [];
                    rows.forEach(row => {
                        const text = row.textContent.trim();
                        const timeMatch = text.match(/^(\d{1,2}:\d{2} - \d{1,2}:\d{2})/);
                        const countMatch = text.match(/(\d+) Pl[äa]tze? frei/);
                        if (timeMatch) {
                            slots.push({
                                time: timeMatch[1],
                                available: countMatch ? parseInt(countMatch[1]) : 1,
                            });
                        }
                    });
                    return slots;
                }
                """
            )

            print(f"  Time slots for {first}:")
            for s in time_slots:
                print(f"    {s['time']}  —  {s['available']} Platz/Plätze frei")

        # --- Step 5: click first time slot to reveal booking endpoint (don't confirm) ---
        first_slot = page.locator('tr.fc-list-event').first
        if await first_slot.count() > 0:
            print("\n[Step 5] Clicking first time slot to find booking API...")
            await first_slot.click()
            await page.wait_for_timeout(2_000)
            # Just capture what appeared — don't click confirm/save
            new_calls = [c for c in api_calls if "brick_ota_termin" in c["url"] and "save" in c["url"].lower()]
            if not new_calls:
                print("  No 'save' endpoint captured yet — dumping all new calls:")
                for c in api_calls[-5:]:
                    print(f"  {c['method']} {c['url']}")

        print("\n--- API calls intercepted ---")
        for call in api_calls:
            print(f"\n  {call['method']} {call['url']}")
            if call.get("headers"):
                print(f"  HEADERS: {call['headers']}")
            if call.get("post_data"):
                print(f"  BODY: {call['post_data'][:400]}")
            print(f"  STATUS: {call.get('status')}")
            print(f"  RESPONSE: {call.get('response', '(not captured)')[:400]}")

        print("\n--- Done. Browser stays open for 30s so you can inspect the page. ---")
        await page.wait_for_timeout(30_000)
        await browser.close()


asyncio.run(main())
