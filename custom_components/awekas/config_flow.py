"""Config flow for the AWEKAS integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import async_user_agent
from .api import (
    AwekasApiError,
    AwekasAuthError,
    AwekasClient,
    AwekasConnectionError,
    AwekasQuotaError,
)
from .const import (
    CONF_INTERVAL,
    CONF_LANGUAGE,
    DEFAULT_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_INTERVAL,
    MIN_INTERVAL,
    SUPPORTED_LANGUAGES,
)
from .coordinator import clamp_interval
from .util import InvalidKeyFormat, normalize_key, to_int, to_text

KEY_SCHEMA = vol.Schema(
    {vol.Required(CONF_API_KEY): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


class AwekasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AWEKAS."""

    VERSION = 1

    async def _async_validate(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, dict[str, Any] | None, dict[str, str]]:
        """Check the key with one request to station.php.

        Returns the cleaned key, the station data and the errors.
        """
        try:
            key = normalize_key(user_input[CONF_API_KEY])
        except InvalidKeyFormat:
            return None, None, {CONF_API_KEY: "invalid_key_format"}

        client = AwekasClient(
            async_get_clientsession(self.hass), key, await async_user_agent(self.hass)
        )
        try:
            data = await client.async_get_station()
        except AwekasAuthError as err:
            return key, None, {"base": err.reason}
        except AwekasQuotaError:
            return key, None, {"base": "quota_exceeded"}
        except (AwekasConnectionError, AwekasApiError):
            return key, None, {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error while validating the AWEKAS API key")
            return key, None, {"base": "unknown"}

        station = data.get("station") if isinstance(data.get("station"), dict) else {}
        if to_int(station.get("id")) is None:
            return key, None, {"base": "cannot_connect"}
        return key, data, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key, data, errors = await self._async_validate(user_input)
            if not errors and key and data:
                station = data["station"]
                await self.async_set_unique_id(str(to_int(station["id"])))
                self._abort_if_unique_id_configured()
                location = to_text(station.get("location"))
                return self.async_create_entry(
                    title=f"AWEKAS {location}" if location else "AWEKAS",
                    data={CONF_API_KEY: key},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=KEY_SCHEMA,
            errors=errors,
            description_placeholders={"url": "https://my.awekas.at"},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start re-authentication (invalid key)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            key, data, errors = await self._async_validate(user_input)
            if not errors and key and data:
                await self.async_set_unique_id(str(to_int(data["station"]["id"])))
                self._abort_if_unique_id_mismatch(reason="wrong_station")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=KEY_SCHEMA,
            errors=errors,
            description_placeholders={"url": "https://my.awekas.at"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AwekasOptionsFlow:
        """Return the options flow."""
        return AwekasOptionsFlow()


class AwekasOptionsFlow(OptionsFlow):
    """Request interval and language."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_INTERVAL: clamp_interval(user_input.get(CONF_INTERVAL)),
                    CONF_LANGUAGE: user_input.get(CONF_LANGUAGE, "system"),
                }
            )

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_INTERVAL,
                    default=clamp_interval(options.get(CONF_INTERVAL, DEFAULT_INTERVAL)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_INTERVAL,
                        max=MAX_INTERVAL,
                        step=10,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_LANGUAGE, default=options.get(CONF_LANGUAGE) or "system"
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=["system", *SUPPORTED_LANGUAGES],
                        translation_key="language",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
