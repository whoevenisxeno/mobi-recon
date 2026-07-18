"""Bluetooth discovery via pluggable, auto-detected backends. Discovery only —
no pairing, no injection. If no backend is available we say so plainly and
never fabricate or simulate results."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .. import utils
from ..capabilities import get_capabilities
from ..oui import lookup_vendor


@dataclass
class BtDevice:
    name: str
    address: str
    vendor: str
    rssi: str = ""
    kind: str = ""  # "classic" | "ble"


def backend_status() -> tuple[str, str]:
    """Returns (backend_name, explanation)."""
    caps = get_capabilities()
    backend = caps.bluetooth_backend
    if backend == "bluez":
        return "bluez", "bluetoothctl/hcitool found."
    if backend == "termux-fork":
        return "termux-fork", "termux-bluetooth-scaninfo found (unofficial Termux fork)."
    return "none", (
        "No Bluetooth backend available. Stock Termux:API has no scan command. "
        "Needs either: (a) root + BlueZ (bluetoothctl/hcitool), or "
        "(b) the unofficial Termux fork that ships termux-bluetooth-scaninfo."
    )


def _scan_bluez(timeout: float = 15.0) -> tuple[list[BtDevice], str]:
    if utils.which("bluetoothctl") is None:
        return [], "bluetoothctl not found"

    utils.run_command(["bluetoothctl", "power", "on"], timeout=5)
    utils.run_command(["bluetoothctl", "scan", "on"], timeout=timeout)

    devices_result = utils.run_command(["bluetoothctl", "devices"], timeout=10)
    if not devices_result.ok:
        return [], devices_result.stderr.strip() or "bluetoothctl devices failed"

    devices = []
    for line in devices_result.stdout.splitlines():
        m = re.match(r"Device ([0-9A-Fa-f:]{17}) (.+)", line.strip())
        if not m:
            continue
        addr, name = m.groups()
        devices.append(BtDevice(name=name, address=addr, vendor=lookup_vendor(addr), kind="classic/ble"))
    return devices, ""


def _scan_termux_fork(timeout: float = 15.0) -> tuple[list[BtDevice], str]:
    import json
    result = utils.run_command(["termux-bluetooth-scaninfo"], timeout=timeout)
    if not result.ok and not result.stdout.strip():
        return [], result.stderr.strip() or "termux-bluetooth-scaninfo produced no output"
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], "could not parse termux-bluetooth-scaninfo output"

    devices = []
    for entry in raw:
        addr = entry.get("address", entry.get("mac", ""))
        devices.append(BtDevice(
            name=entry.get("name", "") or "<unknown>",
            address=addr,
            vendor=lookup_vendor(addr) if addr else "",
            rssi=str(entry.get("rssi", "")),
            kind=entry.get("type", ""),
        ))
    return devices, ""


def scan_devices(timeout: float = 15.0) -> tuple[list[BtDevice], str]:
    backend, _ = backend_status()
    if backend == "bluez":
        return _scan_bluez(timeout)
    if backend == "termux-fork":
        return _scan_termux_fork(timeout)
    _, explanation = backend_status()
    return [], explanation
