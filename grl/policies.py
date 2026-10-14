"""Scripted landing controller that reads the full game state.

A baseline for `GRLEnv`, and a source of demonstrations for agents that learn from other data than their own:
random thrust mostly flies the rocket away, so it never shows a landing (e.g. world models trained on
pixels, see `demonstrator`).
"""
import math
from typing import Mapping, Optional

import numpy as np

# Physics constants from the Godot scripts (rocket.gd, planet.gd, settings.gd)
MAX_THRUST = 69_900_000 * 1e-5      # MAX_THRUST_POWER * THRUST_SCALE
LEG_MAIN_THRUST_PENALTY = 0.15
G = 6.674
DIST_SCALE = 2.5e5
FOOT_ALTITUDE = 12.0                # hull origin altitude when the deployed feet touch the ground


def gravity(state: Mapping) -> float:
    """Gravitational acceleration (px/s^2) at the rocket, as computed by planet.gd."""
    rel = np.subtract(state["position"], state["planet_position"])
    radius = float(state["planet_radius"])
    # planet.gd: (|planet - rocket| - 0.95 R) + 0.05 R, i.e. altitude + 0.1 R
    distance = (float(np.hypot(*rel)) - 0.9 * radius) * DIST_SCALE
    return G * float(state["planet_mass"]) / distance ** 2


def local_frame(state: Mapping):
    """Altitude, velocity (right, up), tilt (rad, > 0 leans right) and spin in the frame of the local vertical."""
    rel = np.subtract(state["position"], state["planet_position"]).astype(float)
    dist = float(np.hypot(*rel)) or 1.0
    up = rel / dist
    right = np.array([-up[1], up[0]])
    velocity = np.asarray(state["linear_velocity"], dtype=float)
    tilt = float(state["rotation"]) - (math.atan2(up[1], up[0]) + math.pi / 2.0)
    tilt = (tilt + math.pi) % (2.0 * math.pi) - math.pi
    return (dist - float(state["planet_radius"]), float(velocity @ right), float(velocity @ up), tilt,
            float(state["angular_velocity"]))


