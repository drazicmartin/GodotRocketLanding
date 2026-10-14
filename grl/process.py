"""Launching and cleaning up the exported GRL game binary."""
import atexit
import os
import platform
import socket
import stat
import subprocess
from pathlib import Path
from typing import Mapping, Optional

from .config import ConfigLike, resolve_config

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


def check_binary(path: Path) -> None:
    """Fail early on a Git LFS pointer, and make sure the binary is executable (git may drop the +x bit)."""
    with open(path, "rb") as f:
        head = f.read(64)
    if head.startswith(b"version https://git-lfs"):
        raise RuntimeError(
            f"{path} is a Git LFS pointer, not the game: install git-lfs and run `git lfs pull` in the repo."
        )
    if os.name == "posix" and not os.access(path, os.X_OK):
        mode = path.stat().st_mode
        # give execute permission to whoever can read it
        path.chmod(mode | ((mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)) >> 2))


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class GameProcess:
    """Owns the game subprocess so it can be terminated (also at interpreter exit)."""

    def __init__(self, port: int, show_window: bool = False, debug: bool = False,
                 binary: Optional[os.PathLike] = None, config: Optional["ConfigLike"] = None):
        self.port = port
        # absolute: the game is started from its own folder, a relative path would be searched in $PATH
        self.binary = Path(binary).resolve() if binary else find_binary()
        self.show_window = show_window
        self.debug = debug
        self.config = config
        self._temp_config: Optional[Path] = None  # written from a dict, deleted on terminate
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        check_binary(self.binary)
        cmd = [str(self.binary), "-p", str(self.port)]
        if not self.show_window or platform.system() == "Linux":
            cmd.append("--headless")
            # Nobody watches: run frames back-to-back with a fixed step instead of in real time
            # (godot --fixed-fps). It must equal 1 / physics_ticks_per_second, which set_scripted fixes at 30.
            cmd += ["--fixed-fps", "30"]
        if self.debug:
            cmd.append("--debug")
        if self.config is not None:
            path = resolve_config(self.config)
            if isinstance(self.config, Mapping):
                self._temp_config = path
            cmd += ["--config", str(path.resolve())]
        # Run from the binary's folder: the .pck sits next to it.
        self.proc = subprocess.Popen(cmd, cwd=self.binary.parent)
        atexit.register(self.terminate)

    def exit_code(self) -> Optional[int]:
        """Exit code once the game has exited, None while it runs (or was never started)."""
        return None if self.proc is None else self.proc.poll()

    def terminate(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        if self._temp_config is not None:
            self._temp_config.unlink(missing_ok=True)
            self._temp_config = None
