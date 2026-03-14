# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Home Assistant custom integration that monitors the Karlsruhe Zulassungsstelle (Konsentas system) for earlier appointment slots. No browser or Chromium — uses the Konsentas REST API directly via `aiohttp`.

## Local testing (no HA needed)

```bash
cd dev
uv run python test_api.py
```

## Integration structure

```
custom_components/karlsruhe_termin/
├── __init__.py       # entry setup/unload, wires client + coordinator
├── config_flow.py    # UI: Vorgangsnr + Zugangscode + scan interval + filters
├── const.py          # DOMAIN, config keys, defaults, PLATFORMS
├── coordinator.py    # DataUpdateCoordinator — fires karlsruhe_termin_earlier_appointment event, tracks last_fetch_time
├── konsentas.py      # API client (fetch_data, book_slot, cancel_appointment, validate)
├── sensor.py         # CurrentAppointmentSensor, EarliestAvailableSensor, LastUpdatedSensor
├── button.py         # BookEarliestButton, CancelAppointmentButton
├── manifest.json     # no extra requirements (aiohttp is built into HA)
└── strings.json      # German UI labels for config flow
```

## API flow (konsentas.py)

1. `POST /api/otamanage_user_login/` — returns current appointment + `userjwt`
2. `POST /api/otamanage_init_change/` — enters change mode (requires JWT)
3. `GET /api/brick_ota_termin_getTimeslot/` — available days with `places > 0`
4. `GET /api/brick_ota_termin_getFirstAvailableTimeslot/` — earliest slot with exact time

The `userjwt` from step 1 is used as `Authorization: Bearer <jwt>` for all subsequent calls.

## Key data shapes

- Dates returned by the API use `yeardate: 20260325` (YYYYMMDD int) — converted to `DD.MM.YYYY` by `_yeardate_to_de()`
- Times are minutes since midnight (`time: 825` → `13:45`) — converted by `_minutes_to_hhmm()`
- `earlier_slot_found` compares `first_slot["yeardate"] < current["yeardate"]` (int comparison)
- Config stores time window as `"HH:MM"` strings; `_hhmm_to_minutes()` converts to int for comparison

## Booking endpoint

`book_slot()` does a fresh login, calls `init_change`, then posts to `postOtaNextStep` with:
- `formdata[ota_termin_id]` = slot recno (e.g. `::20260326:620:635`)
- `ota_termin_resource_group` = `""` (empty)
- `formdata[ota_termin_resource_group]` = `""` (empty)

Success: `body["code"] == 3`. Endpoint confirmed via Playwright interception (`dev/test_booking_endpoint.py`).

## Cancellation endpoint

`cancel_appointment()` does a fresh login, then posts to `otamanage_init_storno` with:
- `signup_recno` = the signup recno from login response
- `code` = zugangscode

Success: HTTP 200. Endpoint confirmed via Playwright interception (`dev/test_storno_endpoint.py`).

## Filters (optional config)

- **Time window** (`time_window_start` / `time_window_end`): `earliest_available` is suppressed if the slot falls outside the HH:MM window. Does not affect `available_appointments` list (date-only, no time info from API).
- **Minimum notice** (`min_notice_days`): Filters out slots (and available days) within N days of today.
