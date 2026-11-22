"""Sensors of an AWEKAS weather station."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    EntityCategory,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AwekasConfigEntry
from .coordinator import AwekasCoordinator, AwekasData
from .entity import AwekasEntity, async_remove_stale_entities
from .util import (
    PRESSURE_TENDENCY,
    WIND_DIRECTIONS,
    pressure_tendency,
    to_datetime,
    to_float,
    to_text,
    wind_direction,
)

PARALLEL_UPDATES = 0


def _to_date(raw: Any) -> date | None:
    text = to_text(raw)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


@dataclass(frozen=True, kw_only=True)
class AwekasSensorEntityDescription(SensorEntityDescription):
    """Describes an AWEKAS sensor."""

    section: str  # section of the API response: current, 1h, day, station, ...
    field: str
    value_fn: Callable[[Any], StateType | datetime | date] = to_float


# ---------- helpers to keep the list readable ----------

TEMP = {
    "device_class": SensorDeviceClass.TEMPERATURE,
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
    "suggested_display_precision": 1,
}
HUM = {
    "device_class": SensorDeviceClass.HUMIDITY,
    "native_unit_of_measurement": PERCENTAGE,
    "suggested_display_precision": 0,
}
PRESS = {
    "device_class": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "native_unit_of_measurement": UnitOfPressure.HPA,
    "suggested_display_precision": 1,
}
WIND = {
    "device_class": SensorDeviceClass.WIND_SPEED,
    "native_unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "suggested_display_precision": 1,
}
WIND_DIR = {
    "device_class": SensorDeviceClass.WIND_DIRECTION,
    "native_unit_of_measurement": DEGREE,
    "suggested_display_precision": 0,
}
RAIN = {
    "device_class": SensorDeviceClass.PRECIPITATION,
    "native_unit_of_measurement": UnitOfPrecipitationDepth.MILLIMETERS,
    "suggested_display_precision": 1,
}
RAIN_RATE = {
    "device_class": SensorDeviceClass.PRECIPITATION_INTENSITY,
    "native_unit_of_measurement": UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    "suggested_display_precision": 1,
}
SOLAR = {
    "device_class": SensorDeviceClass.IRRADIANCE,
    "native_unit_of_measurement": UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    "suggested_display_precision": 0,
}
LUX = {
    "device_class": SensorDeviceClass.ILLUMINANCE,
    "native_unit_of_measurement": LIGHT_LUX,
    "suggested_display_precision": 0,
}
UV = {"native_unit_of_measurement": UV_INDEX, "suggested_display_precision": 1}
MEAS = {"state_class": SensorStateClass.MEASUREMENT}
TS = {
    "device_class": SensorDeviceClass.TIMESTAMP,
    "value_fn": to_datetime,
    "entity_registry_enabled_default": False,
}


def _sensor(key: str, section: str, field: str, **kwargs: Any) -> AwekasSensorEntityDescription:
    return AwekasSensorEntityDescription(
        key=key, translation_key=key, section=section, field=field, **kwargs
    )


def _current(field: str, *groups: dict[str, Any], **kwargs: Any) -> AwekasSensorEntityDescription:
    attrs: dict[str, Any] = {}
    for group in groups:
        attrs.update(group)
    attrs.update(kwargs)
    return _sensor(field, "current", field, **attrs)


SENSORS: list[AwekasSensorEntityDescription] = [
    # ---------- current values ----------
    _current("temperature", TEMP, MEAS),
    _current("dewpoint", TEMP, MEAS),
    _current("windchill", TEMP, MEAS),
    _current("wetbulbtemperature", TEMP, MEAS),
    _current("humidity", HUM, MEAS),
    _current("airpress_rel", PRESS, MEAS),
    _current(
        "tendency",
        device_class=SensorDeviceClass.ENUM,
        options=list(PRESSURE_TENDENCY.values()),
        value_fn=pressure_tendency,
    ),
    _current(
        "precipitation",
        RAIN,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    _sensor("precipitation_1h", "1h", "precipitation_1h", **RAIN, **MEAS),
    _current("rainrate", RAIN_RATE, MEAS),
    _current("windspeed", WIND, MEAS),
    _current("gustspeed", WIND, MEAS),
    _current(
        "winddirection", WIND_DIR, state_class=SensorStateClass.MEASUREMENT_ANGLE
    ),
    _sensor(
        "winddirection_text",
        "current",
        "winddirection",
        device_class=SensorDeviceClass.ENUM,
        options=WIND_DIRECTIONS,
        value_fn=wind_direction,
    ),
    _current("uv", UV, MEAS),
    _current("solar", SOLAR, MEAS),
    _current("brightness", LUX, MEAS),
    _current(
        "suntime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    _current(
        "snowheight",
        MEAS,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
    ),
    *(_current(f"temp{n}", TEMP, MEAS) for n in range(1, 5)),
    *(_current(f"humidity{n}", HUM, MEAS) for n in range(1, 5)),
    *(
        _current(
            f"soilmoisture{n}",
            MEAS,
            native_unit_of_measurement="cbar",
            suggested_display_precision=0,
        )
        for n in range(1, 5)
    ),
    *(
        _current(
            f"leafwetness{n}",
            MEAS,
            suggested_display_precision=0,
        )
        for n in range(1, 3)
    ),
    _current("indoortemperature", TEMP, MEAS),
    _current("indoorhumidity", HUM, MEAS),
    _current(
        "airquality_pm1",
        MEAS,
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    _current(
        "airquality_pm2",
        MEAS,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    _current(
        "airquality_pm10",
        MEAS,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
    ),
    _current(
        "datatimestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=to_datetime,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _sensor(
        "fetchdate",
        "root",
        "fetchdate",
        entity_category=EntityCategory.DIAGNOSTIC,
        **TS,
    ),
]

# ---------- daily minimum / maximum values ----------
DAY_MIN_MAX: list[tuple[str, dict[str, Any]]] = [
    ("temp", TEMP),
    ("dewpoint", TEMP),
    ("hum", HUM),
    ("airp_rel", PRESS),
    ("windspeed", WIND),
    ("gustspeed", WIND),
    ("intemp", TEMP),
    ("inhum", HUM),
]
for _key, _group in DAY_MIN_MAX:
    for _mm in ("min", "max"):
        SENSORS.append(
            _sensor(f"day_{_key}_{_mm}", "day", f"{_key}_{_mm}", **_group)
        )
        SENSORS.append(
            _sensor(f"day_{_key}_{_mm}_ts", "day", f"{_key}_{_mm}_ts", **TS)
        )

DAY_MAX: list[tuple[str, dict[str, Any], bool]] = [
    ("rainrate_max", RAIN_RATE, True),
    ("brightness_max", LUX, True),
    ("solar_max", SOLAR, True),
    ("uv_max", UV, True),
    ("precipitation_24h", RAIN, False),
    ("winddir_max", WIND_DIR, False),
    ("gustdir_max", WIND_DIR, False),
    ("airquality_pm1", {"device_class": SensorDeviceClass.PM1, "native_unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, "suggested_display_precision": 1}, False),
    ("airquality_pm2", {"device_class": SensorDeviceClass.PM25, "native_unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, "suggested_display_precision": 1}, False),
    ("airquality_pm10", {"device_class": SensorDeviceClass.PM10, "native_unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, "suggested_display_precision": 1}, False),
]  # fmt: skip
for _key, _group, _with_ts in DAY_MAX:
    SENSORS.append(_sensor(f"day_{_key}", "day", _key, **_group))
    if _with_ts:
        SENSORS.append(
            _sensor(f"day_{_key}_ts", "day", f"{_key}_ts", **TS)
        )

# ---------- station data (station.php, refreshed once a day) ----------
SENSORS.append(
    _sensor(
        "stationsweb_period",
        "stationsweb",
        "period",
        device_class=SensorDeviceClass.DATE,
        value_fn=_to_date,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
)


def should_create(description: AwekasSensorEntityDescription, data: AwekasData) -> bool:
    """AWEKAS delivers all fields; null means the station does not have this sensor."""
    return data.section(description.section).get(description.field) is not None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AwekasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AWEKAS sensors.

    Only sensors with a value are created. Sensors that start delivering values
    later are added automatically; sensors that are no longer delivered are
    removed when the integration starts.
    """
    coordinator = entry.runtime_data
    created: set[str] = set()

    @callback
    def _async_add_new() -> None:
        new = [
            description
            for description in SENSORS
            if description.key not in created and should_create(description, coordinator.data)
        ]
        if new:
            created.update(description.key for description in new)
            async_add_entities([AwekasSensor(coordinator, description) for description in new])

    _async_add_new()
    async_remove_stale_entities(
        hass, entry, "sensor", {description.key for description in SENSORS} - created
    )
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


class AwekasSensor(AwekasEntity, SensorEntity):
    """A sensor of an AWEKAS weather station."""

    entity_description: AwekasSensorEntityDescription

    def __init__(
        self, coordinator: AwekasCoordinator, description: AwekasSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime | date:
        """Return the value; None when the station has no value."""
        description = self.entity_description
        raw = self.coordinator.data.section(description.section).get(description.field)
        return description.value_fn(raw)
