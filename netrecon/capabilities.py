"""Runtime capability probe. Never assume a binary/permission/API exists — check it."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import utils

TERMUX_API_PROBE_TIMEOUT = 4.0

BINARIES = ["nmap", "whois", "ip", "ping", "traceroute", "bluetoothctl", "hcitool", "host", "dig"]
TERMUX_CLIS = [
    "termux-wifi-scaninfo",
    "termux-wifi-connectioninfo",
    "termux-telephony-deviceinfo",
    "termux-sensor",
    "termux-location",
    "termux-battery-status",
]


@dataclass
class Capabilities:
    is_termux: bool = False
    binaries: dict = field(default_factory=dict)
    termux_clis: dict = field(default_factory=dict)
    termux_api_app_responsive: bool = False
    termux_api_app_error: str = ""
    is_rooted: bool = False
    su_present: bool = False
    bluetooth_backend: str = "none"  # "bluez" | "termux-fork" | "none"

    def summary_lines(self) -> list[str]:
        lines = [f"Termux environment: {'yes' if self.is_termux else 'NO (compatibility mode)'}"]
        lines.append(f"Root: {'yes' if self.is_rooted else 'no'}")
        lines.append(f"Termux:API app responsive: {'yes' if self.termux_api_app_responsive else 'no'}")
        lines.append(f"Bluetooth backend: {self.bluetooth_backend}")
        return lines


def _detect_termux() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "") or os.path.isdir("/data/data/com.termux")


def _detect_root() -> tuple[bool, bool]:
    su_present = utils.which("su") is not None
    is_rooted = False
    try:
        is_rooted = os.geteuid() == 0
    except AttributeError:
        pass
    if not is_rooted and su_present:
        # su binary existing doesn't mean it's usable; a real check would need
        # to actually invoke it, but that can trigger a root prompt as a side
        # effect, which is not acceptable during a passive capability probe.
        pass
    return is_rooted, su_present


def _probe_termux_api_app() -> tuple[bool, str]:
    """termux-api CLI shims exist even when the companion APP is missing/mismatched.
    Run a harmless, fast command under a short timeout to detect a hung/dead app."""
    if utils.which("termux-wifi-connectioninfo") is None:
        return False, "termux-wifi-connectioninfo not installed (termux-api package missing)"
    result = utils.run_command(["termux-wifi-connectioninfo"], timeout=TERMUX_API_PROBE_TIMEOUT)
    if result.timed_out:
        return False, "termux-api CLI hung — Termux:API app is likely not installed or mismatched-signature"
    if not result.ok and not result.stdout.strip():
        return False, result.stderr.strip() or result.error or "no response from Termux:API app"
    return True, ""


def _probe_bluetooth_backend(is_rooted: bool) -> str:
    if utils.which("bluetoothctl") is not None or utils.which("hcitool") is not None:
        return "bluez"
    if utils.which("termux-bluetooth-scaninfo") is not None:
        return "termux-fork"
    return "none"


def probe() -> Capabilities:
    caps = Capabilities()
    caps.is_termux = _detect_termux()

    for b in BINARIES:
        caps.binaries[b] = utils.which(b) is not None

    for cli in TERMUX_CLIS:
        caps.termux_clis[cli] = utils.which(cli) is not None

    caps.is_rooted, caps.su_present = _detect_root()

    if any(caps.termux_clis.values()):
        caps.termux_api_app_responsive, caps.termux_api_app_error = _probe_termux_api_app()
    else:
        caps.termux_api_app_error = "termux-api package not installed"

    caps.bluetooth_backend = _probe_bluetooth_backend(caps.is_rooted)

    utils.get_logger().info("Capability probe: %s", caps.summary_lines())
    return caps


_cached: Capabilities | None = None


def get_capabilities(refresh: bool = False) -> Capabilities:
    global _cached
    if _cached is None or refresh:
        _cached = probe()
    return _cached
