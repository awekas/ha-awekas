"""Weather entity of an AWEKAS weather station."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sun import is_up
from homeassistant.util import dt as dt_util

from . import AwekasConfigEntry
from .const import ATTRIBUTION
from .coordinator import AwekasCoordinator
from .util import current_condition, forecast_condition, to_float, to_int, to_text

PARALLEL_UPDATES = 0
FORECAST_DAYS = 6


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AwekasConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AWEKAS weather entity."""
    async_add_entities([AwekasWeather(entry.runtime_data)])


class AwekasWeather(SingleCoordinatorWeatherEntity[AwekasCoordinator]):
    """Current weather and forecast of an AWEKAS weather station."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_attribution = ATTRIBUTION
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    def __init__(self, coordinator: AwekasCoordinator) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_weather"
        self._attr_device_info = coordinator.device_info
        # the forecast is only delivered with an active AWEKAS Stationsweb subscription
        if coordinator.data.section("forecast"):
            self._attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    @property
    def _current(self) -> dict:
        return self.coordinator.data.section("current")

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        today = self.coordinator.data.section("forecast").get("day0")
        condition = current_condition(
            self._current.get("condition"),
            self._current.get("itsraining"),
            self._current.get("temperature"),
            today.get("fc_code") if isinstance(today, dict) else None,
        )
        if condition == "sunny" and not is_up(self.hass):
            return "clear-night"
        return condition

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return to_float(self._current.get("temperature"))

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the wind chill."""
        return to_float(self._current.get("windchill"))

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return to_float(self._current.get("dewpoint"))

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return to_float(self._current.get("humidity"))

    @property
    def native_pressure(self) -> float | None:
        """Return the relative air pressure."""
        return to_float(self._current.get("airpress_rel"))

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return to_float(self._current.get("windspeed"))

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the gust speed."""
        return to_float(self._current.get("gustspeed"))

    @property
    def wind_bearing(self) -> float | None:
        """Return the wind direction in degrees."""
        return to_float(self._current.get("winddirection"))

    @property
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return to_float(self._current.get("uv"))

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast (today and the next five days)."""
        forecast = self.coordinator.data.section("forecast")
        if not forecast:
            return None
        tz = dt_util.get_time_zone(
            to_text(self.coordinator.data.section("station").get("timezone")) or ""
        ) or dt_util.get_default_time_zone()
        today = dt_util.now(tz).date()

        result: list[Forecast] = []
        for day in range(FORECAST_DAYS):
            values = forecast.get(f"day{day}")
            if not isinstance(values, dict):
                continue
            start = datetime.combine(today + timedelta(days=day), time.min, tzinfo=tz)
            result.append(
                Forecast(
                    datetime=start.isoformat(),
                    condition=forecast_condition(values.get("fc_code")),
                    native_temperature=to_float(values.get("fc_temp_max")),
                    native_templow=to_float(values.get("fc_temp_min")),
                    native_precipitation=to_float(values.get("fc_rainsum")),
                    precipitation_probability=to_int(values.get("fc_rain_possibility")),
                )
            )
        return result or None
