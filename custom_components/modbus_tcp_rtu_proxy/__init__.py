"""Home Assistant integration for Modbus TCP RTU Proxy."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN
from .proxy import ModbusTcpRtuProxy, ProxyConfig

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Modbus TCP RTU Proxy instance."""
    config = ProxyConfig.from_mapping({**entry.data, **entry.options})
    logging.getLogger(f"{__name__}.proxy").setLevel(config.log_level.upper())

    proxy = ModbusTcpRtuProxy(config)
    try:
        await proxy.start()
    except OSError as exc:
        raise ConfigEntryError(f"Could not start Modbus TCP listener: {exc}") from exc

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = proxy
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Modbus TCP RTU Proxy instance."""
    proxy: ModbusTcpRtuProxy | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if proxy is not None:
        await proxy.stop()

    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the proxy when options change."""
    await hass.config_entries.async_reload(entry.entry_id)

