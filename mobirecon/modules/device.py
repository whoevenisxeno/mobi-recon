"""Own-phone info via termux-api: telephony, sensors, GPS, battery."""
from __future__ import annotations

import json

from .. import utils


def _run_json(cmd: list[str], timeout: float) -> tuple[dict | list, str]:
    if utils.which(cmd[0]) is None:
        return {}, f"{cmd[0]} not available (install termux-api package)"
    result = utils.run_command(cmd, timeout=timeout)
    if not result.ok and not result.stdout.strip():
        return {}, result.stderr.strip() or result.error or "No response from Termux:API app"
    try:
        return json.loads(result.stdout), ""
    except json.JSONDecodeError:
        return {}, f"Could not parse {cmd[0]} output"


def telephony_info() -> tuple[dict | list, str]:
    return _run_json(["termux-telephony-deviceinfo"], 8)


def sensor_list() -> tuple[dict | list, str]:
    return _run_json(["termux-sensor", "-l"], 8)


def battery_status() -> tuple[dict | list, str]:
    return _run_json(["termux-battery-status"], 8)


def location(provider: str = "gps", timeout: float = 20.0) -> tuple[dict | list, str]:
    """provider: gps | network | passive."""
    if utils.which("termux-location") is None:
        return {}, "termux-location not available (install termux-api package)"
    result = utils.run_command(["termux-location", "-p", provider, "-r", "once"], timeout=timeout)
    if not result.ok and not result.stdout.strip():
        return {}, result.stderr.strip() or result.error or "No location fix (GPS off, indoors, or app not granted permission)"
    try:
        return json.loads(result.stdout), ""
    except json.JSONDecodeError:
        return {}, "Could not parse termux-location output"
