"""Constants for Karlsruhe Termin integration."""

DOMAIN = "karlsruhe_termin"

MANAGE_URL = "https://karlsruhe.konsentas.de/form/1/manage/{vorgangsnr}?code={zugangscode}"

CONF_VORGANGSNR = "vorgangsnr"
CONF_ZUGANGSCODE = "zugangscode"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 10  # minutes

PLATFORMS = ["sensor", "button"]
