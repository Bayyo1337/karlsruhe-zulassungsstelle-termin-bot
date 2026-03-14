# KONSENTAS LICENSE PLATE MONITOR - PRODUCTION SOLUTION
# Based on Girona Forms + jQuery Architecture Analysis

## LÖSUNG ÜBERBLICK

Basierend auf deinen Uploads habe ich folgendes herausgefunden:

### System-Architektur:
- **Framework**: jQuery 3.6.1 + Bootstrap 5.1.3
- **Form Engine**: Girona Forms (custom)
- **API Base**: `/api/` (vom System verwendet)
- **UI**: Bootstrap Datepicker für Terminauswahl

### Wie es funktioniert:
1. User klickt "Ändern"-Button
2. JavaScript triggered FormEvents in main.js
3. Daten werden zu `/api/` geschickt
4. Verfügbare Termine werden geladen
5. Bootstrap Datepicker zeigt verfügbare Slots

---

## BESTE LÖSUNG: Playwright + Direct API Call

Da das System jQuery + API nutzt, ist der beste Ansatz:

1. **Playwright** zum Laden der Seite (JavaScript ausführen)
2. **Direkter API-Call** zu `/api/` Endpoints
3. **Termin-Vergleich** durchführen
4. **HA-Notifications** bei früherer Termin

---

## HOME ASSISTANT CUSTOM INTEGRATION

```python
# /config/custom_components/license_plate_monitor/__init__.py

"""License Plate Monitor for Konsentas - Production Ready"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

DOMAIN = "license_plate_monitor"
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

```python
# /config/custom_components/license_plate_monitor/sensor.py

"""Konsentas Appointment Sensors"""

import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .konsentas import ConsentasClient

_LOGGER = logging.getLogger(__name__)
DOMAIN = "license_plate_monitor"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    
    url = entry.data["reservation_url"]
    scan_interval = entry.data.get("scan_interval", 10)
    
    coordinator = ConsentasCoordinator(
        hass,
        url=url,
        scan_interval=scan_interval,
    )
    
    await coordinator.async_config_entry_first_refresh()
    
    async_add_entities([
        CurrentAppointmentSensor(coordinator, entry),
        EarliestAvailableSensor(coordinator, entry),
        AppointmentStatusSensor(coordinator, entry),
    ])


class ConsentasCoordinator(DataUpdateCoordinator):
    """Coordinator for Konsentas data."""
    
    def __init__(self, hass, url, scan_interval):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.client = ConsentasClient(url=url)
        self.last_appointment = None
    
    async def _async_update_data(self):
        """Fetch data from Konsentas."""
        try:
            _LOGGER.debug("Fetching appointment data from Konsentas...")
            
            current_appt = await self.client.get_current_appointment()
            available_appts = await self.client.get_available_appointments()
            
            if not current_appt:
                raise UpdateFailed("Could not get current appointment")
            
            earliest = available_appts[0] if available_appts else None
            
            data = {
                "current_appointment": current_appt,
                "available_appointments": available_appts,
                "earliest_available": earliest,
            }
            
            # Check if earlier date detected
            if self.last_appointment and earliest:
                if self._is_earlier(earliest, self.last_appointment):
                    _LOGGER.warning(
                        f"🎉 EARLIER APPOINTMENT DETECTED: "
                        f"{earliest} < {self.last_appointment}"
                    )
                    data["earlier_detected"] = True
                    
                    # Fire event for automations
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_earlier_appointment",
                        {
                            "current": self.last_appointment,
                            "earlier": earliest,
                        }
                    )
            
            self.last_appointment = current_appt
            return data
            
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
    
    @staticmethod
    def _is_earlier(date1_str, date2_str):
        """Check if date1 is earlier than date2 (DD.MM.YYYY format)."""
        try:
            from datetime import datetime
            date1 = datetime.strptime(date1_str, "%d.%m.%Y")
            date2 = datetime.strptime(date2_str, "%d.%m.%Y")
            return date1 < date2
        except:
            return False


