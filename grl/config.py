"""Game launch config: an INI file (Godot ConfigFile) passed to the game with --config.

Example (dict form, as accepted by GRL/GRLEnv `config=`):
    {"camera": {"zoom": 0.25}}

Keys read by the game (scripts/settings.gd):
    [camera] zoom  - Camera2D zoom factor, clamped to [0.1, 2.0]; < 1 shows more of the world.
                     Default 0.1 (fully zoomed out).
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Mapping, Union

ConfigLike = Union[str, os.PathLike, Mapping[str, Mapping[str, object]]]


def _value(v: object) -> str:
    # Godot ConfigFile values are Variant literals: numbers/bools as-is, strings JSON-quoted.
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return json.dumps(str(v))


def write_config(config: Mapping[str, Mapping[str, object]], path: Union[str, os.PathLike, None] = None) -> Path:
    """Write `config` ({section: {key: value}}) as a Godot ConfigFile; a temp file when `path` is None."""
    lines = []
    for section, values in config.items():
        lines.append(f"[{section}]")
        lines += [f"{key}={_value(value)}" for key, value in values.items()]
        lines.append("")
    if path is None:
        fd, path = tempfile.mkstemp(prefix="grl_", suffix=".cfg")
        os.close(fd)
    path = Path(path)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def resolve_config(config: ConfigLike) -> Path:
    """Path to an existing config file, or a temp file written from a dict."""
    if isinstance(config, Mapping):
        return write_config(config)
    path = Path(config)
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    return path
