import asyncio
import importlib.util
import struct
import sys
import types
import unittest
from pathlib import Path


COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "modbus_tcp_rtu_proxy"
PACKAGE_NAME = "modbus_tcp_rtu_proxy_test"

package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(COMPONENT_DIR)]
sys.modules[PACKAGE_NAME] = package

for module_name in ("const", "proxy"):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE_NAME}.{module_name}",
        COMPONENT_DIR / f"{module_name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{PACKAGE_NAME}.{module_name}"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)

proxy_module = sys.modules[f"{PACKAGE_NAME}.proxy"]
ModbusTcpRtuProxy = proxy_module.ModbusTcpRtuProxy
ProxyConfig = proxy_module.ProxyConfig
append_crc = proxy_module.append_crc


class ModbusTcpRtuProxyTest(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        if hasattr(self, "proxy"):
            await self.proxy.stop()
        if hasattr(self, "tcp_server"):
            self.tcp_server.close()
            await self.tcp_server.wait_closed()
        if hasattr(self, "rtu_server"):
            self.rtu_server.close()
            await self.rtu_server.wait_closed()

    async def _start_proxy(self, rtu_handler, *, timeout=0.5):
        self.rtu_requests = []
        self.rtu_server = await asyncio.start_server(rtu_handler, "127.0.0.1", 0)
        rtu_port = self.rtu_server.sockets[0].getsockname()[1]

        config = ProxyConfig(
            name="test",
            listen_host="127.0.0.1",
            listen_port=0,
            rtu_host="127.0.0.1",
            rtu_port=rtu_port,
            request_timeout=timeout,
            inter_request_delay_ms=0,
            log_level="error",
        )
        self.proxy = ModbusTcpRtuProxy(config)
        self.tcp_server = await asyncio.start_server(self.proxy.handle_client, "127.0.0.1", 0)
        self.proxy_port = self.tcp_server.sockets[0].getsockname()[1]

    async def _send_tcp_request(self, pdu):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.proxy_port)
        transaction_id = 42
        unit_id = 1
        request = struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, unit_id) + pdu
        writer.write(request)
        await writer.drain()
        response_mbap = await reader.readexactly(7)
        _tx, _protocol, length, _unit = struct.unpack(">HHHB", response_mbap)
        response_pdu = await reader.readexactly(length - 1)
        writer.close()
        return response_mbap + response_pdu

    async def test_converts_modbus_tcp_read_request_to_rtu_and_back(self):
        async def handle_rtu(reader, writer):
            request = await reader.readexactly(8)
            self.rtu_requests.append(request)
            writer.write(append_crc(bytes.fromhex("01 04 02 12 34")))
            await writer.drain()
            writer.close()

        await self._start_proxy(handle_rtu)

        pdu = bytes.fromhex("04 80 e8 00 01")
        response = await self._send_tcp_request(pdu)

        self.assertEqual(self.rtu_requests, [append_crc(bytes((1,)) + pdu)])
        self.assertEqual(response, struct.pack(">HHHB", 42, 0, 5, 1) + bytes.fromhex("04 02 12 34"))

    async def test_write_single_register_response(self):
        async def handle_rtu(reader, writer):
            request = await reader.readexactly(8)
            self.rtu_requests.append(request)
            writer.write(append_crc(bytes.fromhex("01 06 00 10 00 01")))
            await writer.drain()
            writer.close()

        await self._start_proxy(handle_rtu)

        pdu = bytes.fromhex("06 00 10 00 01")
        response = await self._send_tcp_request(pdu)

        self.assertEqual(self.rtu_requests, [append_crc(bytes((1,)) + pdu)])
        self.assertEqual(response, struct.pack(">HHHB", 42, 0, 6, 1) + pdu)

    async def test_invalid_crc_returns_exception_04(self):
        async def handle_rtu(reader, writer):
            await reader.readexactly(8)
            writer.write(bytes.fromhex("01 04 02 12 34 00 00"))
            await writer.drain()
            writer.close()

        await self._start_proxy(handle_rtu)

        response = await self._send_tcp_request(bytes.fromhex("04 80 e8 00 01"))

        self.assertEqual(response, struct.pack(">HHHB", 42, 0, 3, 1) + bytes.fromhex("84 04"))

    async def test_timeout_returns_exception_0b(self):
        async def handle_rtu(reader, writer):
            await reader.readexactly(8)
            await asyncio.sleep(2)
            writer.close()

        await self._start_proxy(handle_rtu, timeout=0.1)

        response = await self._send_tcp_request(bytes.fromhex("04 80 e8 00 01"))

        self.assertEqual(response, struct.pack(">HHHB", 42, 0, 3, 1) + bytes.fromhex("84 0b"))


if __name__ == "__main__":
    unittest.main()
