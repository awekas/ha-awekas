"""Base entity for the AWEKAS integration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AwekasCoordinator

if TYPE_CHECKING:
    from . import AwekasConfigEntry


class AwekasEntity(CoordinatorEntity[AwekasCoordinator]):
    """Entity of an AWEKAS weather station."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: AwekasCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{key}"
        self._attr_device_info = coordinator.device_info


@callback
def async_remove_stale_entities(
    hass: HomeAssistant, entry: AwekasConfigEntry, domain: str, keys: Iterable[str]
) -> None:
    """Remove entities of sensors the station no longer delivers (value null)."""
    registry = er.async_get(hass)
    for key in keys:
        entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{entry.unique_id}_{key}")
        if entity_id:
            registry.async_remove(entity_id)
