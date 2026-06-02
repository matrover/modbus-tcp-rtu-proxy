"""Config flow for Modbus TCP RTU Proxy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_INTER_REQUEST_DELAY_MS,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    CONF_LOG_LEVEL,
    CONF_MAX_CLIENTS,
    CONF_NAME,
    CONF_REQUEST_TIMEOUT,
    CONF_RTU_HOST,
    CONF_RTU_PORT,
    DEFAULT_INTER_REQUEST_DELAY_MS,
    DEFAULT_LISTEN_HOST,
    DEFAULT_LISTEN_PORT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_CLIENTS,
    DEFAULT_NAME,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RTU_PORT,
    DOMAIN,
    LOG_LEVELS,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_LISTEN_HOST, default=defaults.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST)): str,
            vol.Required(
                CONF_LISTEN_PORT,
                default=defaults.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(CONF_RTU_HOST, default=defaults.get(CONF_RTU_HOST, "")): str,
            vol.Required(
                CONF_RTU_PORT,
                default=defaults.get(CONF_RTU_PORT, DEFAULT_RTU_PORT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(
                CONF_REQUEST_TIMEOUT,
                default=defaults.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=60)),
            vol.Required(
                CONF_INTER_REQUEST_DELAY_MS,
                default=defaults.get(CONF_INTER_REQUEST_DELAY_MS, DEFAULT_INTER_REQUEST_DELAY_MS),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5000)),
            vol.Required(
                CONF_MAX_CLIENTS,
                default=defaults.get(CONF_MAX_CLIENTS, DEFAULT_MAX_CLIENTS),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
            vol.Required(CONF_LOG_LEVEL, default=defaults.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)): vol.In(LOG_LEVELS),
        }
    )


class ModbusTcpRtuProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Modbus TCP RTU Proxy."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input[CONF_RTU_HOST].strip():
                errors[CONF_RTU_HOST] = "rtu_host_required"
            else:
                unique_id = f"{user_input[CONF_LISTEN_HOST]}:{user_input[CONF_LISTEN_PORT]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return options flow handler."""
        return ModbusTcpRtuProxyOptionsFlow()


class ModbusTcpRtuProxyOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Modbus TCP RTU Proxy."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.FlowResult:
        """Manage proxy options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
