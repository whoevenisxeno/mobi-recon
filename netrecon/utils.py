"""Subprocess + logging helpers. All external commands must go through run_command()."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"

LOG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    logger = logging.getLogger("netrecon")
    logger.setLevel(logging.DEBUG)
    log_file = LOG_DIR / f"netrecon_{datetime.now():%Y%m%d}.log"
    fh = logging.FileHandler(log_file)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    _logger = logger
    return logger


@dataclass
class CommandResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: Optional[int] = None
    timed_out: bool = False
    error: str = ""


def which(binary: str) -> Optional[str]:
    return shutil.which(binary)


def run_command(
    args: list[str],
    timeout: float = 15.0,
    input_data: Optional[str] = None,
) -> CommandResult:
    """Run a command with a mandatory timeout, capturing stdout/stderr. Never raises."""
    log = get_logger()
    log.debug("RUN: %s (timeout=%s)", " ".join(args), timeout)
    try:
        proc = subprocess.run(
            args,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = CommandResult(
            ok=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
        if not result.ok:
            log.warning("Command failed (%s): %s | stderr=%s", proc.returncode, args, proc.stderr.strip())
        return result
    except FileNotFoundError:
        log.warning("Binary not found: %s", args[0] if args else "?")
        return CommandResult(ok=False, error=f"binary not found: {args[0] if args else '?'}")
    except subprocess.TimeoutExpired:
        log.warning("Command timed out: %s", args)
        return CommandResult(ok=False, timed_out=True, error="timed out")
    except Exception as exc:  # defensive: never let a subprocess call crash the TUI
        log.error("Command raised exception: %s | %s", args, exc)
        return CommandResult(ok=False, error=str(exc))


def save_json(name: str, data) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{name}_{ts}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def save_text(name: str, text: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{name}_{ts}.txt"
    path.write_text(text)
    return path
