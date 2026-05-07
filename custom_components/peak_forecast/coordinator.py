"""DataUpdateCoordinator that scrapes the peak forecast page on a schedule."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_URL,
    DOMAIN,
)
from .parser import ForecastParseError, ForecastSnapshot, parse_html

_LOGGER = logging.getLogger(__name__)

INTEGRATION_VERSION = "0.1.0"
USER_AGENT = (
    f"HomeAssistant-PeakForecast/{INTEGRATION_VERSION} "
    "(+https://github.com/markweishaar/peakForecast)"
)
REQUEST_TIMEOUT_SECONDS = 30.0


class PeakForecastCoordinator(DataUpdateCoordinator[ForecastSnapshot]):
    """Polls the configured URL and exposes a parsed ForecastSnapshot to entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        merged = {**entry.data, **entry.options}
        self._url: str = merged.get(CONF_URL, DEFAULT_URL)
        interval_minutes: int = int(
            merged.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)
        )
        self.entry_id = entry.entry_id
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
        )
        self._client = get_async_client(hass)

    async def _async_update_data(self) -> ForecastSnapshot:
        try:
            response = await self._client.get(
                self._url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
        except httpx.HTTPError as err:
            raise UpdateFailed(f"failed to fetch {self._url}: {err}") from err

        if response.status_code >= 400:
            raise UpdateFailed(
                f"unexpected status {response.status_code} from {self._url}"
            )

        try:
            return parse_html(response.text, fetched_at=datetime.now(timezone.utc))
        except ForecastParseError as err:
            raise UpdateFailed(f"parse error: {err}") from err
