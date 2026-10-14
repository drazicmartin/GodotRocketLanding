"""Client-side protocol tests against a fake Godot server (no game binary needed)."""
import asyncio
import json
import sys
import threading
from pathlib import Path

import numpy as np
import pytest
from gymnasium import spaces
from websockets.asyncio.server import serve

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grl import GRL, GRLEnv, GRLGym, PROTOCOL_VERSION  # noqa: E402


def fake_state(frame, game_state=None):
    state = {
        "position": [float(frame), -100.0],
        "linear_velocity": [0.0, 1.0],
        "angular_velocity": 0.0,
        "rotation": 0.0,
        "num_frame_computed": frame,
        "rocket_integrity": 1.0,
        "propellant": 1.0,
        "temperature": 300.0,
        "mass": 1.0,
        "left_leg_contact": False,
        "right_leg_contact": False,
        "wind_force": 0.0,
        "wind_direction": [1.0, 0.0],
        "planet_radius": 50000.0,
        "planet_atmosphere_size": 600.0,
        "planet_mass": "2e24",
        "planet_position": [0.0, 50000.0],
        "landing_pad_position": [300.0, 0.0],
        "landing_pad_width": 90.0,
        "landing_pad_distance": 300.0 - frame,
        "on_landing_pad": False,
        "legs_deployed": True,
        "legs_extension": 1.0,
        "settle_time": 0.0,
    }
    if game_state:
        state["game_state"] = game_state
    return state


class FakeGame:
    """Speaks protocol v1: one reply per step, crash after `crash_after` frames."""

    def __init__(self, protocol=PROTOCOL_VERSION, crash_after=3, answer_hello=True):
        self.protocol = protocol
        self.crash_after = crash_after
        self.answer_hello = answer_hello
        self.frame = 0
        self.seeds = []
        self.received = []

    async def handler(self, ws):
        async for raw in ws:
            msg = json.loads(raw)
            self.received.append(msg)
            action = msg.get("action")
            if action == "hello":
                if self.answer_hello:
                    await ws.send(json.dumps({"ack": "hello", "protocol": self.protocol}))
            elif action == "change_level":
                await ws.send(json.dumps({"ack": "change_level"}))
            elif action == "set_seed":
                self.seeds.append(msg["seed"])
            elif action == "restart_level":
                self.frame = 0
                await ws.send(json.dumps({"ack": "restart_level"}))
            elif action == "get_state":
                await ws.send(json.dumps(fake_state(self.frame)))
            elif action == "step":
                self.frame += msg["frame_skip"]
                crashed = self.frame >= self.crash_after
                await ws.send(json.dumps(fake_state(self.frame, "crash" if crashed else None)))


