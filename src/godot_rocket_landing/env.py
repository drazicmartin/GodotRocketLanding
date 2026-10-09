"""One owned Godot process, one connection, one physics tick per step.

Use the patched source project, not the prebuilt GRL binaries. RGB is captured
inside Godot at the same simulation state as the returned telemetry.
"""
from __future__ import annotations

import base64
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from websockets.sync.client import connect

LEVELS = frozenset(("level_1", "level_2", "level_3", "level_4",
                   "random_level_easy", "random_level_moderate", "random_level_hard"))


def landing_reward(state, outcome):
    """Version 1: potential-free dense cost plus terminal integrity bonus.

    Telemetry is used for the reward only; world_model consumes rendered pixels.
    The task is a gentle upright landing anywhere on the planet surface.
    """
    position = np.asarray(state["position"], dtype=float)
    center = np.asarray(state["planet_position"], dtype=float)
    radial = position - center
    norm = float(np.linalg.norm(radial))
    up = radial / max(norm, 1e-9)
    angle = float(state["rotation"])
    rocket_up = np.array([math.sin(angle), -math.cos(angle)])
    tilt = 1.0 - float(np.clip(np.dot(up, rocket_up), -1, 1))
    speed = float(np.linalg.norm(state["linear_velocity"]))
    altitude = max(0.0, norm - float(state["planet_radius"]))
    cost = (0.01 + 0.002 * min(speed, 1000) + 0.05 * tilt
            + 0.0001 * min(altitude, 10000))
    bonus = 100.0 * float(state["rocket_integrity"]) if outcome == "victory" else 0.0
    if outcome == "crash":
        bonus = -100.0
    reward = bonus - cost
    if not math.isfinite(reward):
        raise ValueError("Non-finite simulator reward")
    return float(reward)


