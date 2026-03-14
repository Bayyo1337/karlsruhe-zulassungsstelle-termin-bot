"""
Standalone test — verifies the API client works without Home Assistant.

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
    client = KonsentasClient(VORGANGSNR, ZUGANGSCODE)
    print("Fetching appointment data...\n")
    data = await client.fetch_data()

    appt = data["current_appointment"]
    print(f"Current appointment : {appt['date']} {appt['time']}")
    print(f"Available days      : {data['available_appointments']}")

    slot = data["earliest_available"]
    if slot:
        print(f"Earliest slot       : {slot['date']} {slot['time_start']}–{slot['time_end']}  ({slot['places']} Platz frei)")
    else:
        print("Earliest slot       : none found")

    print(f"Earlier slot found  : {data['earlier_slot_found']}")


asyncio.run(main())
