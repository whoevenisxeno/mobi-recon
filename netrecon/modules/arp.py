"""ARP neighbor table via `ip neigh` — works with no root, no nmap."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .. import utils
from ..oui import lookup_vendor


@dataclass
class ArpEntry:
    ip: str
    mac: str
    vendor: str
    state: str


def get_arp_table() -> list[ArpEntry]:
    if utils.which("ip") is None:
        return []
    result = utils.run_command(["ip", "neigh"], timeout=5)
    if not result.ok:
        return []

    entries = []
    for line in result.stdout.splitlines():
        m = re.match(r"(\S+) dev (\S+) lladdr ([0-9a-fA-F:]+) (\S+)", line)
        if not m:
            continue
        ip, _dev, mac, state = m.groups()
        entries.append(ArpEntry(ip=ip, mac=mac, vendor=lookup_vendor(mac), state=state))
    return entries
