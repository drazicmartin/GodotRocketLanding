"""Tianshou (>= 2.0, high-level API): PPO on GRL/Landing-v0 with parallel game instances.

pip install -e . "tianshou>=2" torch
python examples/tianshou_ppo.py --epochs 10 --num-envs 4
"""
import argparse

from tianshou.highlevel.config import OnPolicyTrainingConfig
from tianshou.highlevel.env import EnvFactoryRegistered, VectorEnvType
from tianshou.highlevel.experiment import ExperimentConfig, PPOExperimentBuilder

import grl  # noqa: F401  (registers GRL/Landing-v0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--steps-per-epoch", type=int, default=10_000)
    parser.add_argument("--num-envs", type=int, default=4)
    args = parser.parse_args()

    env_factory = EnvFactoryRegistered(
        task="GRL/Landing-v0",
        venv_type=VectorEnvType.SUBPROC,  # one headless game per subprocess
        frame_skip=4,
        max_steps=1000,
    )
    experiment = PPOExperimentBuilder(
        env_factory,
        ExperimentConfig(watch=False, persistence_base_dir="runs/tianshou"),
        OnPolicyTrainingConfig(
            max_epochs=args.epochs,
            epoch_num_steps=args.steps_per_epoch,
            num_training_envs=args.num_envs,
            num_test_envs=1,
            collection_step_num_env_steps=1024,
            batch_size=256,
        ),
    ).build()
    experiment.run()
