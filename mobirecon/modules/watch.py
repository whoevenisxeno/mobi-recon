"""Watch mode: re-run host discovery on an interval, diff results, announce changes."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterator

from .host_discovery import Host, discover_hosts


@dataclass
class WatchEvent:
    timestamp: str
    appeared: list[Host]
    disappeared: list[Host]
    total: int
    method: str


def watch_hosts(cidr: str, interval_seconds: int, stop_check: Callable[[], bool]) -> Iterator[WatchEvent]:
    """Yields a WatchEvent after every scan pass. Caller controls stop via stop_check()
    (checked between passes) so Ctrl-C handling stays in the TUI layer, not here."""
    previous: dict[str, Host] = {}
    first_pass = True

    while not stop_check():
        hosts, method = discover_hosts(cidr)
        current = {h.ip: h for h in hosts}

        if first_pass:
            appeared, disappeared = [], []
            first_pass = False
        else:
            appeared = [h for ip, h in current.items() if ip not in previous]
            disappeared = [h for ip, h in previous.items() if ip not in current]

        yield WatchEvent(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            appeared=appeared,
            disappeared=disappeared,
            total=len(current),
            method=method,
        )

        previous = current

        for _ in range(interval_seconds * 10):
            if stop_check():
                break
            time.sleep(0.1)
