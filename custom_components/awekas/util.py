"""Pure helper functions for the AWEKAS integration.

This module has no dependency on Home Assistant or aiohttp so that it can be
tested in isolation.
"""

from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

from .const import MAX_STRING_LENGTH

KEY_PATTERN = re.compile(r"^[A-Za-z0-9+/=_-]{8,256}$")

# errors after which polling is stopped until the user enters a new key
PERMANENT_ERRORS: dict[str, str] = {
    "invalid key": "invalid_key",
}

WIND_DIRECTIONS = [
    "n", "nne", "ne", "ene", "e", "ese", "se", "sse",
    "s", "ssw", "sw", "wsw", "w", "wnw", "nw", "nnw",
]  # fmt: skip

PRESSURE_TENDENCY = {
    -2: "falling_fast",
    -1: "falling",
    0: "steady",
    1: "rising",
    2: "rising_fast",
}

# AWEKAS weather condition codes (API description, table 4) -> HA weather conditions
AWEKAS_CONDITIONS: dict[int, str] = {
    1: "sunny",  # clear
    2: "sunny",  # sunny sky
    3: "partlycloudy",
    4: "cloudy",
    5: "cloudy",  # heavy cloudy
    6: "cloudy",  # overcast sky
    7: "fog",
    8: "rainy",  # rain showers
    9: "pouring",  # heavy rain showers
    10: "rainy",  # light rain
    11: "rainy",
    12: "pouring",  # heavy rain
    13: "snowy",  # light snow
    14: "snowy",
    15: "snowy",  # light snow showers
    16: "snowy",  # snow showers
    17: "snowy-rainy",  # sleet
    18: "hail",
    19: "lightning-rainy",  # thunderstorm
    20: "windy",  # storm
    21: "snowy-rainy",  # freezing rain
    23: "rainy",  # drizzle
    24: "snowy",  # heavy snow
    25: "snowy",  # heavy snow showers
    31: "windy",  # storm > 8 Bft warning
    32: "pouring",  # heavy rain warning
    33: "fog",  # heavy fog warning
    34: "exceptional",  # extreme heat warning
    35: "exceptional",  # extreme cold warning
    36: "exceptional",  # glaze warning
    37: "snowy",  # heavy snowfall warning
    38: "snowy",  # snowdrift warning
    39: "windy",  # squalls warning
    40: "exceptional",  # hurricane/tornado warning
    41: "rainy",  # constant rain warning
    42: "pouring",  # flooding warning
    43: "snowy-rainy",  # sleet warning
    44: "hail",  # hail warning
}

# Forecast condition codes (fc_code) -> HA weather conditions
FORECAST_CONDITIONS: dict[int, str] = {
    1000: "sunny",
    1003: "partlycloudy",
    1006: "cloudy",
    1009: "cloudy",
    1030: "fog",
    1063: "rainy",
    1066: "snowy",
    1069: "snowy-rainy",
    1072: "snowy-rainy",
    1087: "lightning",
    1114: "snowy",
    1117: "snowy",
    1135: "fog",
    1147: "fog",
    1150: "rainy",
    1153: "rainy",
    1168: "snowy-rainy",
    1171: "snowy-rainy",
    1180: "rainy",
    1183: "rainy",
    1186: "rainy",
    1189: "rainy",
    1192: "pouring",
    1195: "pouring",
    1198: "snowy-rainy",
    1201: "snowy-rainy",
    1204: "snowy-rainy",
    1207: "snowy-rainy",
    1210: "snowy",
    1213: "snowy",
    1216: "snowy",
    1219: "snowy",
    1222: "snowy",
    1225: "snowy",
    1237: "hail",
    1240: "rainy",
    1243: "pouring",
    1246: "pouring",
    1249: "snowy-rainy",
    1252: "snowy-rainy",
    1255: "snowy",
    1258: "snowy",
    1261: "hail",
    1264: "hail",
    1273: "lightning-rainy",
    1276: "lightning-rainy",
    1279: "snowy",
    1282: "snowy",
}


class InvalidKeyFormat(ValueError):
    """The entered API key does not look like an AWEKAS key."""


