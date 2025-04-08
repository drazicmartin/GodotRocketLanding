import torch
from simple_ppo import make_env, Agent
from pathlib import Path
import gymnasium as gym
import numpy as np

def enjoy(agent, device):
    # Create the evaluation environment
    eval_env = gym.vector.AsyncVectorEnv(
        [make_env(show_window=True)]
    )

    next_obs, _ = eval_env.reset()
    trunc = np.array([False])
    done = np.array([False])
    while not done.any() and not trunc.any():
        obs = torch.Tensor(next_obs).to(device)
        action, *_ = agent.get_action_and_value(obs)
        next_obs, reward, done, trunc, state = eval_env.step(action.cpu().numpy())

    if done:
        print("eval : victory")
    elif trunc:
        print("eval : crash")

if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    eval_env = gym.vector.AsyncVectorEnv(
        [make_env(show_window=False)]
    )

    agent = Agent(eval_env).to(device)
    agent.load(r"runs\GRLGym__simple_ppo__1744122978\checkpoint.pth")