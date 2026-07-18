"""Host discovery: nmap -sn preferred, pure-Python ping sweep + `ip neigh` fallback."""
from __future__ import annotations

import ipaddress
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .. import utils
from ..oui import lookup_vendor
from .arp import get_arp_table


@dataclass
class Host:
    ip: str
    mac: str = ""
    vendor: str = ""
    hostname: str = ""
    response_time_ms: float = -1.0
    source: str = ""


def discover_hosts_nmap(cidr: str, timeout: float = 60.0) -> list[Host] | None:
    if utils.which("nmap") is None:
        return None
    result = utils.run_command(["nmap", "-sn", "-oX", "-", cidr], timeout=timeout)
    if not result.ok or not result.stdout.strip():
        return None

    hosts = []
    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError:
        return None

    for h in root.findall("host"):
        status = h.find("status")
        if status is None or status.get("state") != "up":
            continue
        ip, mac, hostname = "", "", ""
        for addr in h.findall("address"):
            if addr.get("addrtype") == "ipv4":
                ip = addr.get("addr", "")
            elif addr.get("addrtype") == "mac":
                mac = addr.get("addr", "")
        hn = h.find("hostnames/hostname")
        if hn is not None:
            hostname = hn.get("name", "")
        if not ip:
            continue
        hosts.append(Host(
            ip=ip, mac=mac, vendor=lookup_vendor(mac) if mac else "",
            hostname=hostname, source="nmap",
        ))
    return hosts


def _ping_once(ip: str, timeout_s: float = 1.0) -> tuple[bool, float]:
    if utils.which("ping") is None:
        return False, -1.0
    start = time.monotonic()
    result = utils.run_command(["ping", "-c", "1", "-W", str(int(timeout_s)), ip], timeout=timeout_s + 2)
    elapsed_ms = (time.monotonic() - start) * 1000
    if result.ok:
        m = re.search(r"time=([\d.]+)", result.stdout)
        rtt = float(m.group(1)) if m else elapsed_ms
        return True, rtt
    return False, -1.0


def discover_hosts_ping_sweep(cidr: str, max_workers: int = 32, per_host_timeout: float = 1.0) -> list[Host]:
    """Pure-Python fallback: threaded ping sweep, then enrich with `ip neigh` for MACs."""
    network = ipaddress.ip_network(cidr, strict=False)
    hosts_up: dict[str, Host] = {}

    ips = [str(ip) for ip in network.hosts()]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_ping_once, ip, per_host_timeout): ip for ip in ips}
        for fut in as_completed(futures):
            ip = futures[fut]
            alive, rtt = fut.result()
            if alive:
                hosts_up[ip] = Host(ip=ip, response_time_ms=rtt, source="ping")

    arp_table = {e.ip: e for e in get_arp_table()}
    for ip, entry in arp_table.items():
        if ip in hosts_up:
            hosts_up[ip].mac = entry.mac
            hosts_up[ip].vendor = entry.vendor
        else:
            hosts_up[ip] = Host(ip=ip, mac=entry.mac, vendor=entry.vendor, source="arp")

    return sorted(hosts_up.values(), key=lambda h: tuple(int(p) for p in h.ip.split(".")))


def discover_hosts(cidr: str) -> tuple[list[Host], str]:
    """Try nmap first, fall back to ping sweep + ARP. Returns (hosts, method_used)."""
    nmap_hosts = discover_hosts_nmap(cidr)
    if nmap_hosts is not None:
        return nmap_hosts, "nmap -sn"
    return discover_hosts_ping_sweep(cidr), "ping sweep + ip neigh"
