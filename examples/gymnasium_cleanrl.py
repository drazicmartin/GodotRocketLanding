"""Plain Gymnasium vector env: the base for CleanRL-style single-file scripts.

CleanRL scripts (e.g. ppo_continuous_action.py) build their envs with a `make_env` thunk; swap it for the
one below and keep the rest of the script. A full CleanRL-derived PPO lives in python/simple_ppo.py.

pip install -e .
python examples/gymnasium_cleanrl.py --num-envs 4
"""
import argparse

import gymnasium as gym
import numpy as np

import grl  # noqa: F401  (registers GRL/Landing-v0)


def make_env(seed):
    def thunk():
        env = gym.make("GRL/Landing-v0", frame_skip=4, max_steps=1000)
        env = gym.wrappers.RecordEpisodeStatistics(env)  # CleanRL reads info["episode"]
        env.action_space.seed(seed)
        return env
    return thunk


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-envs", type=int, default=4)
    parser.add_argument("--steps", type=int, default=2000)
    args = parser.parse_args()

    envs = gym.vector.AsyncVectorEnv([make_env(i) for i in range(args.num_envs)])  # one game per process
    obs, _ = envs.reset(seed=0)
    for _ in range(args.steps):
        obs, reward, terminated, truncated, info = envs.step(envs.action_space.sample())  # your policy here
        if "episode" in info:
            for i in np.flatnonzero(info["_episode"]):
                print(f"env {i}: return={info['episode']['r'][i]:.1f} length={info['episode']['l'][i]} "
                      f"outcome={info['game_state'][i]}")
    envs.close()
