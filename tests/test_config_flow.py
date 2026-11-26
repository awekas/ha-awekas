"""Tests for the AWEKAS config flow."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.awekas.api import (
    AwekasAuthError,
    AwekasConnectionError,
    AwekasQuotaError,
)
from custom_components.awekas.const import CONF_INTERVAL, CONF_LANGUAGE, DOMAIN

from .conftest import load_fixture


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A URL-encoded key is accepted, decoded and the station id becomes the unique id."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: " dGVzdGtleTEy%2BMzQ%3D "}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AWEKAS Micheldorf"
    assert result["data"] == {CONF_API_KEY: "dGVzdGtleTEy+MzQ="}
    assert result["result"].unique_id == "2"


async def test_invalid_key_format(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A key with an invalid format is rejected without a request."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "short"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_key_format"}
    mock_client.async_get_station.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AwekasAuthError("invalid key", "invalid_key"), "invalid_key"),
        (AwekasQuotaError("quota exceeded"), "quota_exceeded"),
        (AwekasConnectionError("HTTP 503"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, mock_client: MagicMock, side_effect: Exception, error: str
) -> None:
    """Errors are shown and the flow recovers."""
    mock_client.async_get_station.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "dGVzdGtleTEyMzQ="}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.async_get_station.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "dGVzdGtleTEyMzQ="}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The same station cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "dGVzdGtleTEyMzQ="}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A new key can be entered after the old one became invalid."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bmV1ZXJLZXkxMjM0NQ=="}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "bmV1ZXJLZXkxMjM0NQ=="


async def test_reauth_wrong_station(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The key of another station is rejected during re-authentication."""
    station = load_fixture("station.json")
    station["station"]["id"] = 99
    mock_client.async_get_station.return_value = station
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bmV1ZXJLZXkxMjM0NQ=="}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_station"


async def test_options(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Interval and language can be changed."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_INTERVAL: 120, CONF_LANGUAGE: "en"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_INTERVAL: 120, CONF_LANGUAGE: "en"}
    mock_client.async_get_current.assert_called_with("en")
