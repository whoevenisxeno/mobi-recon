"""Known-devices tracker: persist MACs the user has seen/labeled, flag unknowns."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .. import config, utils

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class KnownDevice:
    mac: str
    label: str = ""
    vendor: str = ""
    first_seen: str = ""
    last_seen: str = ""


def _store_path() -> Path:
    cfg = config.get_config()
    return BASE_DIR / cfg.get("known_devices_file", "known_devices.json")


def load_known() -> dict[str, KnownDevice]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return {mac: KnownDevice(**data) for mac, data in raw.items()}


def save_known(devices: dict[str, KnownDevice]) -> None:
    path = _store_path()
    serializable = {mac: vars(dev) for mac, dev in devices.items()}
    path.write_text(json.dumps(serializable, indent=2))


def add_known(mac: str, label: str, vendor: str = "") -> None:
    devices = load_known()
    now = datetime.now().isoformat(timespec="seconds")
    existing = devices.get(mac.upper())
    if existing:
        existing.label = label or existing.label
        existing.vendor = vendor or existing.vendor
        existing.last_seen = now
    else:
        devices[mac.upper()] = KnownDevice(mac=mac.upper(), label=label, vendor=vendor, first_seen=now, last_seen=now)
    save_known(devices)


def remove_known(mac: str) -> bool:
    devices = load_known()
    if mac.upper() in devices:
        del devices[mac.upper()]
        save_known(devices)
        return True
    return False


def classify(macs_seen: list[str]) -> tuple[list[str], list[str]]:
    """Returns (known_macs, unknown_macs) from a list of currently-seen MACs."""
    known = load_known()
    known_seen, unknown_seen = [], []
    now = datetime.now().isoformat(timespec="seconds")
    touched = False
    for mac in macs_seen:
        key = mac.upper()
        if key in known:
            known[key].last_seen = now
            touched = True
            known_seen.append(mac)
        else:
            unknown_seen.append(mac)
    if touched:
        save_known(known)
    return known_seen, unknown_seen
