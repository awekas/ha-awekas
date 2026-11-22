"""Data update coordinator for the AWEKAS integration.

Protection of the AWEKAS servers:
 - one request at a time, never overlapping (DataUpdateCoordinator)
 - enforced minimum interval of 60 s and +/- 10 % jitter so that installations
   do not hit the API at the same second
 - exponential back-off on network/server errors (5, 10, 20, 40, max. 60 min),
   Retry-After is honoured, 15 minutes pause when the quota is exceeded
 - polling stops completely on permanent errors (invalid key, AWEKAS Plus not
   active) and Home Assistant asks the user to re-enter the key
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_API_KEY
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AwekasApiError,
    AwekasAuthError,
    AwekasClient,
    AwekasConnectionError,
    AwekasError,
    AwekasQuotaError,
)
from .const import (
    BACKOFF_MAX,
    BACKOFF_START,
    CONF_INTERVAL,
    CONF_LANGUAGE,
    DEFAULT_INTERVAL,
    DOMAIN,
    JITTER,
    LOGGER,
    MANUFACTURER,
    MAX_INTERVAL,
    MIN_INTERVAL,
    QUOTA_WAIT,
    STATION_REFRESH,
    STATION_REQUEST_DELAY,
    SUPPORTED_LANGUAGES,
)
from .util import to_text

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import AwekasConfigEntry

STATION_SECTIONS = ("station", "stationsweb", "sensorstatus")


@dataclass
class AwekasData:
    """Data of one station."""

    current: dict[str, Any]
    station: dict[str, Any] | None

    def section(self, name: str) -> dict[str, Any]:
        """Return a section ('current', 'day', '1h', 'forecast', 'station', ...)."""
        source = self.station if name in STATION_SECTIONS else self.current
        if source is None:
            return {}
        if name == "root":
            return source
        value = source.get(name)
        return value if isinstance(value, dict) else {}


def clamp_interval(value: Any) -> int:
    """Return a valid request interval in seconds."""
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL
    return max(MIN_INTERVAL, min(interval, MAX_INTERVAL))


def with_jitter(seconds: float) -> timedelta:
    """Add +/- 10 % random jitter."""
    return timedelta(seconds=seconds * (1 - JITTER + random.random() * 2 * JITTER))


class AwekasCoordinator(DataUpdateCoordinator[AwekasData]):
    """Fetch data from the AWEKAS Stations API."""

    config_entry: AwekasConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AwekasConfigEntry, user_agent: str
    ) -> None:
        """Initialize the coordinator."""
        self._interval = clamp_interval(entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL))
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=with_jitter(self._interval),
        )
        self.client = AwekasClient(
            async_get_clientsession(hass), entry.data[CONF_API_KEY], user_agent
        )
        self._backoff = 0.0
        self._station: dict[str, Any] | None = None
        self._station_fetched = 0.0

    @property
    def language(self) -> str:
        """Language for forecast texts."""
        configured = self.config_entry.options.get(CONF_LANGUAGE) or ""
        if configured in SUPPORTED_LANGUAGES:
            return configured
        system = (self.hass.config.language or "en")[:2].lower()
        return system if system in SUPPORTED_LANGUAGES else "en"

    async def _async_update_data(self) -> AwekasData:
        """Fetch the current values (and once a day the station data)."""
        try:
            current = await self.client.async_get_current(self.language)
        except AwekasAuthError as err:
            # stops polling; Home Assistant starts the re-authentication flow
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key=err.reason
            ) from err
        except AwekasQuotaError as err:
            self.update_interval = with_jitter(QUOTA_WAIT)
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="quota_exceeded"
            ) from err
        except AwekasConnectionError as err:
            if err.retry_after:
                delay = min(max(err.retry_after, self._interval), BACKOFF_MAX)
                self.update_interval = timedelta(seconds=delay)
            else:
                self.update_interval = self._next_backoff()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={
                    "error": str(err),
                    "minutes": str(round(self.update_interval.total_seconds() / 60)),
                },
            ) from err
        except AwekasApiError as err:
            self.update_interval = self._next_backoff()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._backoff = 0.0
        self.update_interval = with_jitter(self._interval)

        if self._station is None or time.monotonic() - self._station_fetched > STATION_REFRESH:
            await self._async_update_station()

        return AwekasData(current=current, station=self._station)

    async def _async_update_station(self) -> None:
        """Station data is optional: errors are only logged."""
        self._station_fetched = time.monotonic()
        await asyncio.sleep(STATION_REQUEST_DELAY)
        try:
            self._station = await self.client.async_get_station()
        except AwekasError as err:
            LOGGER.debug("Could not read station data: %s", err)

    def _next_backoff(self) -> timedelta:
        self._backoff = min(self._backoff * 2, BACKOFF_MAX) if self._backoff else BACKOFF_START
        return with_jitter(self._backoff)

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for the weather station."""
        station = self.data.section("station") if self.data else {}
        stationsweb = self.data.section("stationsweb") if self.data else {}
        location = to_text(station.get("location"))
        return DeviceInfo(
            identifiers={(DOMAIN, str(self.config_entry.unique_id))},
            name=f"AWEKAS {location}" if location else self.config_entry.title,
            manufacturer=MANUFACTURER,
            model=to_text(station.get("hardware")),
            sw_version=to_text(station.get("software")),
            configuration_url=_https_url(station.get("weblink"))
            or _https_url(stationsweb.get("weblink")),
        )


def _https_url(value: Any) -> str | None:
    """Only accept links to awekas.at over https."""
    text = to_text(value)
    if text and text.startswith("https://") and (
        text.split("/")[2] == "awekas.at" or text.split("/")[2].endswith(".awekas.at")
    ):
        return text
    return None
