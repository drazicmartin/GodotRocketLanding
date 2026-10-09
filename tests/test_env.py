import base64
import os

import gymnasium as gym
import numpy as np
import pytest
from godot_rocket_landing import make_env
from godot_rocket_landing.env import landing_reward

STATE = dict(position=[0, -100], planet_position=[0, 1000], planet_radius=1000,
             rotation=0, linear_velocity=[0, 0], rocket_integrity=0.8)


def test_rewards():
    assert np.isfinite(landing_reward(STATE, ""))
    assert landing_reward(STATE, "victory") == pytest.approx(landing_reward(STATE, "") + 80)
    assert landing_reward(STATE, "crash") == pytest.approx(landing_reward(STATE, "") - 100)


def test_terminal_and_time_limit(monkeypatch):
    env = make_env(image_size=32, max_episode_steps=1)
    env._process = object()
    pixels = np.arange(32 * 32 * 3, dtype=np.uint8).reshape(32, 32, 3)
    response = dict(state=STATE, rgb=base64.b64encode(pixels).decode(),
                    height=32, width=32, outcome="", step=0)
    monkeypatch.setattr(env, '_request', lambda *a, **kw: response)
    observation, _ = env.reset(seed=123)
    assert env.observation_space.contains(observation)
    observation[:] = 0
    assert np.array_equal(env.render(), pixels)
    with pytest.raises(ValueError):
        env.step([0, float('nan'), 0])
    response['step'] = 1
    _, _, term, trunc, _ = env.step([0, 0, 0])
    assert not term and trunc
    with pytest.raises(gym.error.ResetNeeded):
        env.step([0, 0, 0])
    env.reset(seed=123)
    response.update(step=1, outcome='victory')
    _, _, term, trunc, info = env.step([0, 0, 0])
    assert term and not trunc and info['is_success']
    env._process = None
    env.close()
    env.close()


@pytest.mark.simulator
@pytest.mark.skipif(not os.environ.get('GRL_TEST_SIMULATOR'), reason='Set GRL_TEST_SIMULATOR=1')
@pytest.mark.parametrize("image_size", [64, 128])
def test_real_simulator(image_size):
    env = make_env(image_size=image_size, max_episode_steps=12)
    try:
        def rollout():
            obs, info = env.reset(seed=123)
            frames, states = [obs], [info['state']]
            for _ in range(12):
                obs, reward, term, trunc, info = env.step([0.7, 0.0, 0.0])
                assert np.isfinite(reward)
                assert info['state']['num_frame_computed'] == states[-1]['num_frame_computed'] + 1
                assert np.array_equal(obs, env.render())
                frames.append(obs)
                states.append(info['state'])
                if term or trunc:
                    break
            return frames, states
        a, sa = rollout()
        b, sb = rollout()
        assert sa == sb
        assert all(np.array_equal(x, y) for x, y in zip(a, b))
        assert len(a) > 2 and not np.array_equal(a[0], a[-1])
        assert np.std(a[0]) > 5  # Reject blank or dummy-driver captures.
        pid = env._process.pid
    finally:
        proc = env._process
        env.close()
    assert proc.poll() is not None


@pytest.mark.simulator
@pytest.mark.skipif(not os.environ.get('GRL_TEST_SIMULATOR'), reason='Set GRL_TEST_SIMULATOR=1')
def test_current_action_changes_current_response():
    # Catches Godot's one-tick-late node transform synchronization.
    with make_env(image_size=64, level_name='level_1') as env:
        env.reset(seed=123)
        *_, coast = env.step([0, 0, 0])
        env.reset(seed=123)
        *_, thrust = env.step([1, 0, 0])
        assert thrust['state']['linear_velocity'][1] < coast['state']['linear_velocity'][1]
        assert thrust['state']['position'][1] < coast['state']['position'][1]


@pytest.mark.simulator
@pytest.mark.skipif(not os.environ.get('GRL_TEST_SIMULATOR'), reason='Set GRL_TEST_SIMULATOR=1')
def test_real_terminal_and_reset():
    with make_env(image_size=64, level_name='level_1', max_episode_steps=600) as env:
        env.reset(seed=4)
        for _ in range(600):
            pixels, reward, term, trunc, info = env.step([0, 0, 0])
            if term or trunc:
                break
        assert term and not trunc
        assert info['outcome'] in ('victory', 'crash')
        assert np.array_equal(pixels, env.render())
        with pytest.raises(gym.error.ResetNeeded):
            env.step([0, 0, 0])
        _, reset_info = env.reset(seed=4)
        assert reset_info['step'] == 0
        env.step([0, 0, 0])
