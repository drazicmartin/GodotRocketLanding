# GRL WebSocket protocol (version 1)

Transport: one WebSocket per game instance (`ws://127.0.0.1:<port>`, port set with `-p`), JSON text frames.
`Settings.PROTOCOL_VERSION` (Godot) and `PROTOCOL_VERSION` (`python/utils.py`) must match; the Python client
checks it on connect and raises if the binary is older or newer.

All control messages are `{"action": ..., ...}`. Replies are one JSON object each.

| Request | Reply |
|---|---|
| `{"action":"hello"}` | `{"ack":"hello","protocol":1}` |
| `{"action":"change_level","level_name":"level_1"}` | `{"ack":"change_level"}` (also sent if already on that level) |
| `{"action":"set_scripted"}` | none (pauses physics at once, 30 ticks/s, stepped by the client) |
| `{"action":"set_seed","seed":42}` | none; seeds Godot's RNG, applied by the next `restart_level`/`change_level` |
| `{"action":"restart_level"}` | `{"ack":"restart_level"}` (send `get_state` afterwards for the first observation) |
| `{"action":"get_state"}` | state |
| `{"action":"step","inputs":{...},"frame_skip":1}` | state, exactly one reply |
| `{"action":"quit"}` | none |

A bare dict of inputs (no `"action"`) is still accepted and means `step` with `frame_skip` 1.

## Inputs
`main_thrust`, `rcs_left_thrust`, `rcs_right_thrust`: float in `[0, 1]` (clamped; missing keys default to 0).

## State
Vectors are `[x, y]` lists. `planet_mass` is a scientific-notation string (e.g. `"2e24"`, too large for a JSON number
in Godot's `Big` class); the Python client converts it to `float`.

When the episode ended during the step, the same state also carries `"game_state": "victory" | "crash"`
(plus `"score"` on victory). That is the *terminated* signal; truncation (time limits) is decided by the client.
Stepping again after the end replies immediately with the final state.

## Speed
Physics runs at 30 ticks per step of simulated time. Headless instances launched by the Python client get
`--fixed-fps 30`, which makes Godot run frames back-to-back instead of waiting for real time (about 60x faster:
~900 steps/s vs ~15 measured on one instance). Windowed instances (`show_window=True`) stay real-time so you can
watch them. The fixed step must stay equal to `1 / physics_ticks_per_second` (set in `set_scripted`).
