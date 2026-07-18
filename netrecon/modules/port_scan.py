"""Port scanning: nmap connect scan by default, SYN scan when root, pure-Python TCP fallback."""
from __future__ import annotations

import socket
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .. import utils
from ..capabilities import get_capabilities

TOP_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 443, 445, 465, 587,
    993, 995, 1723, 3306, 3389, 5900, 8080, 8443, 8888, 9100, 25565,
]


@dataclass
class PortResult:
    port: int
    protocol: str = "tcp"
    state: str = "unknown"
    service: str = ""
    product: str = ""
    version: str = ""
    banner: str = ""


def _parse_port_range(spec: str) -> list[int]:
    if spec.lower() == "top-ports":
        return TOP_PORTS
    ports = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            ports.extend(range(int(lo), int(hi) + 1))
        elif part:
            ports.append(int(part))
    return ports


def scan_with_nmap(host: str, port_spec: str, service_detect: bool = False, timeout: float = 120.0) -> list[PortResult] | None:
    if utils.which("nmap") is None:
        return None

    caps = get_capabilities()
    args = ["nmap", "-oX", "-"]
    args.append("-sS" if caps.is_rooted else "-sT")
    if service_detect:
        args.append("-sV")

    if port_spec.lower() == "top-ports":
        args += ["--top-ports", "100"]
    elif port_spec.lower() == "full":
        args += ["-p-"]
    else:
        args += ["-p", port_spec]

    args.append(host)
    result = utils.run_command(args, timeout=timeout)
    if not result.ok or not result.stdout.strip():
        return None

    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError:
        return None

    results = []
    for port_el in root.findall(".//port"):
        portid = int(port_el.get("portid", "0"))
        proto = port_el.get("protocol", "tcp")
        state_el = port_el.find("state")
        state = state_el.get("state", "unknown") if state_el is not None else "unknown"
        service_el = port_el.find("service")
        service = product = version = ""
        if service_el is not None:
            service = service_el.get("name", "")
            product = service_el.get("product", "")
            version = service_el.get("version", "")
        results.append(PortResult(port=portid, protocol=proto, state=state, service=service, product=product, version=version))
    return results


def _tcp_connect_scan_port(host: str, port: int, timeout: float, grab_banner: bool) -> PortResult:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            banner = ""
            if grab_banner:
                try:
                    sock.settimeout(1.0)
                    data = sock.recv(256)
                    banner = data.decode("utf-8", errors="ignore").strip()
                except (socket.timeout, OSError):
                    pass
            return PortResult(port=port, state="open", banner=banner)
    except (socket.timeout, ConnectionRefusedError, OSError):
        return PortResult(port=port, state="closed")


def scan_with_sockets(host: str, port_spec: str, timeout: float = 1.0, max_workers: int = 64, grab_banner: bool = True) -> list[PortResult]:
    ports = _parse_port_range(port_spec)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_tcp_connect_scan_port, host, p, timeout, grab_banner): p for p in ports}
        for fut in as_completed(futures):
            results.append(fut.result())
    return sorted([r for r in results if r.state == "open"], key=lambda r: r.port)


def scan_ports(host: str, port_spec: str = "top-ports", service_detect: bool = False) -> tuple[list[PortResult], str]:
    nmap_results = scan_with_nmap(host, port_spec, service_detect=service_detect)
    if nmap_results is not None:
        return nmap_results, "nmap"
    return scan_with_sockets(host, port_spec), "socket connect scan"
