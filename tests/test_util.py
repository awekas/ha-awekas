"""Tests for the pure helper functions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.awekas.util import (
    InvalidKeyFormat,
    api_error,
    awekas_condition,
    current_condition,
    forecast_condition,
    normalize_key,
    parse_response,
    pressure_tendency,
    to_bool,
    to_datetime,
    to_float,
    wind_direction,
)


def test_normalize_key() -> None:
    """Keys are trimmed and URL-decoded."""
    assert normalize_key("  abcdEFGH12+/==  ") == "abcdEFGH12+/=="
    assert normalize_key("abcdEFGH12%2B%2F%3D%3D") == "abcdEFGH12+/=="
    for bad in ("", "short", "abc def ghi", "abcdefgh<script>", "x" * 300):
        with pytest.raises(InvalidKeyFormat):
            normalize_key(bad)


def test_parse_response() -> None:
    """Only JSON objects are accepted."""
    assert parse_response(b'{"error": null}') == {"error": None}
    for bad in (b"[1, 2]", b"<html>", b'"text"'):
        with pytest.raises(ValueError):
            parse_response(bad)


def test_api_error() -> None:
    """The error field is evaluated."""
    assert api_error({"error": None}) is None
    assert api_error({"error": ""}) is None
    assert api_error({}) is None
    assert api_error({"error": "invalid key"}) == "invalid key"
    assert len(api_error({"error": "x" * 5000})) == 1024


def test_conversions() -> None:
    """API values are converted robustly."""
    assert to_float(1.7) == 1.7
    assert to_float("1,7") == 1.7
    assert to_float("-") is None
    assert to_float("") is None
    assert to_float(None) is None
    assert to_float(True) is None
    assert to_float("nan") is None
    assert to_float("abc") is None
    assert to_bool(1) is True
    assert to_bool("0") is False
    assert to_bool(None) is None
    assert to_datetime(1795381680) == datetime(2026, 11, 22, 21, 8, tzinfo=UTC)
    assert to_datetime(1795381680000) == datetime(2026, 11, 22, 21, 8, tzinfo=UTC)
    assert to_datetime(0) is None


def test_wind_and_tendency() -> None:
    """Compass directions and pressure tendency."""
    assert wind_direction(0) == "n"
    assert wind_direction(319) == "nw"
    assert wind_direction(360) == "n"
    assert wind_direction(-1) is None
    assert wind_direction(None) is None
    assert pressure_tendency(2) == "rising_fast"
    assert pressure_tendency(-1) == "falling"
    assert pressure_tendency(7) is None


def test_conditions() -> None:
    """Condition codes are mapped to Home Assistant weather conditions."""
    assert awekas_condition(0) is None
    assert awekas_condition(0, raining=True) == "rainy"
    assert awekas_condition(3) == "partlycloudy"
    assert awekas_condition(19) == "lightning-rainy"
    assert awekas_condition(99) is None
    assert forecast_condition(1000) == "sunny"
    assert forecast_condition(1183) == "rainy"
    assert forecast_condition(1219) == "snowy"
    assert forecast_condition(1255) == "snowy"
    assert forecast_condition(None) is None


def test_current_condition() -> None:
    """Fallbacks when the station reports no condition (code 0)."""
    # reported condition code wins
    assert current_condition(3, False, 5, 1183) == "partlycloudy"
    # station measures rain / snow
    assert current_condition(0, True, 5, 1000) == "rainy"
    assert current_condition(0, True, 0.5, 1000) == "snowy"
    # today's forecast, precipitation replaced by cloudy while it is dry
    assert current_condition(0, False, 1.7, 1183) == "cloudy"
    assert current_condition(0, False, 1.7, 1255) == "cloudy"
    assert current_condition(0, False, 1.7, 1003) == "partlycloudy"
    assert current_condition(0, False, 1.7, 1000) == "sunny"
    # no forecast (no Stationsweb)
    assert current_condition(0, False, 1.7, None) is None