def normalize_key(raw: str) -> str:
    """Clean up an entered API key.

    The key is base64; accept it also when it was copied URL-encoded (%2B, %2F, %3D).
    """
    key = (raw or "").strip()
    if re.search(r"%[0-9a-fA-F]{2}", key):
        key = unquote(key)
    if not KEY_PATTERN.fullmatch(key):
        raise InvalidKeyFormat
    return key


def parse_response(body: bytes) -> dict[str, Any]:
    """Parse a JSON response body. Raises ValueError on invalid content."""
    data = json.loads(body.decode("utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise ValueError("unexpected response format")
    return data


def api_error(data: dict[str, Any]) -> str | None:
    """Return the error text reported by the API, or None."""
    error = data.get("error")
    if error is None or error is False or error == "":
        return None
    text = str(error).strip()
    return text[:MAX_STRING_LENGTH] if text else None


def to_float(raw: Any) -> float | None:
    """Convert an API value to a number. None if the station has no value."""
    if raw is None or isinstance(raw, (bool, dict, list)):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip().replace(",", ".")
        if text in ("", "-"):
            return None
        try:
            value = float(text)
        except ValueError:
            return None
    return value if math.isfinite(value) else None


def to_int(raw: Any) -> int | None:
    """Convert an API value to an integer."""
    value = to_float(raw)
    return None if value is None else round(value)


def to_bool(raw: Any) -> bool | None:
    """Convert an API value to a boolean."""
    if isinstance(raw, bool):
        return raw
    if raw in (1, "1", "true"):
        return True
    if raw in (0, "0", "false"):
        return False
    return None


def to_text(raw: Any) -> str | None:
    """Convert an API value to a (length limited) string."""
    if raw is None or isinstance(raw, (dict, list)):
        return None
    text = str(raw).strip()
    return text[:MAX_STRING_LENGTH] if text else None


def to_datetime(raw: Any) -> datetime | None:
    """Convert a unix timestamp (seconds, or milliseconds) to an aware datetime."""
    value = to_float(raw)
    if value is None or value <= 0:
        return None
    if value >= 1e11:  # milliseconds
        value /= 1000
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def wind_direction(raw: Any) -> str | None:
    """Convert degrees to one of 16 compass directions."""
    deg = to_float(raw)
    if deg is None or deg < 0 or deg > 360:
        return None
    return WIND_DIRECTIONS[round(deg / 22.5) % 16]


def pressure_tendency(raw: Any) -> str | None:
    """Convert the pressure tendency code to an option key."""
    code = to_int(raw)
    return None if code is None else PRESSURE_TENDENCY.get(code)


def awekas_condition(code: Any, raining: Any = None) -> str | None:
    """Map the current AWEKAS condition code to a HA weather condition."""
    value = to_int(code)
    if value and value in AWEKAS_CONDITIONS:
        return AWEKAS_CONDITIONS[value]
    if to_bool(raining):
        return "rainy"
    return None


def forecast_condition(code: Any) -> str | None:
    """Map a forecast condition code to a HA weather condition."""
    value = to_int(code)
    return None if value is None else FORECAST_CONDITIONS.get(value)


# conditions that mean precipitation - not shown when the station measures none
PRECIPITATION_CONDITIONS = {
    "rainy",
    "pouring",
    "snowy",
    "snowy-rainy",
    "lightning-rainy",
    "hail",
    "lightning",
}
SNOW_TEMPERATURE = 1.0  # °C, at or below: precipitation is shown as snow


def current_condition(
    code: Any, raining: Any, temperature: Any, forecast_today: Any
) -> str | None:
    """Current condition of the station.

    1. condition code reported by the station (if not 0 = "no report")
    2. the station measures precipitation: rain, or snow at about 0 °C and below
    3. today's forecast; precipitation is replaced by "cloudy" because the
       station measures none
    4. unknown (no forecast without AWEKAS Stationsweb)
    """
    value = to_int(code)
    if value and value in AWEKAS_CONDITIONS:
        return AWEKAS_CONDITIONS[value]
    if to_bool(raining):
        temp = to_float(temperature)
        return "snowy" if temp is not None and temp <= SNOW_TEMPERATURE else "rainy"
    condition = forecast_condition(forecast_today)
    if condition in PRECIPITATION_CONDITIONS:
        return "cloudy"
    return condition
