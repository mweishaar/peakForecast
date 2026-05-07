"""Constants for the Peak Forecast integration."""
from __future__ import annotations

DOMAIN = "peak_forecast"
PLATFORMS: list[str] = ["sensor", "binary_sensor"]

DEFAULT_URL = "https://capitalelec.com/peak-forecast"
DEFAULT_SCAN_INTERVAL_MINUTES = 15
MIN_SCAN_INTERVAL_MINUTES = 5

SOURCE_TIMEZONE = "America/Chicago"
PERIOD_DURATION_MINUTES = 30

LEVEL_LOW = 0
LEVEL_MEDIUM = 1
LEVEL_HIGH = 2
LEVEL_UNKNOWN = -1

LEVEL_NAMES: dict[int, str] = {
    LEVEL_LOW: "low",
    LEVEL_MEDIUM: "medium",
    LEVEL_HIGH: "high",
    LEVEL_UNKNOWN: "unknown",
}

CONF_URL = "url"
CONF_SCAN_INTERVAL = "scan_interval_minutes"

ATTRIBUTION = "Data from Capital Electric Cooperative (capitalelec.com)"
MANUFACTURER = "Capital Electric Cooperative"
DEVICE_NAME = "Peak Forecast"
