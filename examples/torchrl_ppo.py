"""TorchRL: PPO on GRL/Landing-v0 with parallel game instances.

pip install -e . "torchrl>=0.14" torch
python examples/torchrl_ppo.py --frames 100000 --num-envs 4
"""
import argparse

import gymnasium as gym
import torch
from tensordict.nn import NormalParamExtractor, TensorDictModule
from torch import nn
from torchrl.collectors import Collector
from torchrl.data import LazyTensorStorage, ReplayBuffer
from torchrl.data.replay_buffers.samplers import SamplerWithoutReplacement
from torchrl.envs import GymWrapper, ParallelEnv
from torchrl.modules import MLP, ProbabilisticActor, TanhNormal, ValueOperator
from torchrl.objectives import ClipPPOLoss
from torchrl.objectives.value import GAE

import grl  # noqa: F401  (registers GRL/Landing-v0)


def make_env():
    # GymWrapper around our env: TorchRL's own GymEnv(frame_skip=...) would repeat actions in Python instead.
    return GymWrapper(gym.make("GRL/Landing-v0", frame_skip=4, max_steps=1000))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=100_000)
    parser.add_argument("--num-envs", type=int, default=4)
    args = parser.parse_args()
    frames_per_batch, minibatch, epochs = 1024, 256, 4

    env = ParallelEnv(args.num_envs, make_env)  # one headless game per worker process
    n_obs = env.observation_spec["observation"].shape[-1]
    n_act = env.action_spec.shape[-1]

    actor = ProbabilisticActor(
        TensorDictModule(nn.Sequential(MLP(in_features=n_obs, out_features=2 * n_act, num_cells=[64, 64]),
                                       NormalParamExtractor()),
                         in_keys=["observation"], out_keys=["loc", "scale"]),
        spec=env.action_spec, in_keys=["loc", "scale"], distribution_class=TanhNormal,
        distribution_kwargs={"low": -1.0, "high": 1.0}, return_log_prob=True,
    )
    critic = ValueOperator(MLP(in_features=n_obs, out_features=1, num_cells=[64, 64]), in_keys=["observation"])

    collector = Collector(env, actor, frames_per_batch=frames_per_batch, total_frames=args.frames)
    advantage = GAE(gamma=0.99, lmbda=0.95, value_network=critic, average_gae=True)
    loss_fn = ClipPPOLoss(actor, critic, clip_epsilon=0.2, entropy_coeff=1e-3)
    optim = torch.optim.Adam(loss_fn.parameters(), lr=3e-4)
    buffer = ReplayBuffer(storage=LazyTensorStorage(frames_per_batch), sampler=SamplerWithoutReplacement())

    for i, data in enumerate(collector):
        for _ in range(epochs):
            advantage(data)
            buffer.extend(data.reshape(-1))
            for _ in range(frames_per_batch // minibatch):
                losses = loss_fn(buffer.sample(minibatch))
                loss = losses["loss_objective"] + losses["loss_critic"] + losses["loss_entropy"]
                loss.backward()
                optim.step()
                optim.zero_grad()
        print(f"batch {i}: mean reward {data['next', 'reward'].mean().item():.3f}")

    collector.shutdown()  # also closes the env and its game instances
