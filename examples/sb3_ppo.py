"""Stable-Baselines3: PPO on GRL/Landing-v0 with parallel game instances.

pip install -e . stable-baselines3
python examples/sb3_ppo.py --timesteps 100000 --num-envs 8
"""
import argparse

import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv

import grl  # noqa: F401  (registers GRL/Landing-v0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--num-envs", type=int, default=8)
    args = parser.parse_args()

    # Each subprocess launches its own headless game on a free port.
    env = make_vec_env("GRL/Landing-v0", n_envs=args.num_envs, vec_env_cls=SubprocVecEnv,
                       env_kwargs={"frame_skip": 4, "max_steps": 1000})
    model = PPO("MlpPolicy", env, n_steps=256, batch_size=256, verbose=1)
    model.learn(total_timesteps=args.timesteps)
    model.save("ppo_grl_sb3")
    env.close()

    # Watch the trained agent in a window.
    eval_env = gym.make("GRL/Landing-v0", show_window=True, frame_skip=4)
    obs, _ = eval_env.reset(seed=0)
    done = False
    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = eval_env.step(action)
        done = terminated or truncated
    print("outcome:", info["game_state"])  # "victory", "crash", or "running" if truncated
    eval_env.close()
