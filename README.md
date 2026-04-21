# Karlsruhe Zulassungsstelle Termin

Home Assistant integration that monitors the Karlsruhe vehicle registration office (Zulassungsstelle) for earlier appointment slots and notifies you when one becomes available.

## Requirements

- An existing appointment at [karlsruhe.konsentas.de](https://karlsruhe.konsentas.de)
- Your **Vorgangsnummer** and **Zugangscode** from the booking confirmation email
- Home Assistant with [HACS](https://hacs.xyz) installed

## Installation

### Via HACS (recommended)

1. Open HACS → **Integrations**
2. Click the three-dot menu (⋮) → **Custom repositories**
3. Add `https://github.com/Bayyo1337/karlsruhe-zulassungsstelle-termin-bot` as type **Integration**
4. Click **Download** on the new entry
5. Restart Home Assistant

### Manual

Copy the `custom_components/karlsruhe_termin/` folder into your HA `/config/custom_components/` directory and restart.

## Setup

1. Go to **Settings → Integrations → Add Integration**
2. Search for **Karlsruhe Zulassungsstelle**
3. Enter your **Vorgangsnummer** (e.g. `CA-1360317A`) and **Zugangscode** (e.g. `1337`)
4. Set a polling interval (default: 10 minutes)
5. Optionally configure filters (see below)

## Entities

| Entity | Description |
|--------|-------------|
| `sensor.aktueller_termin` | Your currently booked appointment date and time |
| `sensor.fruhester_verfugbarer_termin` | The earliest available slot (date + time) |
| `sensor.zuletzt_aktualisiert` | Timestamp of the last successful data fetch |
| `button.fruhesten_termin_buchen` | Books the earlier slot — only active when an earlier slot exists |
| `button.termin_stornieren` | Cancels your current appointment — **use with caution** |

The earliest available sensor includes these attributes:
- `time_start` / `time_end` — time window of the slot
- `places` — number of available seats
- `all_available_days` — all available weekdays found
- `is_earlier_than_current` — `true` when the slot is before your current appointment

## Optional filters

Configure these during setup to narrow which earlier slots are considered valid:

| Setting | Default | Description |
|---------|---------|-------------|
| `time_window_start` | `00:00` | Ignore slots starting before this time (e.g. `09:00`) |
| `time_window_end` | `23:59` | Ignore slots starting after this time (e.g. `15:00`) |
| `min_notice_days` | `0` | Ignore slots fewer than N days from today (e.g. `2`) |

## Multiple appointments

Add the integration multiple times (once per Vorgangsnummer) to monitor several appointments simultaneously. Each instance creates its own set of entities.

## Automation example

Get notified (e.g. on your phone) when an earlier slot opens up:

```yaml
alias: "Zulassung – Früherer Termin verfügbar"
trigger:
  - platform: state
    entity_id: sensor.fruhester_verfugbarer_termin
condition:
  - condition: template
    value_template: "{{ state_attr('sensor.fruhester_verfugbarer_termin', 'is_earlier_than_current') }}"
action:
  - service: notify.mobile_app_dein_telefon
    data:
      title: "Früherer Termin verfügbar!"
      message: >
        {{ states('sensor.fruhester_verfugbarer_termin') }} —
        {{ state_attr('sensor.fruhester_verfugbarer_termin', 'places') }} Platz frei
```

## Notes

- The integration uses the Konsentas REST API directly — no browser or Chromium required
- Both the booking and cancellation endpoints were confirmed via Playwright network interception
- Always verify any booking or cancellation on the [Konsentas website](https://karlsruhe.konsentas.de) afterwards
- Polling too frequently may result in rate limiting; 10 minutes worked for me
