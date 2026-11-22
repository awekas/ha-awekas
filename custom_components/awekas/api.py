"""Client for the AWEKAS Stations API V2.1.

Protection of the AWEKAS servers and of the user:
 - fixed HTTPS endpoint, no redirects, request timeout, response size limit
 - identifying User-Agent so AWEKAS can see which client generates traffic
 - the API key is sent only to api.awekas.at and never appears in exceptions or logs
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

import aiohttp
from yarl import URL

from .const import (
    API_BASE,
    ENDPOINT_CURRENT,
    ENDPOINT_STATION,
    MAX_RESPONSE_BYTES,
    REQUEST_TIMEOUT,
)
from .util import PERMANENT_ERRORS, api_error, parse_response


class AwekasError(Exception):
    """Base class for AWEKAS errors."""


class AwekasAuthError(AwekasError):
    """Permanent error: invalid key or AWEKAS Plus not active."""

    def __init__(self, message: str, reason: str) -> None:
        """Initialize."""
        super().__init__(message)
        self.reason = reason


class AwekasQuotaError(AwekasError):
    """The API quota is exceeded."""


class AwekasApiError(AwekasError):
    """The API reported another error."""


class AwekasConnectionError(AwekasError):
    """The server could not be reached or returned an invalid response."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        """Initialize."""
        super().__init__(message)
        self.retry_after = retry_after


class AwekasClient:
    """Minimal client for the AWEKAS Stations API."""

    def __init__(
        self, session: aiohttp.ClientSession, api_key: str, user_agent: str
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}

    async def async_get_current(self, language: str) -> dict[str, Any]:
        """Fetch current values, daily values and forecast."""
        return await self._request(ENDPOINT_CURRENT, {"lng": language})

    async def async_get_station(self) -> dict[str, Any]:
        """Fetch the station data."""
        return await self._request(ENDPOINT_STATION, {})

    async def _request(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        query = urlencode({"key": self._api_key, **params}, quote_via=quote, safe="")
        url = URL(f"{API_BASE}{endpoint}?{query}", encoded=True)
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    raise AwekasConnectionError(
                        f"HTTP {resp.status}", _retry_after(resp.headers.get("Retry-After"))
                    )
                length = resp.headers.get("Content-Length")
                if length and length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
                    raise AwekasConnectionError("response too large")
                body = await resp.content.read(MAX_RESPONSE_BYTES + 1)
        except AwekasConnectionError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            # only the exception type: aiohttp messages can contain the URL with the key
            raise AwekasConnectionError(type(err).__name__) from None

        if len(body) > MAX_RESPONSE_BYTES:
            raise AwekasConnectionError("response too large")
        try:
            data = parse_response(body)
        except ValueError:
            raise AwekasConnectionError("invalid JSON response") from None

        if error := api_error(data):
            key = error.lower()
            if key in PERMANENT_ERRORS:
                raise AwekasAuthError(error, PERMANENT_ERRORS[key])
            if "quota" in key:
                raise AwekasQuotaError(error)
            raise AwekasApiError(error)
        return data


def _retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header given in seconds."""
    if value and value.strip().isdigit():
        return float(value.strip())
    return None
