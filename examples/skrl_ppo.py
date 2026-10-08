"""skrl: PPO on GRL/Landing-v0 with parallel game instances.

pip install -e . "skrl>=2" torch
python examples/skrl_ppo.py --timesteps 20000 --num-envs 4
"""
import argparse

import gymnasium as gym
import torch
import torch.nn as nn
from skrl.agents.torch.ppo import PPO, PPO_CFG
from skrl.envs.wrappers.torch import wrap_env
from skrl.memories.torch import RandomMemory
from skrl.models.torch import DeterministicMixin, GaussianMixin, Model
from skrl.trainers.torch import SequentialTrainer

import grl  # noqa: F401  (registers GRL/Landing-v0)


class Policy(GaussianMixin, Model):
    def __init__(self, observation_space, action_space, device):
        Model.__init__(self, observation_space=observation_space, action_space=action_space, device=device)
        GaussianMixin.__init__(self, clip_actions=True)
        self.net = nn.Sequential(nn.Linear(self.num_observations, 64), nn.Tanh(),
                                 nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, self.num_actions))
        self.log_std = nn.Parameter(torch.zeros(self.num_actions))

    def compute(self, inputs, role):
        return self.net(inputs["observations"]), {"log_std": self.log_std}


class Value(DeterministicMixin, Model):
    def __init__(self, observation_space, action_space, device):
        Model.__init__(self, observation_space=observation_space, action_space=action_space, device=device)
        DeterministicMixin.__init__(self)
        self.net = nn.Sequential(nn.Linear(self.num_observations, 64), nn.Tanh(),
                                 nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 1))

    def compute(self, inputs, role):
        return self.net(inputs["observations"]), {}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=20_000)
    parser.add_argument("--num-envs", type=int, default=4)
    args = parser.parse_args()

    env = gym.make_vec("GRL/Landing-v0", num_envs=args.num_envs, vectorization_mode="async",
                       frame_skip=4, max_steps=1000)
    env = wrap_env(env)

    models = {"policy": Policy(env.observation_space, env.action_space, env.device),
              "value": Value(env.observation_space, env.action_space, env.device)}
    rollouts = 256
    cfg = PPO_CFG(rollouts=rollouts, mini_batches=4)
    memory = RandomMemory(memory_size=rollouts, num_envs=env.num_envs, device=env.device)
    agent = PPO(models=models, memory=memory, cfg=cfg,
                observation_space=env.observation_space, action_space=env.action_space, device=env.device)

    trainer = SequentialTrainer(cfg={"timesteps": args.timesteps, "headless": True}, env=env, agents=agent)
    trainer.train()
    env.close()
