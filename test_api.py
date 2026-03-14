"""
Test the aiohttp-based API client directly — no browser needed.

Usage:
    uv run python test_api.py
"""

import asyncio
import importlib.util
import sys
import types

# Load konsentas.py directly without triggering __init__.py (which needs homeassistant)
_const = types.ModuleType("karlsruhe_termin.const")
_const.MANAGE_URL = "https://karlsruhe.konsentas.de/form/1/manage/{vorgangsnr}?code={zugangscode}"
sys.modules["karlsruhe_termin"] = types.ModuleType("karlsruhe_termin")
sys.modules["karlsruhe_termin.const"] = _const

_spec = importlib.util.spec_from_file_location(
    "karlsruhe_termin.konsentas",
    "custom_components/karlsruhe_termin/konsentas.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
KonsentasClient = _mod.KonsentasClient

VORGANGSNR = "CA-5250317A"
ZUGANGSCODE = "8638"


async def main():
    import aiohttp, base64
    BASE = _mod.BASE
    _XHR = _mod._XHR

    print("--- Step-by-step API debug ---\n")
    async with aiohttp.ClientSession() as session:
        manage_url = f"{BASE}/form/1/manage/{VORGANGSNR}?code={ZUGANGSCODE}"

        print("1. GET manage page...")
        async with session.get(manage_url) as r:
            print(f"   status={r.status}")

        print("2. POST login → get userjwt...")
        data = aiohttp.FormData()
        data.add_field("vgnr", VORGANGSNR)
        data.add_field("accesscode", ZUGANGSCODE)
        data.add_field("signupform_recno", "1")
        async with session.post(f"{BASE}/api/otamanage_user_login/", data=data, headers=_XHR) as r:
            login_body = await r.json(content_type=None)
            login_data = login_body.get("data", {})
            jwt = login_data.get("userjwt")
            signup_recno = login_data.get("signup_recno")
            print(f"   status={r.status}  userjwt={'OK' if jwt else 'MISSING'}  signup_recno={signup_recno}  can_change={login_data.get('signup_can_change')}")

        if not jwt:
            print("   ERROR: no userjwt in login response")
            return
        auth = {"Authorization": f"Bearer {jwt}", **_XHR}

        print("3. POST init_change (using userjwt from login)...")
        data2 = aiohttp.FormData()
        data2.add_field("signup_recno", str(signup_recno))
        data2.add_field("code", ZUGANGSCODE)
        async with session.post(f"{BASE}/api/otamanage_init_change/", data=data2, headers=auth) as r:
            text = await r.text()
            print(f"   status={r.status}  body={text[:300]}")

        print("5. GET getTimeslot...")
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        start_ts = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        end_ts = int((now + timedelta(days=90)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        async with session.get(
            f"{BASE}/api/brick_ota_termin_getTimeslot/",
            params={"start": start_ts, "end": end_ts},
            headers=auth,
        ) as r:
            body = await r.json(content_type=None)
            print(f"   status={r.status}  body={str(body)[:400]}")

        print("6. GET getFirstAvailableTimeslot...")
        async with session.get(f"{BASE}/api/brick_ota_termin_getFirstAvailableTimeslot/", headers=auth) as r:
            body = await r.json(content_type=None)
            print(f"   status={r.status}  body={str(body)[:400]}")

    print("\n--- Full client fetch ---\n")
    client = KonsentasClient(VORGANGSNR, ZUGANGSCODE)
    print("Fetching appointment data via API (no browser)...\n")
    data = await client.fetch_data()

    appt = data["current_appointment"]
    print(f"Current appointment : {appt['date']} {appt['time']}")

    available = data["available_appointments"]
    print(f"Available days (earlier than current): {available}")

    slot = data["earliest_available"]
    if slot:
        print(f"Earliest slot       : {slot['date']} {slot['time_start']}–{slot['time_end']}  ({slot['places']} Platz frei)")
        print(f"Slot recno          : {slot['recno']}")
    else:
        print("Earliest slot       : none found")

    print(f"Earlier slot found  : {data['earlier_slot_found']}")


asyncio.run(main())
