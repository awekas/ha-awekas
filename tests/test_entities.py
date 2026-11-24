"""Tests for the AWEKAS entities, based on real data of the AWEKAS test station."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.awekas.api import AwekasConnectionError

from .conftest import load_fixture


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, "awekas", f"2_{key}")


async def test_sensors(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Sensors show the values of the test station."""
    await _setup(hass, mock_config_entry)

    numbers = {
        "temperature": 1.7,
        "humidity": 87,
        "airpress_rel": 1010.5,
        "winddirection": 319,
        "temp1": 8.3,
        "soilmoisture1": 17,
        "indoortemperature": 24.8,
        "airquality_pm2": 18.8,
        "day_temp_min": -0.8,
    }
    for key, value in numbers.items():
        entity_id = _entity_id(hass, "sensor", key)
        assert entity_id, key
        assert float(hass.states.get(entity_id).state) == value, key

    texts = {
        "tendency": "rising_fast",
        "winddirection_text": "nw",
        "stationsweb_period": "2030-12-11",
    }
    for key, value in texts.items():
        entity_id = _entity_id(hass, "sensor", key)
        assert entity_id, key
        assert hass.states.get(entity_id).state == value, key


    assert hass.states.get(_entity_id(hass, "binary_sensor", "itsraining")).state == "off"
    assert hass.states.get(_entity_id(hass, "binary_sensor", "awekasplus")).state == "on"


async def test_only_existing_sensors(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Sensors without a value (null) do not exist at the station and are not created."""
    await _setup(hass, mock_config_entry)
    for key in (
        "temp3", "temp4", "humidity1", "humidity2", "soilmoisture2",
        "leafwetness2", "brightness", "snowheight", "day_brightness_max",
    ):  # fmt: skip
        assert _entity_id(hass, "sensor", key) is None, key


async def test_new_sensor_is_added(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A sensor that starts delivering values is added without a restart."""
    await _setup(hass, mock_config_entry)
    assert _entity_id(hass, "sensor", "humidity1") is None

    current = load_fixture("current.json")
    current["current"]["humidity1"] = 55
    mock_client.async_get_current.return_value = current
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    entity_id = _entity_id(hass, "sensor", "humidity1")
    assert entity_id
    assert float(hass.states.get(entity_id).state) == 55


async def test_registered_sensor_is_kept(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A sensor that existed before is kept (unknown) while its value is null."""
    mock_config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor", "awekas", "2_humidity1", config_entry=mock_config_entry
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = _entity_id(hass, "sensor", "humidity1")
    assert entity_id
    assert hass.states.get(entity_id).state == "unknown"


async def test_station_entities_survive_failed_station_request(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """station.php failing during startup does not remove the station entities."""
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(hass, "binary_sensor", "awekasplus")
    assert hass.states.get(entity_id).state == "on"
    registry_id = er.async_get(hass).async_get(entity_id).id

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_client.async_get_station.side_effect = AwekasConnectionError("HTTP 503")
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # same registry entry (entity ID, name, area, history kept), value unknown for now
    assert er.async_get(hass).async_get(entity_id).id == registry_id
    assert hass.states.get(entity_id).state == "unknown"


async def test_timestamp_sensors_disabled_by_default(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The many time-of-min/max sensors exist but are disabled by default."""
    await _setup(hass, mock_config_entry)
    entry = er.async_get(hass).async_get(_entity_id(hass, "sensor", "day_temp_min_ts"))
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_weather(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The weather entity shows current values and the 6-day forecast."""
    await _setup(hass, mock_config_entry)
    entity_id = _entity_id(hass, "weather", "weather")
    state = hass.states.get(entity_id)
    # condition 0 = "no report", dry; forecast "light rain" -> cloudy
    assert state.state == "cloudy"
    assert state.attributes["temperature"] == 1.7
    assert state.attributes["humidity"] == 87

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": entity_id, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    forecast = response[entity_id]["forecast"]
    assert len(forecast) == 6
    assert forecast[0]["condition"] == "rainy"
    # Home Assistant rounds forecast temperatures to tenths
    assert forecast[0]["temperature"] == 4.1
    assert forecast[0]["templow"] == -0.6
    assert forecast[0]["precipitation_probability"] == 63
    assert forecast[2]["condition"] == "sunny"
    assert forecast[4]["condition"] == "snowy"


async def test_weather_condition(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A reported condition code is mapped to a Home Assistant condition."""
    current = load_fixture("current.json")
    current["current"]["condition"] = 19
    mock_client.async_get_current.return_value = current
    await _setup(hass, mock_config_entry)
    assert hass.states.get(_entity_id(hass, "weather", "weather")).state == "lightning-rainy"


async def test_weather_condition_raining(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Without a condition code, measured precipitation is shown."""
    current = load_fixture("current.json")
    current["current"]["itsraining"] = True
    current["current"]["temperature"] = 0.2
    mock_client.async_get_current.return_value = current
    await _setup(hass, mock_config_entry)
    assert hass.states.get(_entity_id(hass, "weather", "weather")).state == "snowy"


async def test_weather_without_forecast(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Without Stationsweb there is no forecast and the condition stays unknown."""
    current = load_fixture("current.json")
    del current["forecast"]
    mock_client.async_get_current.return_value = current
    await _setup(hass, mock_config_entry)
    assert hass.states.get(_entity_id(hass, "weather", "weather")).state == "unknown"
