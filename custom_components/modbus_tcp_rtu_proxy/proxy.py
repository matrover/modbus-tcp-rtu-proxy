"""Modbus TCP to Modbus RTU-over-TCP proxy engine."""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
)

LOGGER = logging.getLogger(__name__)

MODBUS_EXCEPTION_INVALID_RESPONSE = 0x04
MODBUS_EXCEPTION_GATEWAY_TARGET_FAILED = 0x0B
WRITER_CLOSE_TIMEOUT = 2.0


def crc16_modbus(data: bytes) -> int:
    """Return the Modbus RTU CRC16 for a byte string."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(frame: bytes) -> bytes:
    """Append little-endian Modbus RTU CRC bytes to a frame."""
    crc = crc16_modbus(frame)
    return frame + bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def has_valid_crc(frame: bytes) -> bool:
    """Return True when a complete RTU frame has a valid CRC."""
    if len(frame) < 4:
        return False
    expected = crc16_modbus(frame[:-2])
    actual = frame[-2] | (frame[-1] << 8)
    return expected == actual


async def close_writer(writer: asyncio.StreamWriter) -> None:
    """Close a stream writer without hanging unload or tests."""
    writer.close()
    try:
        await asyncio.wait_for(writer.wait_closed(), timeout=WRITER_CLOSE_TIMEOUT)
    except (TimeoutError, OSError):
        pass


@dataclass(slots=True)
class ProxyConfig:
    """Runtime configuration for one proxy instance."""

    name: str = DEFAULT_NAME
    listen_host: str = DEFAULT_LISTEN_HOST
    listen_port: int = DEFAULT_LISTEN_PORT
    rtu_host: str = ""
    rtu_port: int = DEFAULT_RTU_PORT
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    inter_request_delay_ms: int = DEFAULT_INTER_REQUEST_DELAY_MS
    max_clients: int = DEFAULT_MAX_CLIENTS
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ProxyConfig":
        """Create config from Home Assistant config entry data/options."""
        return cls(
            name=str(data.get(CONF_NAME, DEFAULT_NAME)),
            listen_host=str(data.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST)),
            listen_port=int(data.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)),
            rtu_host=str(data[CONF_RTU_HOST]),
            rtu_port=int(data.get(CONF_RTU_PORT, DEFAULT_RTU_PORT)),
            request_timeout=float(data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)),
            inter_request_delay_ms=int(data.get(CONF_INTER_REQUEST_DELAY_MS, DEFAULT_INTER_REQUEST_DELAY_MS)),
            max_clients=int(data.get(CONF_MAX_CLIENTS, DEFAULT_MAX_CLIENTS)),
            log_level=str(data.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)),
        )


class RtuBridge:
    """Single serialized connection to a transparent TCP-to-RS485 adapter."""

    def __init__(self, config: ProxyConfig) -> None:
        self.config = config
        self._lock = asyncio.Lock()
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._last_request = 0.0

    async def close(self) -> None:
        """Close the adapter connection."""
        if self._writer is not None:
            await close_writer(self._writer)
        self._reader = None
        self._writer = None

    async def request(self, unit_id: int, pdu: bytes) -> bytes:
        """Send one Modbus PDU as RTU and return the response PDU."""
        async with self._lock:
            await self._connect()
            assert self._reader is not None
            assert self._writer is not None

            delay = self.config.inter_request_delay_ms / 1000
            elapsed = time.monotonic() - self._last_request
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

            await self._drain_stale_bytes()
            rtu_request = append_crc(bytes((unit_id,)) + pdu)
            LOGGER.debug("RTU request: %s", rtu_request.hex(" "))
            self._writer.write(rtu_request)
            await self._writer.drain()
            self._last_request = time.monotonic()

            try:
                response = await asyncio.wait_for(
                    self._read_rtu_response(pdu[0]),
                    timeout=self.config.request_timeout,
                )
            except Exception:
                await self.close()
                raise

            LOGGER.debug("RTU response: %s", response.hex(" "))
            if not has_valid_crc(response):
                raise ValueError(f"Invalid RTU CRC: {response.hex(' ')}")

            if response[0] != unit_id:
                raise ValueError(f"RTU unit id {response[0]} does not match request unit id {unit_id}")

            return response[1:-2]

    async def _connect(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return
        await self.close()
        LOGGER.info("Connecting to RTU adapter %s:%s", self.config.rtu_host, self.config.rtu_port)
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.config.rtu_host, self.config.rtu_port),
            timeout=self.config.request_timeout,
        )

    async def _drain_stale_bytes(self) -> None:
        if self._reader is None:
            return
        while True:
            try:
                data = await asyncio.wait_for(self._reader.read(256), timeout=0.02)
            except asyncio.TimeoutError:
                return
            if not data:
                await self.close()
                return
            LOGGER.debug("Dropped stale RTU bytes: %s", data.hex(" "))

    async def _read_rtu_response(self, request_function: int) -> bytes:
        assert self._reader is not None
        head = await self._reader.readexactly(2)
        response_function = head[1]

        if response_function & 0x80:
            return head + await self._reader.readexactly(3)

        if request_function in (1, 2, 3, 4):
            byte_count = await self._reader.readexactly(1)
            return head + byte_count + await self._reader.readexactly(byte_count[0] + 2)

        if request_function in (5, 6, 15, 16):
            return head + await self._reader.readexactly(6)

        chunks = [head]
        while True:
            try:
                data = await asyncio.wait_for(self._reader.read(256), timeout=0.05)
            except asyncio.TimeoutError:
                break
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks)


class ModbusTcpRtuProxy:
    """Modbus TCP server that forwards requests to an RTU bridge."""

    def __init__(self, config: ProxyConfig) -> None:
        self.config = config
        self.bridge = RtuBridge(config)
        self._client_semaphore = asyncio.Semaphore(config.max_clients)
        self._server: asyncio.AbstractServer | None = None
        self._client_writers: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        """Start the Modbus TCP listener."""
        self._server = await asyncio.start_server(
            self.handle_client,
            self.config.listen_host,
            self.config.listen_port,
        )
        sockets = ", ".join(str(sock.getsockname()) for sock in self._server.sockets or [])
        LOGGER.info("%s listening on %s", self.config.name, sockets)

    async def stop(self) -> None:
        """Stop the Modbus TCP listener and all active connections."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        for writer in list(self._client_writers):
            await close_writer(writer)

        await self.bridge.close()
        LOGGER.info("%s stopped", self.config.name)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle one Modbus TCP client."""
        peer = writer.get_extra_info("peername")
        self._client_writers.add(writer)
        async with self._client_semaphore:
            LOGGER.info("Client connected: %s", peer)
            try:
                while True:
                    mbap = await reader.readexactly(7)
                    transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", mbap)
                    if protocol_id != 0:
                        raise ValueError(f"Unsupported Modbus protocol id {protocol_id}")
                    if length < 2 or length > 254:
                        raise ValueError(f"Invalid Modbus TCP length {length}")

                    pdu = await reader.readexactly(length - 1)
                    LOGGER.debug("TCP request tx=%s unit=%s pdu=%s", transaction_id, unit_id, pdu.hex(" "))

                    response_pdu = await self._handle_pdu(unit_id, pdu, transaction_id)
                    response = struct.pack(">HHHB", transaction_id, 0, len(response_pdu) + 1, unit_id) + response_pdu
                    writer.write(response)
                    await writer.drain()
            except asyncio.IncompleteReadError:
                pass
            except Exception as exc:
                LOGGER.warning("Client %s disconnected after error: %s", peer, exc)
            finally:
                self._client_writers.discard(writer)
                await close_writer(writer)
                LOGGER.info("Client disconnected: %s", peer)

    async def _handle_pdu(self, unit_id: int, pdu: bytes, transaction_id: int) -> bytes:
        function = pdu[0]
        try:
            return await self.bridge.request(unit_id, pdu)
        except asyncio.TimeoutError:
            LOGGER.warning("RTU timeout for tx=%s function=%s", transaction_id, function)
            return bytes((function | 0x80, MODBUS_EXCEPTION_GATEWAY_TARGET_FAILED))
        except Exception as exc:
            LOGGER.warning("RTU error for tx=%s function=%s: %s", transaction_id, function, exc)
            return bytes((function | 0x80, MODBUS_EXCEPTION_INVALID_RESPONSE))