async def start(game):
    server = await serve(game.handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def start_in_thread(game):
    """Run the fake server on its own loop so blocking gym code can run on the main thread."""
    ready = threading.Event()
    box = {}

    def target():
        async def main():
            server, box["port"] = await start(game)
            ready.set()
            await asyncio.Event().wait()

        asyncio.run(main())

    threading.Thread(target=target, daemon=True).start()
    ready.wait(5)
    return box["port"]


def run(coro):
    return asyncio.run(coro)


def test_handshake_and_step_returns_single_reply():
    async def go():
        game = FakeGame()
        server, port = await start(game)
        client = GRL(port=port)
        await client.connect()
        state = await client.step({"main_thrust": 1.0})
        assert state["position"] == [1.0, -100.0]
        assert state["planet_mass"] == 2e24
        assert "game_state" not in state
        sent = [m for m in game.received if m["action"] == "step"][0]
        assert sent == {"action": "step", "inputs": {"main_thrust": 1.0}, "frame_skip": 1}
        server.close()

    run(go())


def test_protocol_mismatch_fails_loudly():
    async def go():
        server, port = await start(FakeGame(protocol=PROTOCOL_VERSION + 1))
        with pytest.raises(RuntimeError, match="Protocol mismatch"):
            await GRL(port=port).connect()
        server.close()

    run(go())


def test_old_binary_without_hello_times_out():
    async def go():
        server, port = await start(FakeGame(answer_hello=False))
        client = GRL(port=port)
        import websockets

        client.websocket = await websockets.connect(client.uri)
        with pytest.raises(RuntimeError, match="re-export"):
            await client.handshake(timeout=0.2)
        server.close()

    run(go())


class FakeGymEnv(GRLGym):
    observation_space_names = ["position", "linear_velocity", "propellant"]
    observation_space_dict = {
        "position": {"low": [-1e4, -1e4], "high": [1e4, 1e4]},
        "linear_velocity": {"low": [-1e3, -1e3], "high": [1e3, 1e3]},
        "propellant": {"low": [0], "high": [1]},
    }

    def __init__(self, port, **kw):
        super().__init__(port=port, **kw)
        self.action_space = spaces.Discrete(2)

    def setup_observation_space(self):
        self.define_observation_space()

    async def async_start(self):  # the fake server is already running, don't launch a binary
        await self.env.connect()
        await self.env.change_level(self.level_name)
        await self.env.set_scripted()

    def decode_action(self, action):
        return {"main_thrust": float(action), "rcs_left_thrust": 0.0, "rcs_right_thrust": 0.0}

    def get_reward(self, state, obs, terminated, truncated):
        return 1.0


def test_gym_episode_terminates_on_single_reply_and_resets():
    game = FakeGame(crash_after=3)
    port = start_in_thread(game)
    env = FakeGymEnv(port=port)
    obs, _ = env.reset(seed=7)
    assert obs.shape == (5,) and obs.dtype == np.float32  # custom obs subset
    done = False
    steps = 0
    while not done:
        obs, reward, done, trunc, state = env.step(np.int64(1))
        steps += 1
    assert steps == 3 and state["game_state"] == "crash"
    # no stray terminal message left in the pipe: a second episode starts cleanly
    obs, _ = env.reset(seed=8)
    assert obs[0] == 0.0
    assert game.seeds == [7, 8]


def test_frame_skip_is_forwarded():
    async def go():
        game = FakeGame(crash_after=100)
        server, port = await start(game)
        client = GRL(port=port)
        await client.connect()
        state = await client.step({}, frame_skip=4)
        assert state["num_frame_computed"] == 4
        server.close()

    run(go())


class FakeLandingEnv(GRLEnv):
    async def async_start(self):  # the fake server is already running, don't launch a binary
        await self.env.connect()
        await self.env.change_level(self.level_name)
        await self.env.set_scripted()


def test_default_env_passes_gymnasium_checker_and_truncates():
    from gymnasium.utils.env_checker import check_env

    port = start_in_thread(FakeGame(crash_after=10_000))
    env = FakeLandingEnv(port=port, max_steps=3)
    check_env(env, skip_render_check=True)
    env.reset(seed=1)
    flags = [env.step(env.action_space.sample())[2:4] for _ in range(3)]
    assert flags == [(False, False), (False, False), (False, True)]


def test_default_env_terminates_with_crash_reward():
    port = start_in_thread(FakeGame(crash_after=2))
    env = FakeLandingEnv(port=port, discrete_actions=True)
    env.reset()
    env.step(1)
    _, reward, terminated, truncated, info = env.step(0)
    assert terminated and not truncated and reward == -100.0 and info["game_state"] == "crash"


def test_registered_id():
    import gymnasium as gym

    assert "GRL/Landing-v0" in gym.registry


def test_process_helpers(tmp_path, monkeypatch):
    from grl.process import BINARY_ENV_VAR, find_binary, find_free_port

    fake = tmp_path / "game.bin"
    fake.write_text("")
    monkeypatch.setenv(BINARY_ENV_VAR, str(fake))
    assert find_binary() == fake
    assert 0 < find_free_port() < 65536


def test_info_keys_are_stable_and_actions_are_symmetric():
    port = start_in_thread(FakeGame(crash_after=2))
    env = FakeLandingEnv(port=port)
    _, info0 = env.reset()
    _, _, _, _, info1 = env.step(np.zeros(3, dtype=np.float32))
    _, _, terminated, _, info2 = env.step(np.zeros(3, dtype=np.float32))
    # Tianshou/TorchRL stack infos: every step must carry the same keys
    assert set(info0) == set(info1) == set(info2)
    assert (info1["game_state"], info2["game_state"], info2["is_success"]) == ("running", "crash", False)
    assert terminated
    assert env.decode_action(np.array([-1.0, 0.0, 1.0, 1.0])) == {
        "main_thrust": 0.0, "rcs_left_thrust": 0.5, "rcs_right_thrust": 1.0, "legs": 1.0}


def test_config_file_is_written_and_passed(tmp_path, monkeypatch):
    from grl.config import resolve_config, write_config
    from grl.process import GameProcess

    path = write_config({"camera": {"zoom": 0.25}, "misc": {"name": "a b", "flag": True}}, tmp_path / "g.cfg")
    assert path.read_text() == '[camera]\nzoom=0.25\n\n[misc]\nname="a b"\nflag=true\n'
    assert resolve_config(path) == path

    launched = {}
    monkeypatch.setattr("subprocess.Popen", lambda cmd, cwd=None: launched.setdefault("cmd", cmd))
    fake = tmp_path / "game.bin"
    fake.write_text("")
    game = GameProcess(1234, binary=fake, config={"camera": {"zoom": 0.5}})
    game.start()
    game.proc = None  # nothing real to terminate at exit
    cmd = launched["cmd"]
    cfg = Path(cmd[cmd.index("--config") + 1])
    assert "zoom=0.5" in cfg.read_text()


def test_rgb_array_render_last_state_and_checker():
    from gymnasium.utils.env_checker import check_env

    with pytest.raises(ValueError, match="render_mode"):
        GRLEnv(render_mode="rgb")
    assert FakeLandingEnv(port=1).render() is None   # no render_mode: nothing to draw, nothing launched
    port = start_in_thread(FakeGame(crash_after=10_000))
    env = FakeLandingEnv(port=port, render_mode="rgb_array", render_size=48, frame_skip=2)
    assert env.metadata["render_fps"] == 15 and GRLEnv.metadata["render_fps"] == 30
    with pytest.raises(RuntimeError, match="reset"):
        env.render()
    check_env(env)
    _, info = env.reset(seed=3)
    assert env.last_state["position"] == info["position"]
    idle = env.render()
    assert idle.shape == (48, 48, 3) and idle.dtype == np.uint8
    env.step(np.array([1.0, -1.0, -1.0, 1.0], dtype=np.float32))
    assert env.last_state["num_frame_computed"] == 2
    assert not np.array_equal(env.render(), idle)
    env.close()


def lander_state(**overrides):
    state = fake_state(0)
    state.update({"planet_mass": 4e18, "position": [0.0, -140.0], "linear_velocity": [0.0, 0.0],
                  "mass": 9.9, "landing_pad_distance": 800.0, "legs_extension": 0.0, "legs_deployed": False})
    state.update(overrides)
    return state


def test_scripted_lander():
    from grl.policies import ScriptedLander, gravity, local_frame

    # measured in level_1 (rocket 100 px above the default planet): 16.42 px/s^2
    assert gravity(lander_state(position=[0.0, -100.0])) == pytest.approx(16.42, abs=0.01)
    altitude, v_right, v_up, tilt, spin = local_frame(lander_state(linear_velocity=[3.0, -2.0], rotation=0.1))
    assert (altitude, v_right, v_up, tilt) == pytest.approx((140.0, 3.0, 2.0, 0.1))
    action = ScriptedLander().act(lander_state())
    assert action.shape == (4,) and action.dtype == np.float32 and np.all(np.abs(action) <= 1)
    assert action[1] > -1.0 and action[2] == -1.0 and action[3] == -1.0   # lean right towards the pad, legs up
    assert -1.0 < action[0] < 0.0   # about a quarter of the thrust to hover
    landed = lander_state(landing_pad_distance=5.0, left_leg_contact=True, right_leg_contact=True)
    assert ScriptedLander().act(landed).tolist() == [-1.0, -1.0, -1.0, 1.0]
    a, b = ScriptedLander(noise=0.3, seed=1), ScriptedLander(noise=0.3, seed=1)
    assert all(np.array_equal(a.act(lander_state()), b.act(lander_state())) for _ in range(50))
    with pytest.raises(ValueError):
        ScriptedLander(noise=-1)


def test_demonstrator_reads_the_env_state():
    from grl.policies import demonstrator

    with pytest.raises(ValueError, match="Box"):
        demonstrator(FakeLandingEnv(port=1, discrete_actions=True))
    port = start_in_thread(FakeGame(crash_after=10_000))
    env = FakeLandingEnv(port=port)
    policy = demonstrator(env, noise=0.0)
    with pytest.raises(RuntimeError, match="reset"):
        policy.act()
    env.reset(seed=0)
    policy.reset()
    action = policy.act(np.zeros((8, 8, 3)))   # the observation is ignored
    assert env.action_space.contains(action)
    env.step(action)
    env.close()


def test_binary_checks_and_exited_game(tmp_path):
    import os

    from grl.process import check_binary

    pointer = tmp_path / "GRL.exe"
    pointer.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:0\nsize 1\n")
    with pytest.raises(RuntimeError, match="git lfs pull"):
        check_binary(pointer)
    binary = tmp_path / "GRL.x86_64"
    binary.write_bytes(b"\x7fELF")
    binary.chmod(0o644)
    check_binary(binary)
    if os.name == "posix":
        assert os.access(binary, os.X_OK)

    class ExitedGame:
        def exit_code(self):
            return 1

    async def go():
        from grl.process import find_free_port

        client = GRL(port=find_free_port())
        client.game = ExitedGame()
        with pytest.raises(RuntimeError, match="exited"):
            await client.connect(retries=3, delay=0.01)

    run(go())
