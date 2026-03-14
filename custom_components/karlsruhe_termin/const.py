"""Constants for Karlsruhe Termin integration."""

DOMAIN = "karlsruhe_termin"

MANAGE_URL = "https://karlsruhe.konsentas.de/form/1/manage/{vorgangsnr}?code={zugangscode}"

CONF_VORGANGSNR = "vorgangsnr"
CONF_ZUGANGSCODE = "zugangscode"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIME_WINDOW_START = "time_window_start"  # "HH:MM"
CONF_TIME_WINDOW_END = "time_window_end"       # "HH:MM"
CONF_MIN_NOTICE_DAYS = "min_notice_days"

DEFAULT_SCAN_INTERVAL = 10  # minutes
DEFAULT_TIME_WINDOW_START = "00:00"
DEFAULT_TIME_WINDOW_END = "23:59"
DEFAULT_MIN_NOTICE_DAYS = 0

PLATFORMS = ["sensor", "button"]
