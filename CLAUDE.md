# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

GodotRocketLanding (GRL) is a Godot 4.7 rocket-landing simulator whose physics is exposed over a raw
WebSocket to Python, so external agents (scripted or RL-trained) can control the rocket frame-by-frame.
The repo contains both the Godot game (GDScript, `scripts/`, `scenes/`, `shaders/`) and a Python client
library / RL training stack (`python/`) that drives it.

## Commands

### Running the game
- Godot editor: open `project.godot` with Godot **4.7.2** (Forward Plus renderer).
- Prebuilt export binaries are checked into the repo root (`GRL.exe`, `GRL.x86_64`, `GRL.pck`,
  `GRL.console.exe`, `GRL.sh`) — these are what the Python client launches as a subprocess, not build
  artifacts to regenerate casually. If you change GDScript/scenes and need the Python client to see the
  change, re-export from the Godot editor to refresh these files.
- Headless/server mode: pass `--headless`; debug logging: pass `--debug` (read in `main.gd` via
  `OS.get_cmdline_args()` and stored in the `Settings` autoload).

### Python client / RL stack
```bash
pip install -e .
# for the PPO training/eval scripts (simple_ppo.py, enjoy_ppo.py):
pip install torch tqdm

python python/simple_landing.py          # single scripted rocket, GRL client directly (no gym)
python python/batch_simple_landing.py    # runs 4 SimpleLanding instances concurrently on separate ports
python python/simple_ppo.py              # PPO training against GRLGym (gymnasium.Env wrapper)
python python/enjoy_ppo.py               # replay a trained checkpoint (path is hardcoded in the file)
```
There is no lint/test/build tooling configured in this repo (no GDScript linter; Python tests: `pytest`) — don't assume commands beyond what's listed above.

## Architecture

### Godot <-> Python bridge
- `scripts/server.gd` (`NWebSocketServer`, autoloaded as `WebSocketServer`) is a raw TCP/WebSocket server
  that accepts one peer per launched game instance and emits `message_received` / `client_connected` /
  `client_disconnected` signals.
- `scripts/actions.gd` is the **single router** for inbound JSON. Messages with an `"action"` key are
  dispatched (`hello`, `step`, `get_state`, `restart_level`, `change_level`, `set_scripted`, `set_seed`,
  `quit`); a bare dict without `"action"` is treated as a legacy `step`. Wire format, replies and the
  protocol version are documented in `docs/protocol.md` (keep `Settings.PROTOCOL_VERSION` and
  `PROTOCOL_VERSION` in `python/utils.py` in sync).
- `Actions` emits `step_requested(inputs, frame_skip)`; `scripts/main.gd` applies the inputs via
  `Rocket.set_inputs()`, unpauses the tree, lets `frame_skip` physics ticks run, re-pauses and sends **one**
  state reply. This is what makes it behave like a synchronous Gym `step()`.
- Episode end: `rocket.gd` emits `simulation_finished`; `Actions.episode_result` stores the first outcome and
  `main.get_state()` merges it (`game_state: "victory"|"crash"`) into the state, so terminal steps are still a
  single reply. `set_seed` seeds Godot's RNG; it only affects the next level load (`rocket.gd` `_ready`).
- `Settings.control_mode` toggles `"manual"` (keyboard) vs `"script"` (external control, tree paused between steps).
- The Python side is the `grl/` package (repo root, `pip install -e .`): `client.py` (`GRL` async client,
  handshake, `step`, `set_seed`, `ignition` loop calling the user's `process(state)`), `process.py`
  (`GameProcess` launches/terminates the binary, `find_binary` honours `$GRL_BINARY`, `find_free_port`),
  `env.py` (`GRLGym` base `gymnasium.Env` + ready-to-use `GRLEnv`, registered as `GRL/Landing-v0`).
  `examples/` has one runnable training script per RL library (SB3, RLlib, skrl, Tianshou, TorchRL,
  Gymnasium/CleanRL). Keep `info` keys identical on every step (Tianshou/TorchRL stack them) and don't add a
  `compute_reward` method to envs (SB3 treats it as a GoalEnv); rewards go in `get_reward`.
  A game launched with `-p` quits when its client disconnects (`Settings.launched_by_client`), so killed
  workers don't leave orphan processes.
  `python/utils.py` is only a back-compat shim for the example scripts. Tests in `tests/` use a fake
  server, so they do not exercise any GDScript.
- The committed `GRL.exe` / `GRL.x86_64` / `GRL.pck` must be re-exported from Godot 4.7 after any GDScript
  change; a stale binary never answers `hello` and the client raises with a "re-export" error.

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
