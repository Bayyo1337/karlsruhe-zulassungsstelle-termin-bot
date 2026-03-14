# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Home Assistant custom integration that monitors the Karlsruhe Zulassungsstelle (vehicle registration office) for earlier appointment slots via the Konsentas booking system (`karlsruhe.konsentas.de`).

Users need a valid appointment first (Vorgangsnummer + Zugangscode, e.g. `CA-5250317A` / `8638`). The integration polls the manage page, compares available slots against the current booking, and fires a `karlsruhe_termin_earlier_appointment` HA event when an earlier date is found.

## Setup

```bash
# Install dependencies
pip install playwright
playwright install chromium
```

> **Note for HA container users:** Playwright/Chromium must be installed inside the container. See `PRODUCTION-SOLUTION.md` for context.

## Integration structure

```
custom_components/karlsruhe_termin/
├── __init__.py        # entry setup/unload
├── config_flow.py     # UI: Vorgangsnr + Zugangscode + scan interval
├── const.py           # DOMAIN, config keys, MANAGE_URL template
├── coordinator.py     # DataUpdateCoordinator, fires HA event on earlier slot
├── konsentas.py       # Playwright client (fetch_data, validate)
├── manifest.json
├── sensor.py          # CurrentAppointmentSensor, EarliestAvailableSensor
└── strings.json       # German UI labels
```

## Key design decisions

- **Single browser session per poll**: `konsentas.py` opens one Chromium instance, reads the current appointment from the table, clicks "Ändern", extracts available slots from the Bootstrap Datepicker, then closes.
- **All date strings are DD.MM.YYYY** (German format). The JS helper in `konsentas.py` also handles Unix timestamps from `data-date` attributes.
- **Event payload** of `karlsruhe_termin_earlier_appointment`: `{current, earlier, manage_url}` — use this in HA automations to send notifications.
- **Selector for the change button**: `[data-action="signup_init_change"]` — stable Konsentas attribute per `PRODUCTION-SOLUTION.md`.

## HA automation example

```yaml
trigger:
  platform: event
  event_type: karlsruhe_termin_earlier_appointment
action:
  - service: notify.mobile_app_dein_telefon
    data:
      title: "Früherer Termin verfügbar!"
      message: "{{ trigger.event.data.earlier }} (vorher: {{ trigger.event.data.current }})"
      data:
        clickAction: "{{ trigger.event.data.manage_url }}"
```
