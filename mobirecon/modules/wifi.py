"""WiFi scanning via termux-api. Handles Android's ~30s scan throttle and the
empty-result-when-Location-is-off gotcha explicitly instead of pretending it's a bug."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from .. import utils, config
from ..oui import lookup_vendor

_last_scan_time: float = 0.0
_last_scan_result: list["AccessPoint"] | None = None


@dataclass
class AccessPoint:
    ssid: str
    bssid: str
    vendor: str
    rssi: int
    frequency: int
    capabilities: str


def cooldown_remaining() -> float:
    cfg = config.get_config()
    cooldown = cfg.get("wifi_scan_cooldown_seconds", 30)
    elapsed = time.monotonic() - _last_scan_time
    return max(0.0, cooldown - elapsed)


def get_cached_scan() -> list[AccessPoint] | None:
    return _last_scan_result


def scan_access_points(force: bool = False, timeout: float = 15.0) -> tuple[list[AccessPoint], str]:
    """Returns (aps, note). note explains empty/throttled/cached results plainly."""
    global _last_scan_time, _last_scan_result

    if utils.which("termux-wifi-scaninfo") is None:
        return [], "termux-wifi-scaninfo not available (install termux-api package)"

    remaining = cooldown_remaining()
    if not force and remaining > 0:
        cached = _last_scan_result or []
        return cached, (
            f"Android throttles WiFi scans to ~1/30s. {remaining:.0f}s left on cooldown — "
            f"showing last cached result ({len(cached)} networks)."
        )

    result = utils.run_command(["termux-wifi-scaninfo"], timeout=timeout)
    _last_scan_time = time.monotonic()

    if not result.ok and not result.stdout.strip():
        return [], "No response from Termux:API app — is it installed and running?"

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], "Could not parse termux-wifi-scaninfo output"

    if not raw:
        note = (
            "Scan returned zero networks. On modern Android this almost always means "
            "Location services are OFF (WiFi scanning is gated behind Location permission), "
            "not that there are no networks nearby. Turn Location ON and rescan."
        )
        _last_scan_result = []
        return [], note

    aps = []
    for entry in raw:
        bssid = entry.get("bssid", "")
        aps.append(AccessPoint(
            ssid=entry.get("ssid", "") or "<hidden>",
            bssid=bssid,
            vendor=lookup_vendor(bssid) if bssid else "",
            rssi=entry.get("rssi", 0),
            frequency=entry.get("frequency", 0),
            capabilities=entry.get("capabilities", ""),
        ))
    aps.sort(key=lambda a: a.rssi, reverse=True)
    _last_scan_result = aps
    return aps, f"{len(aps)} networks found."


def get_connection_info() -> tuple[dict, str]:
    if utils.which("termux-wifi-connectioninfo") is None:
        return {}, "termux-wifi-connectioninfo not available (install termux-api package)"
    result = utils.run_command(["termux-wifi-connectioninfo"], timeout=8)
    if not result.ok and not result.stdout.strip():
        return {}, "No response from Termux:API app"
    try:
        return json.loads(result.stdout), ""
    except json.JSONDecodeError:
        return {}, "Could not parse termux-wifi-connectioninfo output"