class ScriptedLander:
    """Cruises to the pad, descends onto it with the legs down, and cuts the engine once on it.

    `act(state)` returns an action for `GRLEnv`'s Box(4) action space ([-1, 1]: main, rcs_left, rcs_right,
    legs). `noise` (>= 0) adds Gaussian noise of that standard deviation to the thrusters and, with probability
    `noise / 20` per step, starts a burst of 5-25 steps of random thrust, so demonstrations also show misses,
    recoveries and crashes. `noise=0` is deterministic.

    Tuned on `random_level_easy` (50 000 px planet) with `frame_skip=5`, seeds 0-29 and 500 steps (83 s):
    28 land (median 48 s), one times out, one starts in an unrecoverable dive; 22 land with `noise=0.1`.
    The feet have no sideways friction, so the rocket must touch down without horizontal speed or it slides
    off the pad.
    """

    cruise_altitude = 140.0   # px, hull origin above the surface while flying to the pad
    max_speed = 90.0          # px/s, horizontal
    max_tilt = 0.6            # rad from the local vertical
    attitude_lag = 2.0        # s, the attitude loop is slow: lead the horizontal speed by the current tilt

    def __init__(self, noise: float = 0.0, seed: Optional[int] = None):
        if noise < 0:
            raise ValueError("noise must be >= 0")
        self.noise = float(noise)
        self.rng = np.random.default_rng(seed)
        self.burst = 0
        self.descending = False

    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        self.burst = 0
        self.descending = False

    def act(self, state: Mapping) -> np.ndarray:
        action = self.control(state)
        if self.noise > 0:
            if self.burst == 0 and self.rng.random() < self.noise / 20.0:
                self.burst = int(self.rng.integers(5, 26))
            if self.burst > 0:
                self.burst -= 1
                action[:3] = self.rng.uniform(-1.0, 1.0, 3)
            else:
                action[:3] += self.rng.normal(0.0, self.noise, 3)
        return np.clip(action, -1.0, 1.0).astype(np.float32)

    def control(self, state: Mapping) -> np.ndarray:
        altitude, v_right, v_up, tilt, spin = local_frame(state)
        pad = float(state.get("landing_pad_distance", 0.0))
        half_pad = float(state.get("landing_pad_width", 90.0)) / 2.0
        legs_extension = float(state.get("legs_extension", 0.0))
        legs = 1.0 if abs(pad) < 250.0 or altitude < 60.0 else -1.0
        if state.get("left_leg_contact") and state.get("right_leg_contact") and abs(pad) < half_pad:
            return np.array([-1.0, -1.0, -1.0, 1.0])   # on the pad: engine off, let it settle

        # Descend once above the pad and slow; give up (climb back) only when drifting off it
        if not self.descending:
            self.descending = abs(pad) < 20.0 and abs(v_right) < 6.0
        elif abs(pad) > 40.0:
            self.descending = False

        # Horizontal: a speed towards the pad that can still be braked, reached by leaning
        target_v = math.copysign(min(self.max_speed, 0.7 * math.sqrt(14.0 * abs(pad)), 0.35 * abs(pad)), pad)
        if self.descending and altitude < 60.0:
            target_v = 0.0
        g = gravity(state)
        predicted_v = v_right + g * math.tan(float(np.clip(tilt, -1.2, 1.2))) * self.attitude_lag
        max_tilt = self.max_tilt * float(np.clip((altitude - 20.0) / 150.0, 0.15, 1.0))   # upright near ground
        target_tilt = float(np.clip(0.018 * (target_v - predicted_v), -max_tilt, max_tilt))
        # Attitude: spin towards the target tilt no faster than the RCS can stop it (~0.15 rad/s^2 with the
        # legs down). rcs_left turns clockwise (leans right), rcs_right counter-clockwise.
        error = target_tilt - tilt
        target_spin = math.copysign(min(0.5, 0.8 * math.sqrt(0.3 * abs(error)), 1.5 * abs(error)), error)
        torque = float(np.clip(4.0 * (target_spin - spin), -1.0, 1.0))

        # Vertical: hold the cruise altitude, or descend slower and slower down to the ground
        if self.descending:
            target_up = -float(np.clip(0.8 * (altitude - FOOT_ALTITUDE), 4.0, 40.0))
        else:
            target_up = float(np.clip(0.8 * (self.cruise_altitude - altitude), -40.0, 40.0))
        accel = g + 1.5 * (target_up - v_up)
        max_accel = MAX_THRUST / float(state["mass"]) * (1.0 - LEG_MAIN_THRUST_PENALTY * legs_extension)
        main = float(np.clip(accel / (max_accel * max(math.cos(tilt), 0.3)), 0.0, 1.0))
        return np.array([2.0 * main - 1.0, 2.0 * max(torque, 0.0) - 1.0, 2.0 * max(-torque, 0.0) - 1.0, legs])


class _EnvPolicy:
    """A ScriptedLander bound to an env: `act()` ignores its argument and reads the env's latest state."""

    def __init__(self, env, lander: ScriptedLander):
        self.env = env.unwrapped
        self.lander = lander

    def reset(self) -> None:
        self.lander.reset()

    def act(self, observation=None) -> np.ndarray:
        state = self.env.last_state
        if state is None:
            raise RuntimeError("reset() the env before asking for an action")
        return self.lander.act(state)


def demonstrator(env, noise: float = 0.1, seed: Optional[int] = 0):
    """Noisy ScriptedLander for collecting demonstrations from any pipeline that owns the env.

    Returns an object with `reset()` and `act(observation)`: the observation (pixels, vector, ...) is ignored,
    actions come from `env.last_state`. Needs the Box(4) action space (`discrete_actions=False`).
    """
    if getattr(env.unwrapped, "discrete_actions", False):
        raise ValueError("demonstrator needs the continuous Box(4) action space (discrete_actions=False)")
    return _EnvPolicy(env, ScriptedLander(noise=noise, seed=seed))