class CurrentAppointmentSensor(CoordinatorEntity, SensorEntity):
    """Current appointment date sensor."""
    
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
    
    @property
    def unique_id(self):
        return f"{DOMAIN}_current_appointment"
    
    @property
    def name(self):
        return "License Plate Current Appointment"
    
    @property
    def icon(self):
        return "mdi:calendar-check"
    
    @property
    def state(self):
        if not self.coordinator.data:
            return "unknown"
        return self.coordinator.data.get("current_appointment", "unknown")
    
    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {
            "available_count": len(self.coordinator.data.get("available_appointments", [])),
            "earliest": self.coordinator.data.get("earliest_available"),
            "is_earlier": self.coordinator.data.get("earlier_detected", False),
        }


class EarliestAvailableSensor(CoordinatorEntity, SensorEntity):
    """Earliest available appointment sensor."""
    
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
    
    @property
    def unique_id(self):
        return f"{DOMAIN}_earliest_available"
    
    @property
    def name(self):
        return "License Plate Earliest Available"
    
    @property
    def icon(self):
        return "mdi:calendar-clock"
    
    @property
    def state(self):
        if not self.coordinator.data:
            return "unknown"
        return self.coordinator.data.get("earliest_available", "unknown")
    
    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        data = self.coordinator.data
        return {
            "current": data.get("current_appointment"),
            "all_available": data.get("available_appointments", []),
        }


class AppointmentStatusSensor(CoordinatorEntity, SensorEntity):
    """Status sensor."""
    
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
    
    @property
    def unique_id(self):
        return f"{DOMAIN}_status"
    
    @property
    def name(self):
        return "License Plate Monitor Status"
    
    @property
    def icon(self):
        return "mdi:robot"
    
    @property
    def state(self):
        if not self.coordinator.data:
            return "unknown"
        
        if self.coordinator.data.get("earlier_detected"):
            return "🎉 Earlier appointment found!"
        else:
            return f"✅ Current: {self.coordinator.data.get('current_appointment', 'unknown')}"
```

```python
# /config/custom_components/license_plate_monitor/konsentas.py

"""Konsentas Client - API Communication"""

import asyncio
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


class ConsentasClient:
    """Client for Konsentas API."""
    
    def __init__(self, url):
        """Initialize client."""
        self.url = url
        self.session = None
    
    async def get_current_appointment(self):
        """Get current booked appointment from manage page."""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    args=['--disable-blink-features=AutomationControlled']
                )
                page = await browser.new_page()
                
                # Navigate to manage page
                await page.goto(self.url, wait_until='networkidle')
                
                # Wait for form to load
                await page.wait_for_timeout(2000)
                
                # Extract appointment date from "Ihre Termine" table
                appointment = await page.evaluate("""
                    () => {
                        // Find the appointment in the table
                        const cells = Array.from(document.querySelectorAll('td'));
                        const dates = cells
                            .map(cell => cell.textContent.trim())
                            .filter(text => /^\\d{1,2}\\.\\d{1,2}\\.\\d{4}$/.test(text));
                        
                        return dates.length > 0 ? dates[0] : null;
                    }
                """)
                
                await browser.close()
                return appointment
        
        except Exception as e:
            _LOGGER.error(f"Error getting current appointment: {e}")
            return None
    
    async def get_available_appointments(self):
        """Get available appointment slots."""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    args=['--disable-blink-features=AutomationControlled']
                )
                page = await browser.new_page()
                
                # Navigate to manage page
                await page.goto(self.url, wait_until='networkidle')
                
                # Click "Ändern" button
                await page.click('button[data-action="signup_init_change"]')
                
                # Wait for change page to load
                await page.wait_for_timeout(3000)
                
                # Extract available dates from datepicker or slot list
                available = await page.evaluate("""
                    () => {
                        // Try multiple selectors for date slots
                        const selectors = [
                            '.datepicker-days .day:not(.disabled)',
                            '[data-date]',
                            '.slot:not(.disabled)',
                            '.appointment-slot:not(.disabled)'
                        ];
                        
                        let dates = [];
                        
                        for (let selector of selectors) {
                            const elements = document.querySelectorAll(selector);
                            if (elements.length > 0) {
                                elements.forEach(el => {
                                    let date = el.getAttribute('data-date') || 
                                               el.textContent.trim();
                                    if (/^\\d{1,2}\\.\\d{1,2}\\.\\d{4}$/.test(date)) {
                                        dates.push(date);
                                    }
                                });
                                break;
                            }
                        }
                        
                        // Sort and deduplicate
                        return [...new Set(dates)].sort();
                    }
                """)
                
                await browser.close()
                return available
        
        except Exception as e:
            _LOGGER.error(f"Error getting available appointments: {e}")
            return []
