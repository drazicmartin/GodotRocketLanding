# Pixel training with world_model

This integration starts from **dev commit 28955706a4e5e69a65f23022bbaee3993d2fb13e**.
It also includes the subsequent dev socket fix at `a490566`.
It runs the actual Godot scenes and physics and captures the Godot viewport; no
telemetry-to-image substitute or Python physics surrogate is used.

## Install

Use Godot **4.3 stable**, Python 3.11 (3.12 also tested), Git, and the same Python
virtual environment as `world_model`. The checked-in `GRL.exe`, `GRL.x86_64` and
`GRL.pck` predate this protocol. The adapter deliberately launches Godot against
`project.godot` instead of using those exports. No re-export is needed.

```bash
# In your world_model virtual environment, after checking out this patched repo:
python -m pip install -e /absolute/path/to/GodotRocketLanding
export GODOT_BIN=/absolute/path/to/Godot_v4.3-stable_linux.x86_64
export GRL_PROJECT_PATH=/absolute/path/to/GodotRocketLanding
# Import original assets once. Headless mode is safe for asset import only.
"$GODOT_BIN" --headless --path "$GRL_PROJECT_PATH" --editor --import --quit
```

On Windows PowerShell use `$env:GODOT_BIN = 'C:\path\Godot_v4.3-stable_win64.exe'`
and `$env:GRL_PROJECT_PATH = 'C:\path\GodotRocketLanding'`. Windows instructions
are provided but execution has only been tested on Linux.

The default project path is the editable package's repository root. Use
`GRL_PROJECT_PATH` explicitly for wheels or moved installations. The project and
Godot executable must exist on every collection/evaluation machine; offline
training and offline model evaluation only need the saved dataset.

## Linux servers without a desktop

Install `xvfb`, `xauth`, and Mesa OpenGL drivers using your operating system's
package manager. Prefix **collection, online evaluation, inference, and simulator
tests** with `xvfb-run -a`. Optionally set `LIBGL_ALWAYS_SOFTWARE=1` for Mesa CPU
rendering. Do **not** pass `--headless` during RGB collection: Godot's dummy
renderer cannot supply training pixels. Training itself does not need a display.

## End-to-end smoke run

Run these from your `world_model` checkout, after installing both packages:

```bash
world-model collect --config "$GRL_PROJECT_PATH/configs/world_model_smoke.json" --output data/grl-smoke
world-model train --config "$GRL_PROJECT_PATH/configs/world_model_smoke.json" --data data/grl-smoke --output runs/grl-smoke --device cpu
world-model eval-model --checkpoint runs/grl-smoke/best.pt --data data/grl-smoke --horizon 3 --output runs/grl-smoke/model-eval.json
world-model eval --checkpoint runs/grl-smoke/best.pt --episodes 2 --output runs/grl-smoke/mpc-eval.json
world-model eval --checkpoint runs/grl-smoke/best.pt --episodes 2 --random --output runs/grl-smoke/random-eval.json
python -m examples.inference --checkpoint runs/grl-smoke/best.pt
```

For a server, for example: `xvfb-run -a world-model collect ...`.
Output paths must be new. The smoke config verifies plumbing, not landing skill.
For longer experiments start with `configs/world_model.json`, inspect trajectories,
and tune data coverage and planner cost. Random thruster actions rarely land
successfully; a useful controller needs adequate successful and failure examples.

## Contract and semantics

```python
from godot_rocket_landing import make_env

env = make_env(render_mode="rgb_array")
try:
    observation, info = env.reset(seed=123)
    pixels, reward, terminated, truncated, info = env.step([0.7, 0.0, 0.0])
    rgb = env.render()  # uint8 [128, 128, 3], cached; never advances physics
finally:
    env.close()
```

- Factory: `godot_rocket_landing:make_env`; no world_model source change needed.
- Actions: float32 `Box(0, 1, (3,))`, ordered main, left RCS, right RCS. Invalid
  shapes, NaNs, and out-of-bounds actions are rejected rather than clipped.
- Observations and render: independent copies of the same post-step RGB image.
  `world_model` ignores the returned observation and reads `render()` only.
- One adapter step advances one physics tick at 30 Hz. The bridge synchronizes
  the completed physics-server transform and velocities before capturing the
  scene, avoiding Godot node properties that normally lag until the next tick. World_model's
  `action_repeat` controls how many such ticks form one training transition.
- Reset seeds Godot before level instantiation. Python derives the simulator seed
  deterministically from Gymnasium's RNG and returns it in reset info. Test seeds
  reproduce local trajectories; cross-platform bitwise physics is not promised.
- Camera: 640×640 source viewport, rocket-following translation, world-aligned
  rotation, no camera smoothing. Image downsampling is fixed in the config.
  Particles and sprite animation are disabled in this opt-in mode so wall-clock
  inference delays cannot animate observations. Original art and scene objects
  remain visible. Keep this camera contract fixed between training and deployment.
- Victory/crash are true terminals from the upstream simulator; a Python step
  budget is a truncation. No autoreset: terminal images belong to the ending
  episode, and step after any end requires reset.
- Reward v1: negative per-step cost for speed, tilt, and altitude, plus
  `100 * remaining_integrity` on victory and `-100` on crash. It is explicitly
  defined in `landing_reward`; the policy/model receives pixels, not telemetry.
  Changing reward semantics requires recollection/retraining of outcome heads.
- `info` exposes telemetry, outcome, success flag, and step number for debugging.
- Each environment owns a subprocess and connection, selects a free port by
  default, bounds RPC waits, validates protocol/request IDs, and cleans up on
  failures/close. Separate environments are required for parallel workers.
- The training server binds to localhost. The legacy WebSocket protocol and
  interactive mode retain their previous defaults unless `--world-model` is set.

## Source audit and scope

`dev` contains source, unlike `main`. The existing `python/utils.py` has no RGB
render implementation, ignores simulator reset seeds, relies on a process-global
asyncio event loop, launches binaries relative to the working directory, and does
not retain a process handle for reliable cleanup. Its legacy terminal protocol
uses separate messages, which can become misaligned if a client assumes every
packet is a normal state. The new package leaves existing example clients intact
and uses one versioned response containing pixels, telemetry, outcome, and step.

The new autoload is enabled only by a launch flag. Small guards in `main.gd`,
`actions.gd`, and `main_menu.gd` prevent the legacy protocol from also driving the
same scene. The upstream landing/crash rules and force/thermal/wind models are
preserved. In particular, a victory means upstream's leg-contact rule, not a new
validated physical touchdown criterion. Success rates should be interpreted in
that context.

## Tests

```bash
python -m pip install -e '.[test]'
python -m pytest -q
GRL_TEST_SIMULATOR=1 xvfb-run -a python -m pytest -q
```

The opt-in real-simulator test checks reproducible seeded states/images,
one-tick frame counts, nonblank and changing RGB, time limits, and child cleanup.
See `validation.json` for the actual checks and results from this change.
