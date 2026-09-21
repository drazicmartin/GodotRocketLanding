# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

GodotRocketLanding (GRL) is a Godot 4.3 rocket-landing simulator whose physics is exposed over a raw
WebSocket to Python, so external agents (scripted or RL-trained) can control the rocket frame-by-frame.
The repo contains both the Godot game (GDScript, `scripts/`, `scenes/`, `shaders/`) and a Python client
library / RL training stack (`python/`) that drives it.

## Commands

### Running the game
- Godot editor: open `project.godot` with Godot **4.3** (Forward Plus renderer).
- Prebuilt export binaries are checked into the repo root (`GRL.exe`, `GRL.x86_64`, `GRL.pck`,
  `GRL.console.exe`, `GRL.sh`) — these are what the Python client launches as a subprocess, not build
  artifacts to regenerate casually. If you change GDScript/scenes and need the Python client to see the
  change, re-export from the Godot editor to refresh these files.
- Headless/server mode: pass `--headless`; debug logging: pass `--debug` (read in `main.gd` via
  `OS.get_cmdline_args()` and stored in the `Settings` autoload).

### Python client / RL stack
```bash
pip install websockets gymnasium
# for the PPO training/eval scripts (simple_ppo.py, enjoy_ppo.py):
pip install torch tqdm

python python/simple_landing.py          # single scripted rocket, GRL client directly (no gym)
python python/batch_simple_landing.py    # runs 4 SimpleLanding instances concurrently on separate ports
python python/simple_ppo.py              # PPO training against GRLGym (gymnasium.Env wrapper)
python python/enjoy_ppo.py               # replay a trained checkpoint (path is hardcoded in the file)
```
There is no lint/test/build tooling configured in this repo (no `requirements.txt`, no CI, no GDScript
linter, no test suite) — don't assume commands beyond what's listed above.

## Architecture

### Godot <-> Python bridge
- `scripts/server.gd` (`NWebSocketServer`, class autoloaded as `WebSocketServer`) is a raw TCP/WebSocket
  server (not Godot's higher-level `WebSocketMultiplayerPeer`) that accepts one peer per launched game
  instance and emits `message_received` / `client_connected` / `client_disconnected` signals.
- Every inbound message is JSON. Two receivers decide what a message means based on shape:
  - `scripts/actions.gd`: messages with an `"action"` key (`get_state`, `restart_level`, `set_scripted`,
    `change_level`, `quit`). These are meta/control commands, not physics inputs.
  - `scripts/main.gd`: messages *without* an `"action"` key are treated as rocket thruster inputs
    (`main_thrust`, `rcs_left_thrust`, `rcs_right_thrust`) and applied via `Rocket.set_inputs()`.
- `Settings.control_mode` (autoload `scripts/settings.gd`) toggles `"manual"` (keyboard, for humans) vs
  `"script"` (external control). In `"script"` mode the tree is kept paused and advanced exactly one
  physics step per received input via `main.gd`'s `allow_one_physics_step()` — this is what makes the
  simulation behave like a synchronous Gym `step()` call: client sends action -> one physics tick runs ->
  server sends back the resulting state.
- `python/utils.py` is the client-side mirror of this protocol:
  - `GRL` (ABC): low-level async websocket client. Launches the exported binary as a subprocess
    (`start_game`), speaks the JSON action/state protocol, and drives a scripted loop via `ignition()`,
    which repeatedly calls the user-supplied `process(state) -> action` method.
  - `GRLGym` (ABC, extends `gymnasium.Env`): wraps `GRL` as a standard Gym environment (`reset`/`step`
    close over asyncio via `run_until_complete`). Subclasses must implement `compute_reward`,
    `get_reward`, and observation-space config (`observation_space_dict` / `observation_space_names`).
  - `simple_landing.py` and `batch_simple_landing.py` show the low-level `GRL` usage pattern (subclass +
    override `process`); `simple_ppo.py`/`enjoy_ppo.py` show the `GRLGym` + PPO training pattern.

### Simulation core (scripts/)
- `rocket.gd` (`RigidBody2D`): owns all rocket physics — thrust/RCS forces, propellant consumption and
  mass updates, atmospheric drag/heating/hull-stress damage model, leg-contact/landing/crash detection,
  and `get_state()` (the dict serialized back to Python). `set_inputs()`/`sanitize_input()` is the only
  entry point for external control; inputs are clamped to `[0, 1]` and zeroed once `propellant <= 0`.
- `planet.gd` (`StaticBody2D`): dynamic gravity (Newtonian, via `Big.gd` for the huge mass values) and an
  exponential-atmosphere model (density/temperature/drag by altitude) shared by `rocket.gd`'s
  drag/thermal calculations and the atmosphere shader.
- `wind.gd`: raycasts around the rocket to apply directional wind force; independent of the planet's
  atmosphere model.
- `scripts/Big.gd`: arbitrary-precision (mantissa/exponent) number class used for planet mass so gravity
  math doesn't overflow `float`/`int`; see `Settings.MASS_SCALE`/`DIST_SCALE`/`THRUST_SCALE` for the
  scale factors used to keep everything else in normal float range.
- `main_menu.gd` / level scenes (`scenes/level_*.tscn`, `scenes/random_level_*.tscn`) select which
  planet/rocket/wind configuration loads; `Actions.change_level()` / `restart_level()` is how both humans
  (Escape/Restart keybinds) and the Python client (`change_level`/`restart_level` actions) switch levels.

### Rocket control surface (matches README's documented protocol)
Inputs: `main_thrust`, `rcs_left_thrust`, `rcs_right_thrust` (each `float` in `[0, 1]`).
State (`Rocket.get_state()` merged with `Wind.get_state()` and `Planet.get_state()` in `main.gd`):
position, linear/angular velocity, rotation, frame count, integrity, propellant, temperature, mass,
leg-contact flags, wind, planet radius/mass/atmosphere/position.
