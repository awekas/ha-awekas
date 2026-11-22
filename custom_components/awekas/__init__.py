"""The AWEKAS integration: weather data of your own AWEKAS weather station."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import AwekasCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.WEATHER]

type AwekasConfigEntry = ConfigEntry[AwekasCoordinator]


async def async_user_agent(hass: HomeAssistant) -> str:
    """Identifying User-Agent, so AWEKAS can see which client generates traffic."""
    integration = await async_get_integration(hass, DOMAIN)
    return f"HomeAssistant-AWEKAS/{integration.version} HomeAssistant/{HA_VERSION}"


async def async_setup_entry(hass: HomeAssistant, entry: AwekasConfigEntry) -> bool:
    """Set up AWEKAS from a config entry."""
    coordinator = AwekasCoordinator(hass, entry, await async_user_agent(hass))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AwekasConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: AwekasConfigEntry) -> None:
    """Reload the entry when the options (interval, language) change."""
    await hass.config_entries.async_reload(entry.entry_id)
