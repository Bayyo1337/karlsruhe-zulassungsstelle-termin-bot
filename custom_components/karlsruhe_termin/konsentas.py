"""Konsentas API client — pure aiohttp, no browser needed."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE = "https://karlsruhe.konsentas.de"
_XHR = {"X-Requested-With": "XMLHttpRequest"}


class KonsentasClient:
    """Interact with the Konsentas appointment API."""

    def __init__(self, vorgangsnr: str, zugangscode: str) -> None:
        self.vorgangsnr = vorgangsnr
        self.zugangscode = zugangscode
        self.manage_url = f"{BASE}/form/1/manage/{vorgangsnr}?code={zugangscode}"

    async def fetch_data(self) -> dict:
        """Return current appointment and available slots via direct API calls.

        Flow: login → init_change → getTimeslot + getFirstAvailableTimeslot.
        All authenticated with the userjwt returned by login.
        """
        async with aiohttp.ClientSession() as session:
            login = await _login(session, self.vorgangsnr, self.zugangscode)
            signup_recno = login["signup_recno"]
            current = login["current_appointment"]
            auth = {"Authorization": f"Bearer {login['jwt']}", **_XHR}

            await _init_change(session, auth, signup_recno, self.zugangscode)

            # 4. Get available days and earliest time slot
            available_days = await _get_available_days(session, auth, current["yeardate"])
            first_slot = await _get_first_available_slot(session, auth)

            earlier_found = (
                first_slot is not None
                and _yeardate_to_de(first_slot["yeardate"]) < current["date"]
            ) if first_slot else False

            return {
                "current_appointment": current,
                "available_appointments": [
                    _yeardate_to_de(d) for d in available_days
                ],
                "earliest_available": first_slot,
                "earlier_slot_found": earlier_found,
                "manage_url": self.manage_url,
                # Stored for the book_slot button
                "_jwt": jwt,
                "_signup_recno": signup_recno,
            }

    async def book_slot(self, slot_recno: str, jwt: str, signup_recno: int) -> bool:
        """Book a specific slot. Returns True on success."""
        async with aiohttp.ClientSession() as session:
            auth = {"Authorization": f"Bearer {jwt}", **_XHR}
            data = aiohttp.FormData()
            data.add_field("recno", slot_recno)
            data.add_field("signup_recno", str(signup_recno))
            async with session.post(
                f"{BASE}/api/brick_ota_termin_save/",
                data=data,
                headers=auth,
            ) as resp:
                body = await resp.json(content_type=None)
                _LOGGER.debug("book_slot response: %s", body)
                return body.get("code") == 3

    async def validate(self) -> bool:
        """Return True if credentials are valid."""
        try:
            async with aiohttp.ClientSession() as session:
                login = await _login(session, self.vorgangsnr, self.zugangscode)
                return bool(login.get("signup_recno"))
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Private API helpers
# ---------------------------------------------------------------------------

async def _login(session: aiohttp.ClientSession, vorgangsnr: str, zugangscode: str) -> dict:
    data = aiohttp.FormData()
    data.add_field("vgnr", vorgangsnr)
    data.add_field("accesscode", zugangscode)
    data.add_field("signupform_recno", "1")

    async with session.post(f"{BASE}/api/otamanage_user_login/", data=data, headers=_XHR) as resp:
        body = await resp.json(content_type=None)

    d = body.get("data", {})
    termins = d.get("termins", [])
    if not termins:
        raise ValueError("Login failed or no termins found")

    jwt = d.get("userjwt")
    if not jwt:
        raise ValueError("Login response missing userjwt")

    t = termins[0]
    yeardate = int(t["yeardate"])
    time_min = int(t["time"])

    return {
        "jwt": jwt,
        "signup_recno": d["signup_recno"],
        "current_appointment": {
            "date": _yeardate_to_de(yeardate),
            "time": _minutes_to_hhmm(time_min),
            "yeardate": yeardate,
        },
    }


async def _init_change(
    session: aiohttp.ClientSession,
    auth: dict,
    signup_recno: int,
    zugangscode: str,
) -> None:
    data = aiohttp.FormData()
    data.add_field("signup_recno", str(signup_recno))
    data.add_field("code", zugangscode)
    async with session.post(f"{BASE}/api/otamanage_init_change/", data=data, headers=auth) as resp:
        await resp.read()  # consume response


async def _get_available_days(
    session: aiohttp.ClientSession,
    auth: dict,
    current_yeardate: int,
) -> list[int]:
    """Return yeardates (YYYYMMDD ints) of days with open slots before the current appointment."""
    now = datetime.now(timezone.utc)
    start_ts = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end_ts = int((now + timedelta(days=90)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    async with session.get(
        f"{BASE}/api/brick_ota_termin_getTimeslot/",
        params={"start": start_ts, "end": end_ts},
        headers=auth,
    ) as resp:
        body = await resp.json(content_type=None)

    termins = body.get("data", {}).get("termins", [])
    available = []
    for t in termins:
        if int(t.get("places", 0)) <= 0:
            continue
        if t.get("className") == "termin-booked-out":
            continue
        yd = int(t["yeardate"])
        if yd < int(current_yeardate):
            available.append(yd)

    return sorted(available)


async def _get_first_available_slot(
    session: aiohttp.ClientSession,
    auth: dict,
) -> dict | None:
    """Return the earliest available time slot with date, start time, end time, places."""
    async with session.get(
        f"{BASE}/api/brick_ota_termin_getFirstAvailableTimeslot/",
        headers=auth,
    ) as resp:
        body = await resp.json(content_type=None)

    t = body.get("data", {}).get("termin")
    if not t:
        return None

    yeardate = int(t["yeardate"])
    time_start = int(t["time"])
    duration = int(t.get("duration", 15))
    time_end = time_start + duration

    return {
        "recno": t["recno"],
        "date": _yeardate_to_de(yeardate),
        "yeardate": yeardate,
        "time_start": _minutes_to_hhmm(time_start),
        "time_end": _minutes_to_hhmm(time_end),
        "places": int(t.get("places", 1)),
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _yeardate_to_de(yeardate: int) -> str:
    """Convert 20260325 → '25.03.2026'."""
    s = str(yeardate)
    return f"{s[6:8]}.{s[4:6]}.{s[0:4]}"


def _minutes_to_hhmm(minutes: int) -> str:
    """Convert 825 → '13:45'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
