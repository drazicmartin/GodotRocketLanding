"""Backward-compatible import path: the code now lives in the `grl` package (repo root)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grl import GRL, GRLEnv, GRLGym, PROTOCOL_VERSION  # noqa: E402,F401
