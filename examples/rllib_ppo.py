"""Ray RLlib: PPO on GRLEnv with several env runners (each one runs its own headless game).

pip install -e . "ray[rllib]" torch
python examples/rllib_ppo.py --iterations 20 --num-env-runners 4
"""
import argparse
import os

from ray.rllib.algorithms.ppo import PPOConfig
from ray.tune.registry import register_env

from grl import GRLEnv

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--num-env-runners", type=int, default=4)
    args = parser.parse_args()

    register_env("grl_landing", lambda env_config: GRLEnv(**env_config))

    config = (
        PPOConfig()
        .environment("grl_landing", env_config={"frame_skip": 4, "max_steps": 1000})
        .env_runners(num_env_runners=args.num_env_runners)
        .training(train_batch_size_per_learner=2000, minibatch_size=250)
    )
    algo = config.build_algo()
    for i in range(args.iterations):
        result = algo.train()
        print(f"iter {i}: episode_return_mean={result['env_runners'].get('episode_return_mean')}")
    print("checkpoint:", algo.save(os.path.abspath("ppo_grl_rllib")))
    algo.stop()
