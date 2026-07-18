"""Export scan results to timestamped JSON + pretty TXT in ./output."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .. import utils


def _to_plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    return obj


def _to_text(obj: Any, indent: int = 0) -> str:
    pad = "  " * indent
    plain = _to_plain(obj)
    lines = []
    if isinstance(plain, dict):
        for k, v in plain.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(_to_text(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {v}")
    elif isinstance(plain, list):
        for i, item in enumerate(plain):
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}[{i}]")
                lines.append(_to_text(item, indent + 1))
            else:
                lines.append(f"{pad}- {item}")
    else:
        lines.append(f"{pad}{plain}")
    return "\n".join(lines)


def export_result(name: str, data: Any) -> tuple[str, str]:
    """Writes both JSON and TXT. Returns (json_path, txt_path) as strings."""
    plain = _to_plain(data)
    json_path = utils.save_json(name, plain)
    text_body = f"netrecon export: {name}\n{'=' * 40}\n" + _to_text(data)
    txt_path = utils.save_text(name, text_body)
    return str(json_path), str(txt_path)
