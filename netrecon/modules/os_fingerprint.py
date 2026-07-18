"""OS fingerprinting via nmap -O. ROOT GATED — SYN/OS probes need raw sockets."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .. import utils
from ..capabilities import get_capabilities


@dataclass
class OsGuess:
    name: str
    accuracy: int


def fingerprint_os(host: str, timeout: float = 60.0) -> tuple[list[OsGuess], str]:
    """Returns (guesses, error). error is empty on success."""
    caps = get_capabilities()
    if not caps.is_rooted:
        return [], "OS fingerprinting requires root (nmap -O needs raw socket access)"
    if utils.which("nmap") is None:
        return [], "nmap not installed"

    result = utils.run_command(["nmap", "-O", "-oX", "-", host], timeout=timeout)
    if not result.ok or not result.stdout.strip():
        return [], result.stderr.strip() or "nmap -O produced no output"

    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError:
        return [], "failed to parse nmap XML output"

    guesses = []
    for match in root.findall(".//osmatch"):
        name = match.get("name", "unknown")
        accuracy = int(match.get("accuracy", "0"))
        guesses.append(OsGuess(name=name, accuracy=accuracy))
    if not guesses:
        return [], "no OS match found (target may be filtering probes)"
    return guesses, ""
