"""Local connection info: IP, gateway, subnet, interface, SSID, public IP + geolocation."""
from __future__ import annotations

import json
import re
import socket
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from typing import Optional

from .. import utils


@dataclass
class ConnectionInfo:
    local_ip: Optional[str] = None
    interface: Optional[str] = None
    gateway: Optional[str] = None
    subnet_cidr: Optional[str] = None
    ssid: Optional[str] = None
    public_ip: Optional[str] = None
    geo_city: Optional[str] = None
    geo_country: Optional[str] = None
    geo_org: Optional[str] = None
    errors: list[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _get_default_route() -> tuple[Optional[str], Optional[str]]:
    """Returns (gateway, interface) from `ip route`."""
    if utils.which("ip") is None:
        return None, None
    result = utils.run_command(["ip", "route", "show", "default"], timeout=5)
    if not result.ok:
        return None, None
    m = re.search(r"default via (\S+) dev (\S+)", result.stdout)
    if m:
        return m.group(1), m.group(2)
    return None, None


def _get_local_ip_and_cidr(interface: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if utils.which("ip") is None or not interface:
        return None, None
    result = utils.run_command(["ip", "-4", "addr", "show", "dev", interface], timeout=5)
    if not result.ok:
        return None, None
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", result.stdout)
    if not m:
        return None, None
    cidr = m.group(1)
    ip = cidr.split("/")[0]
    return ip, cidr


def _get_ssid() -> Optional[str]:
    if utils.which("termux-wifi-connectioninfo") is None:
        return None
    result = utils.run_command(["termux-wifi-connectioninfo"], timeout=6)
    if not result.ok:
        return None
    try:
        data = json.loads(result.stdout)
        ssid = data.get("ssid")
        if ssid and ssid != "<unknown ssid>":
            return ssid
    except json.JSONDecodeError:
        pass
    return None


def _get_public_ip_and_geo() -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Best-effort external call to a geolocation API. Times out fast, never raises."""
    try:
        with urllib.request.urlopen("https://ipapi.co/json/", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            return (
                data.get("ip"),
                data.get("city"),
                data.get("country_name"),
                data.get("org"),
            )
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, socket.timeout):
        return None, None, None, None


def get_connection_info(include_public: bool = True) -> ConnectionInfo:
    info = ConnectionInfo(errors=[])

    gateway, interface = _get_default_route()
    info.gateway = gateway
    info.interface = interface
    if not interface:
        info.errors.append("Could not determine default interface (is `ip` installed / network up?)")

    local_ip, cidr = _get_local_ip_and_cidr(interface)
    info.local_ip = local_ip
    info.subnet_cidr = cidr

    info.ssid = _get_ssid()
    if info.ssid is None:
        info.errors.append("SSID unavailable (needs termux-api + Termux:API app + Location on)")

    if include_public:
        pub_ip, city, country, org = _get_public_ip_and_geo()
        info.public_ip, info.geo_city, info.geo_country, info.geo_org = pub_ip, city, country, org
        if pub_ip is None:
            info.errors.append("Public IP/geolocation lookup failed (no internet or API unreachable)")

    return info
