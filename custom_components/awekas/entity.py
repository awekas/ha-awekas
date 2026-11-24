"""Base entity for the AWEKAS integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
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
def async_registered_keys(
    hass: HomeAssistant, entry: AwekasConfigEntry, domain: str
) -> set[str]:
    """Keys of the entities this station already has in the entity registry.

    These entities are always created again, even if their value is currently
    null (e.g. station.php not reachable during startup). They then show
    unknown instead of disappearing, so entity IDs, names, areas and history
    are kept. The integration never removes registry entries.
    """
    prefix = f"{entry.unique_id}_"
    return {
        entity.unique_id.removeprefix(prefix)
        for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if entity.domain == domain and entity.unique_id.startswith(prefix)
    }
