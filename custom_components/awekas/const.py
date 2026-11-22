"""Constants for the AWEKAS integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "awekas"
LOGGER = logging.getLogger(__package__)

ATTRIBUTION: Final = "Data provided by AWEKAS (www.awekas.at)"
MANUFACTURER: Final = "AWEKAS"

API_BASE: Final = "https://api.awekas.at/"
ENDPOINT_CURRENT: Final = "current.php"
ENDPOINT_STATION: Final = "station.php"

CONF_INTERVAL: Final = "interval"
CONF_LANGUAGE: Final = "language"

# Request interval in seconds. The lower limit cannot be configured below 60 s.
# AWEKAS limits (API description V2.1): 240 requests per hour, 2 requests per second.
# With the minimum interval the integration uses at most about 61 requests per hour.
MIN_INTERVAL: Final = 60
DEFAULT_INTERVAL: Final = 60
MAX_INTERVAL: Final = 3600

REQUEST_TIMEOUT: Final = 15  # seconds
MAX_RESPONSE_BYTES: Final = 512 * 1024
MAX_STRING_LENGTH: Final = 1024
JITTER: Final = 0.1  # +/- 10 %

BACKOFF_START: Final = 5 * 60  # seconds
BACKOFF_MAX: Final = 60 * 60
QUOTA_WAIT: Final = 15 * 60
STATION_REFRESH: Final = 24 * 60 * 60  # station data rarely changes
STATION_REQUEST_DELAY: Final = 1.5  # AWEKAS allows max. 2 requests per second

SUPPORTED_LANGUAGES: Final = ["de", "en", "es", "it", "fr", "nl", "pl"]
