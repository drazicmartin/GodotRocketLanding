"""Launching and cleaning up the exported GRL game binary."""
import atexit
import os
import platform
import socket
import subprocess
from pathlib import Path
from typing import Optional

BINARY_ENV_VAR = "GRL_BINARY"


def find_binary() -> Path:
    """Locate the exported game: $GRL_BINARY, then the repo root, then the current directory."""
    name = "GRL.exe" if platform.system() == "Windows" else "GRL.x86_64"
    candidates = []
    if os.environ.get(BINARY_ENV_VAR):
        candidates.append(Path(os.environ[BINARY_ENV_VAR]))
    candidates.append(Path(__file__).resolve().parent.parent / name)
    candidates.append(Path.cwd() / name)
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"Could not find {name}. Set ${BINARY_ENV_VAR} to the exported binary. Tried: "
        + ", ".join(str(c) for c in candidates)
    )


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class GameProcess:
    """Owns the game subprocess so it can be terminated (also at interpreter exit)."""

    def __init__(self, port: int, show_window: bool = False, debug: bool = False,
                 binary: Optional[os.PathLike] = None):
        self.port = port
        self.binary = Path(binary) if binary else find_binary()
        self.show_window = show_window
        self.debug = debug
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        cmd = [str(self.binary), "-p", str(self.port)]
        if not self.show_window or platform.system() == "Linux":
            cmd.append("--headless")
            # Nobody watches: run frames back-to-back with a fixed step instead of in real time
            # (godot --fixed-fps). It must equal 1 / physics_ticks_per_second, which set_scripted fixes at 30.
            cmd += ["--fixed-fps", "30"]
        if self.debug:
            cmd.append("--debug")
        # Run from the binary's folder: the .pck sits next to it.
        self.proc = subprocess.Popen(cmd, cwd=self.binary.parent)
        atexit.register(self.terminate)

    def terminate(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
