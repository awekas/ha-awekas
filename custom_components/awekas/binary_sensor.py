"""Binary sensors of an AWEKAS weather station."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AwekasConfigEntry
from .coordinator import AwekasCoordinator
from .entity import AwekasEntity, async_remove_stale_entities
from .util import to_bool

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AwekasBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an AWEKAS binary sensor."""

    section: str
    field: str


BINARY_SENSORS: list[AwekasBinarySensorEntityDescription] = [
    AwekasBinarySensorEntityDescription(
        key="itsraining",
        translation_key="itsraining",
        section="current",
        field="itsraining",
    ),
    AwekasBinarySensorEntityDescription(
        key="awekasplus",
        translation_key="awekasplus",
        entity_category=EntityCategory.DIAGNOSTIC,
        section="station",
        field="AWEKASplus",
    ),
    AwekasBinarySensorEntityDescription(
        key="stationsweb",
        translation_key="stationsweb",
        entity_category=EntityCategory.DIAGNOSTIC,
        section="stationsweb",
        field="enabled",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AwekasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AWEKAS binary sensors (only those with a value, see sensor.py)."""
    coordinator = entry.runtime_data
    created: set[str] = set()

    @callback
    def _async_add_new() -> None:
        new = [
            description
            for description in BINARY_SENSORS
            if description.key not in created
            and coordinator.data.section(description.section).get(description.field) is not None
        ]
        if new:
            created.update(description.key for description in new)
            async_add_entities([AwekasBinarySensor(coordinator, description) for description in new])

    _async_add_new()
    async_remove_stale_entities(
        hass, entry, "binary_sensor", {d.key for d in BINARY_SENSORS} - created
    )
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


class AwekasBinarySensor(AwekasEntity, BinarySensorEntity):
    """A binary sensor of an AWEKAS weather station."""

    entity_description: AwekasBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AwekasCoordinator,
        description: AwekasBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        description = self.entity_description
        return to_bool(self.coordinator.data.section(description.section).get(description.field))
