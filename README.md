# Modbus TCP RTU Proxy

A Home Assistant custom integration that exposes a Modbus TCP listener and forwards requests to a transparent TCP-to-RS485 adapter as Modbus RTU frames.

[![Open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=matrover&repository=modbus-tcp-rtu-proxy&category=integration)
[![Add this integration to Home Assistant.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=modbus_tcp_rtu_proxy)

Use this when a device expects Modbus TCP, but your RS485 adapter only provides a raw TCP serial stream.

```text
Modbus TCP client -> Home Assistant:1502 -> proxy -> adapter:8899 -> RS485 device
```

## Installation With HACS

1. In HACS, add this repository as a custom repository with category `Integration`.
2. Download `Modbus TCP RTU Proxy`.
3. Restart Home Assistant.
4. Add the integration from Settings -> Devices & services.

HACS requires a public GitHub repository for normal installation.

## Configuration

Default values:

| Option | Default | Description |
| --- | --- | --- |
| Name | Modbus TCP RTU Proxy | Instance name |
| Listen host | `0.0.0.0` | Address Home Assistant listens on |
| Listen port | `1502` | Modbus TCP port exposed by the proxy |
| RTU host | none | IP or host of the transparent TCP-to-RS485 adapter |
| RTU port | `8899` | TCP port of the transparent adapter |
| Request timeout | `3.0` | Seconds to wait for an RTU response |
| Inter request delay | `80` | Milliseconds between RTU requests |
| Max clients | `4` | Maximum simultaneous TCP clients |
| Log level | `info` | Proxy logging level |

## Solis Example

For a Solis inverter through a transparent Waveshare TCP-to-RS485 adapter:

```text
Home Assistant solis_modbus -> HA host:1502 -> proxy -> Waveshare <adapter-ip>:8899 -> Solis RS485
```

Configure this integration:

- RTU host: the Waveshare adapter IP address
- RTU port: `8899`
- Listen port: `1502`

Configure `solis_modbus`:

- Host: the Home Assistant host IP
- Port: `1502`
- Slave/unit id: `1`
- Connection: `WAVESHARE`

Keep the Waveshare in transparent TCP server mode.

## Notes

- The proxy serializes all RTU traffic because RS485 is half-duplex.
- RTU timeouts are returned as Modbus exception `0x0B`.
- Invalid RTU responses are returned as Modbus exception `0x04`.
