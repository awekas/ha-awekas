"""Fixtures for the AWEKAS tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.awekas.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
TEST_KEY = "dGVzdGtleTEyMzQ1Njc4OTA="


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture (real responses of the AWEKAS test station)."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in all tests."""


@pytest.fixture(autouse=True)
def no_station_delay() -> Generator[None]:
    """Skip the pause between the two API requests."""
    with patch("custom_components.awekas.coordinator.STATION_REQUEST_DELAY", 0):
        yield


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the AWEKAS API client used by the coordinator and the config flow."""
    with (
        patch("custom_components.awekas.coordinator.AwekasClient", autospec=True) as cls,
        patch("custom_components.awekas.config_flow.AwekasClient", new=cls),
    ):
        client = cls.return_value
        client.async_get_current = AsyncMock(return_value=load_fixture("current.json"))
        client.async_get_station = AsyncMock(return_value=load_fixture("station.json"))
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry for the test station."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="AWEKAS Micheldorf",
        unique_id="2",
        data={CONF_API_KEY: TEST_KEY},
        options={},
    )
