"""Tests for setup, unload and the protection of the AWEKAS servers."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.awekas.api import (
    AwekasAuthError,
    AwekasConnectionError,
    AwekasQuotaError,
)
from custom_components.awekas.diagnostics import async_get_config_entry_diagnostics

from .conftest import TEST_KEY


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads, fetches station data once and unloads."""
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_client.async_get_current.call_count == 1
    assert mock_client.async_get_station.call_count == 1

    # the next update does not request station.php again (only once a day)
    await mock_config_entry.runtime_data.async_refresh()
    assert mock_client.async_get_current.call_count == 2
    assert mock_client.async_get_station.call_count == 1

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_minimum_interval(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The interval never goes below 60 s minus jitter."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={"interval": 5})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    interval = mock_config_entry.runtime_data.update_interval.total_seconds()
    assert 54 <= interval <= 66


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Connection problems during setup lead to a retry."""
    mock_client.async_get_current.side_effect = AwekasConnectionError("HTTP 503")
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_error_starts_reauth(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """An invalid key stops the integration and asks for a new key."""
    mock_client.async_get_current.side_effect = AwekasAuthError("invalid key", "invalid_key")
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_auth_error_while_running(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """AWEKAS Plus expiring while running stops polling and asks for a new key."""
    await _setup(hass, mock_config_entry)
    mock_client.async_get_current.side_effect = AwekasAuthError(
        "AWEKAS Plus not active", "plus_inactive"
    )
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert not mock_config_entry.runtime_data.last_update_success
    flows = hass.config_entries.flow.async_progress()
    assert flows and flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_backoff(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Errors increase the interval step by step, success resets it."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_client.async_get_current.side_effect = AwekasConnectionError("HTTP 503")
    await coordinator.async_refresh()
    assert 270 <= coordinator.update_interval.total_seconds() <= 330  # 5 min
    await coordinator.async_refresh()
    assert 540 <= coordinator.update_interval.total_seconds() <= 660  # 10 min

    mock_client.async_get_current.side_effect = AwekasConnectionError("HTTP 429", 1200)
    await coordinator.async_refresh()
    assert coordinator.update_interval.total_seconds() == 1200  # Retry-After

    mock_client.async_get_current.side_effect = AwekasQuotaError("quota exceeded")
    await coordinator.async_refresh()
    assert 810 <= coordinator.update_interval.total_seconds() <= 990  # 15 min

    mock_client.async_get_current.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert 54 <= coordinator.update_interval.total_seconds() <= 66


async def test_diagnostics_without_key(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Diagnostics never contain the API key or the exact position."""
    await _setup(hass, mock_config_entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    text = str(diagnostics)
    assert TEST_KEY not in text
    assert "47.8725" not in text
    assert diagnostics["current"]["current"]["temperature"] == 1.7


async def test_station_retry_after_failure(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A failed station request is not repeated on every poll."""
    mock_client.async_get_station.side_effect = AwekasConnectionError("HTTP 503")
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_client.async_get_station.call_count == 1

    await mock_config_entry.runtime_data.async_refresh()
    assert mock_client.async_get_station.call_count == 1  # next try only after 15 minutes


async def test_time_zone_resolved_in_coordinator(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The station time zone is resolved once by the coordinator."""
    await _setup(hass, mock_config_entry)
    assert str(mock_config_entry.runtime_data.time_zone) == "Europe/Vienna"