class RocketLandingEnv(gym.Env):
    metadata = {"render_modes": ["rgb_array"], "render_fps": 30}

    def __init__(self, render_mode="rgb_array", *, project_path=None, godot_bin=None,
                 level_name="random_level_easy", image_size=128, max_episode_steps=900,
                 port=None, timeout=30.0):
        if render_mode != "rgb_array":
            raise ValueError("Only render_mode='rgb_array' is supported")
        if level_name not in LEVELS:
            raise ValueError(f"Unknown level: {level_name}")
        if not isinstance(image_size, int) or not 32 <= image_size <= 640:
            raise ValueError("image_size must be an integer in [32, 640]")
        if not isinstance(max_episode_steps, int) or max_episode_steps < 1:
            raise ValueError("max_episode_steps must be a positive integer")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if port is not None and (not isinstance(port, int) or not 1024 <= port <= 65535):
            raise ValueError("port must be 1024..65535 or None")
        self.render_mode = render_mode
        self.level_name = level_name
        self.image_size = image_size
        self.max_episode_steps = max_episode_steps
        self.timeout = float(timeout)
        self.port = port
        self.project_path = Path(project_path or os.environ.get("GRL_PROJECT_PATH")
                                 or Path(__file__).resolve().parents[2]).expanduser().resolve()
        self.godot_bin = godot_bin or os.environ.get("GODOT_BIN") or "godot"
        self.action_space = spaces.Box(0.0, 1.0, shape=(3,), dtype=np.float32)
        self.observation_space = spaces.Box(0, 255, shape=(image_size, image_size, 3), dtype=np.uint8)
        self._process = self._socket = self._log = None
        self._pixels = None
        self._request_id = 0
        self._steps = 0
        self._done = True

    def _start(self):
        project = self.project_path
        if not (project / "scripts/world_model_bridge.gd").is_file():
            raise FileNotFoundError(f"Patched Godot dev source required at {project}; see docs/world-model.md")
        executable = shutil.which(str(self.godot_bin))
        if executable is None:
            raise FileNotFoundError("Godot 4.3 not found; set GODOT_BIN to its executable")
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError("RGB needs a display. On Linux run under xvfb-run -a; do not use --headless.")
        # An ephemeral port avoids collisions between sequential/parallel workers.
        # A process that loses the bind race is detected by the startup check below.
        port = self.port
        if port is None:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
        self._log = tempfile.TemporaryFile(mode="w+b")
        command = [executable, "--path", str(project), "--rendering-method", "gl_compatibility",
                   "--audio-driver", "Dummy", "--resolution", "640x640", "--",
                   "--world-model", "--wm-port", str(port)]
        try:
            self._process = subprocess.Popen(command, cwd=project, stdout=self._log, stderr=self._log)
            deadline = time.monotonic() + self.timeout
            while True:
                if self._process.poll() is not None:
                    raise RuntimeError("Godot exited during startup")
                try:
                    self._socket = connect(f"ws://127.0.0.1:{port}",
                                           open_timeout=min(1.0, self.timeout),
                                           close_timeout=1, max_size=4 * 1024 * 1024,
                                           compression=None)
                    break
                except (OSError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Timed out connecting to Godot")
                    time.sleep(0.05)
            hello = self._request("hello")
            if hello.get("pid") != self._process.pid or self._process.poll() is not None:
                raise RuntimeError("Port belongs to a different simulator process")
            if not hello.get("rendering"):
                raise RuntimeError("Godot is not rendering; use a display or Xvfb")
            if (hello.get("engine_major"), hello.get("engine_minor")) != (4, 3):
                raise RuntimeError("This integration is validated for Godot 4.3; use that version")
        except Exception as error:
            self._log.seek(0)
            details = self._log.read().decode(errors="replace")[-6000:]
            self.close()
            raise RuntimeError(f"{error}\nGodot log:\n{details}") from error

    def _request(self, command, **fields):
        self._request_id += 1
        self._socket.send(json.dumps({"id": self._request_id, "command": command, **fields}, allow_nan=False))
        reply = json.loads(self._socket.recv(timeout=self.timeout))
        if reply.get("protocol") != 1 or reply.get("id") != self._request_id:
            raise RuntimeError("Mismatched Godot protocol/request ID")
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply

    def _observation(self, reply):
        size = self.image_size
        if (reply.get("height"), reply.get("width")) != (size, size):
            raise RuntimeError("Godot image geometry changed")
        pixels = np.frombuffer(base64.b64decode(reply["rgb"], validate=True), dtype=np.uint8)
        if pixels.size != size * size * 3:
            raise RuntimeError("Invalid RGB payload size")
        self._pixels = pixels.reshape(size, size, 3).copy()
        return self._pixels.copy()

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if options:
            raise ValueError("No reset options supported; configure level_name in the factory")
        if self._process is None:
            self._start()
        # Keep transmitted integers exactly representable in JSON/Godot's parser.
        simulator_seed = int(self.np_random.integers(0, 2**31))
        try:
            reply = self._request("reset", seed=simulator_seed, level=self.level_name,
                                  image_size=self.image_size)
            obs = self._observation(reply)
        except Exception:
            self.close()
            raise
        self._steps = 0
        self._done = False
        return obs, {"state": reply["state"], "simulator_seed": simulator_seed, "step": 0}

    def step(self, action):
        if self._done:
            raise gym.error.ResetNeeded("Call reset() before stepping or after episode end")
        action = np.asarray(action, dtype=np.float32)
        if action.shape != (3,) or not np.isfinite(action).all() or (action < 0).any() or (action > 1).any():
            raise ValueError("Expected three finite thrusters in [0, 1]")
        try:
            reply = self._request("step", thrusters=action.tolist())
            if reply["step"] != self._steps + 1:
                raise RuntimeError("Godot step sequence mismatch")
            obs = self._observation(reply)
            reward = landing_reward(reply["state"], reply["outcome"])
        except Exception:
            self.close()
            raise
        self._steps += 1
        terminated = reply["outcome"] in ("victory", "crash")
        truncated = self._steps >= self.max_episode_steps and not terminated
        self._done = terminated or truncated
        return obs, reward, terminated, truncated, {
            "state": reply["state"], "outcome": reply["outcome"],
            "is_success": reply["outcome"] == "victory", "step": self._steps,
        }

    def render(self):
        if self._pixels is None:
            raise gym.error.ResetNeeded("Call reset() before render()")
        # No round trip, advancement, or camera change during model inference.
        return self._pixels.copy()

    def close(self):
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._process is not None:
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=3)
            self._process = None
        if self._log is not None:
            self._log.close()
            self._log = None
        self._done = True
        self._pixels = None


def make_env(render_mode="rgb_array", **kwargs):
    return RocketLandingEnv(render_mode=render_mode, **kwargs)
