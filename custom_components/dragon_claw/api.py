"""Minimal Dragon Claw gRPC client, Wake-on-LAN and ARP lookup."""

from __future__ import annotations

import socket
from enum import IntEnum

import grpc

DEFAULT_PORT = 37121
_SERVICE = "/net.janrupf.dc.DragonClawAgent/"
_TIMEOUT = 5


class PowerAction(IntEnum):
    """Mirrors PowerAction in dragon-claw proto/service.proto."""

    POWER_OFF = 0
    REBOOT = 1
    REBOOT_TO_FIRMWARE = 2
    LOCK = 4
    LOG_OUT = 5
    SUSPEND = 6
    HIBERNATE = 7
    HYBRID_SUSPEND = 8


# ponytail: hand-rolled protobuf, the schema is 2 tiny messages; switch to generated stubs if it grows.
def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def encode_power_action_request(action: PowerAction) -> bytes:
    """PowerActionRequest { action = 1 }."""
    return b"\x08" + _varint(action)


def decode_supported_power_actions(data: bytes) -> set[PowerAction]:
    """SupportedPowerActions { repeated PowerAction actions = 1 }, packed or not."""
    values: list[int] = []
    pos = 0
    while pos < len(data):
        key, pos = _read_varint(data, pos)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _read_varint(data, pos)
            if field == 1:
                values.append(value)
        elif wire == 2:
            length, pos = _read_varint(data, pos)
            end = pos + length
            while field == 1 and pos < end:
                value, pos = _read_varint(data, pos)
                values.append(value)
            pos = end
        else:
            raise ValueError(f"Unexpected wire type {wire}")
    return {PowerAction(v) for v in values if v in PowerAction._value2member_map_}


async def _call(host: str, port: int, method: str, request: bytes) -> bytes:
    async with grpc.aio.insecure_channel(f"{host}:{port}") as channel:
        return await channel.unary_unary(_SERVICE + method)(request, timeout=_TIMEOUT)


async def get_supported_power_actions(host: str, port: int) -> set[PowerAction]:
    """Query supported actions; raises grpc.aio.AioRpcError when unreachable."""
    return decode_supported_power_actions(
        await _call(host, port, "GetSupportedPowerActions", b"")
    )


async def perform_power_action(host: str, port: int, action: PowerAction) -> None:
    """Perform a power action on the agent."""
    await _call(host, port, "PerformPowerAction", encode_power_action_request(action))


def send_magic_packet(mac: str, broadcast: str = "255.255.255.255") -> None:
    """Send a Wake-on-LAN magic packet (blocking, run in executor)."""
    raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    if len(raw) != 6:
        raise ValueError(f"Invalid MAC address: {mac}")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(b"\xff" * 6 + raw * 16, (broadcast, 9))


def mac_from_arp(ip: str) -> str | None:
    """Best-effort MAC lookup from the Linux ARP table (blocking)."""
    try:
        with open("/proc/net/arp", encoding="ascii") as arp:
            for line in arp.readlines()[1:]:
                parts = line.split()
                if parts[0] == ip and parts[3] != "00:00:00:00:00:00":
                    return parts[3]
    except OSError:
        pass
    return None


if __name__ == "__main__":
    assert encode_power_action_request(PowerAction.REBOOT) == b"\x08\x01"
    assert encode_power_action_request(PowerAction.POWER_OFF) == b"\x08\x00"
    assert decode_supported_power_actions(b"") == set()
    # packed: field 1, len 3, [0, 1, 6]
    assert decode_supported_power_actions(b"\x0a\x03\x00\x01\x06") == {
        PowerAction.POWER_OFF, PowerAction.REBOOT, PowerAction.SUSPEND
    }
    # unpacked + unknown enum value 99 ignored
    assert decode_supported_power_actions(b"\x08\x04\x08\x63") == {PowerAction.LOCK}
    assert _read_varint(_varint(300), 0) == (300, 2)
    print("ok")
