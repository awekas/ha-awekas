"""Diagnostics support for AWEKAS. The API key and the exact position are removed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import AwekasConfigEntry

TO_REDACT = {CONF_API_KEY, "key", "londec", "latdec", "camlink"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AwekasConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "update_interval_s": coordinator.update_interval.total_seconds()
        if coordinator.update_interval
        else None,
        "last_update_success": coordinator.last_update_success,
        "current": async_redact_data(data.current, TO_REDACT) if data else None,
        "station": async_redact_data(data.station, TO_REDACT) if data and data.station else None,
    }