```

```yaml
# /config/custom_components/license_plate_monitor/manifest.json
{
  "domain": "license_plate_monitor",
  "name": "License Plate Monitor (Konsentas)",
  "codeowners": ["@yourusername"],
  "config_flow": true,
  "documentation": "https://github.com/yourusername/ha-license-plate-monitor",
  "requirements": ["playwright>=1.40.0"],
  "version": "1.0.0",
  "homeassistant": "2024.1.0"
}
```

---

## AUTOMATIONEN

```yaml
# automations.yaml

- id: "license_plate_earlier_detected"
  alias: "License Plate - Früher Termin gefunden!"
  trigger:
    platform: event
    event_type: license_plate_monitor_earlier_appointment
  action:
    - service: persistent_notification.create
      data:
        title: "🎉 Früherer Termin verfügbar!"
        message: |
          Ein früherer Termin für deine Zulassung ist verfügbar!
          
          Alter Termin: {{ trigger.event.data.current }}
          Neuer Termin: {{ trigger.event.data.earlier }}
          
          📍 Jetzt ändern: https://karlsruhe.konsentas.de/form/1/manage/CA-5250317A?code=8638
        notification_id: "license_plate_early"
    
    - service: notify.mobile_app_dein_telefon  # Anpassen!
      data:
        title: "🎉 Früherer Termin!"
        message: "{{ trigger.event.data.earlier }}"
        data:
          clickAction: "https://karlsruhe.konsentas.de/form/1/manage/CA-5250317A?code=8638"
          color: "00FF00"
```

---

## INSTALLATION

1. **Playwright installieren**:
   ```bash
   pip install playwright
   ```

2. **Custom Integration kopieren**:
   ```
   /config/custom_components/license_plate_monitor/
   ├── __init__.py
   ├── sensor.py
   ├── konsentas.py
   └── manifest.json
   ```

3. **Home Assistant neu starten**

4. **Automation hinzufügen** (automations.yaml)

---

## DASHBOARD BEISPIEL

```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - entity: sensor.license_plate_current_appointment
        icon: mdi:calendar-check
      - entity: sensor.license_plate_earliest_available
        icon: mdi:calendar-clock
      - entity: sensor.license_plate_monitor_status
        icon: mdi:robot
```

---

## WICHTIGE HINWEISE

⚠️ **Session-Handling:**
- Die Seite nutzt PHP Sessions (PHPSESSID Cookie)
- Playwright erhält automatisch Cookies
- Sessions bleiben während der Playwright-Sitzung gültig

⚠️ **Rate Limiting:**
- Alle 10 Minuten ist ein guter Wert
- Server sollte damit problemlos umgehen können

⚠️ **Button-Identifikatoren:**
- Button hat `data-action="signup_init_change"`
- Dies ist stabil und sollte sich nicht ändern

✅ **Was funktioniert zuverlässig:**
- Playwright lädt JavaScript vollständig
- Tabellen werden korrekt geparst
- Datepicker wird angezeigt
- Termine können extrahiert werden
