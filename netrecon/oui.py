"""MAC vendor lookup: bundled offline OUI DB, optional online fallback."""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from . import config
from .utils import get_logger

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "oui.tsv"

_db: dict[str, str] | None = None


def _normalize_mac(mac: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", mac).upper()


def _load_db() -> dict[str, str]:
    global _db
    if _db is not None:
        return _db
    db: dict[str, str] = {}
    if DATA_PATH.exists():
        for line in DATA_PATH.read_text().splitlines():
            line = line.strip()
            if not line or "\t" not in line:
                continue
            prefix, vendor = line.split("\t", 1)
            db[prefix.upper()] = vendor
    _db = db
    return db


def _online_lookup(prefix: str) -> Optional[str]:
    """Best-effort online fallback. Disabled by default via config."""
    url = f"https://api.macvendors.com/{prefix}"
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8", errors="ignore").strip()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        get_logger().debug("Online OUI lookup failed for %s: %s", prefix, exc)
    return None


def lookup_vendor(mac: str) -> str:
    """Return a vendor name for a MAC address, or a clear placeholder if unknown."""
    norm = _normalize_mac(mac)
    if len(norm) < 6:
        return "Unknown"
    prefix = norm[:6]

    db = _load_db()
    vendor = db.get(prefix)
    if vendor:
        return vendor

    if _is_locally_administered(norm):
        return "Randomized/Private MAC"

    cfg = config.get_config()
    if cfg.get("online_vendor_lookup"):
        online = _online_lookup(norm[:6])
        if online:
            return online

    return "Unknown"


def _is_locally_administered(mac_hex: str) -> bool:
    try:
        first_octet = int(mac_hex[0:2], 16)
    except ValueError:
        return False
    return bool(first_octet & 0b10)
