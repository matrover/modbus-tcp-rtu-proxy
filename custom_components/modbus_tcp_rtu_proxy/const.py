"""Constants for Modbus TCP RTU Proxy."""

from __future__ import annotations

DOMAIN = "modbus_tcp_rtu_proxy"

CONF_NAME = "name"
CONF_INTER_REQUEST_DELAY_MS = "inter_request_delay_ms"
CONF_LISTEN_HOST = "listen_host"
CONF_LISTEN_PORT = "listen_port"
CONF_LOG_LEVEL = "log_level"
CONF_MAX_CLIENTS = "max_clients"
CONF_REQUEST_TIMEOUT = "request_timeout"
CONF_RTU_HOST = "rtu_host"
CONF_RTU_PORT = "rtu_port"

DEFAULT_INTER_REQUEST_DELAY_MS = 80
DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 1502
DEFAULT_LOG_LEVEL = "info"
DEFAULT_MAX_CLIENTS = 4
DEFAULT_NAME = "Modbus TCP RTU Proxy"
DEFAULT_REQUEST_TIMEOUT = 3.0
DEFAULT_RTU_PORT = 8899

LOG_LEVELS = ("debug", "info", "warning", "error")
