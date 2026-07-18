"""Reverse DNS, whois, traceroute."""
from __future__ import annotations

import socket
from dataclasses import dataclass

from .. import utils


def reverse_dns(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror, OSError):
        return ""


def whois_lookup(target: str, timeout: float = 15.0) -> tuple[str, str]:
    """Returns (output, error)."""
    if utils.which("whois") is None:
        return "", "whois binary not installed"
    result = utils.run_command(["whois", target], timeout=timeout)
    if not result.ok and not result.stdout.strip():
        return "", result.stderr.strip() or result.error or "whois lookup failed"
    return result.stdout, ""


@dataclass
class TracerouteHop:
    hop: int
    address: str
    rtt_ms: str


def traceroute(target: str, max_hops: int = 30, timeout: float = 60.0) -> tuple[list[TracerouteHop], str]:
    if utils.which("traceroute") is None:
        return [], "traceroute binary not installed"
    result = utils.run_command(["traceroute", "-m", str(max_hops), "-w", "2", target], timeout=timeout)
    if not result.ok and not result.stdout.strip():
        return [], result.stderr.strip() or result.error or "traceroute failed"

    hops = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        hops.append(TracerouteHop(hop=int(parts[0]), address=parts[1].split()[0] if parts[1] else "*", rtt_ms=parts[1]))
    return hops, ""
