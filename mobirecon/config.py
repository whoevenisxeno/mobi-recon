"""JSON config file with defaults, loaded/saved next to the repo root."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULTS = {
    "banner_text": "MOBI RECON",
    "banner_font": "slant",
    "color_theme": "cyan",
    "default_port_range": "1-1000",
    "scan_timeout": 15,
    "output_dir": "output",
    "online_vendor_lookup": False,
    "known_devices_file": "known_devices.json",
    "wifi_scan_cooldown_seconds": 30,
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            merged = {**DEFAULTS, **data}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULTS)


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


_config: dict | None = None


def get_config(refresh: bool = False) -> dict:
    global _config
    if _config is None or refresh:
        _config = load_config()
    return _config
