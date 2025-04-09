from ast import parse
import torch
from simple_ppo import make_env, Agent, parse_args
from pathlib import Path
import gymnasium as gym
import numpy as np

def is_done(done, trunc):
    if isinstance(done, bool):
        return not done and not trunc
    else:
        return not done.any() and not trunc.any()

def enjoy(args, agent, device, eval_env=None):
    # Create the evaluation environment

    if eval_env is None:
        eval_env = make_env(env_id=args.env_id, idx=0, show_window=args.show_window, seed=args.seed, capture_video=args.capture_video, output_dir="debug/eval")

    next_obs, _ = eval_env.reset()
    trunc = False
    done = False
    while is_done(done, trunc):
        obs = torch.Tensor(next_obs).to(device)
        action, *_ = agent.get_action_and_value(obs)
        next_obs, reward, done, trunc, info = eval_env.step(action.cpu().numpy())

    print(info)

if __name__ == "__main__":
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    eval_env = gym.vector.AsyncVectorEnv(
        [make_env(env_id=args.env_id, idx=0, show_window=args.show_window, seed=args.seed, capture_video=args.capture_video, output_dir="debug/eval")]
    )

    agent = Agent(eval_env).to(device)
    agent.load(r"runs\LunarLander-v3__simple_ppo__1744191388\checkpoint.pth")

    env = make_env(env_id=args.env_id, idx=0, show_window=args.show_window, seed=args.seed, capture_video=args.capture_video, output_dir="debug/eval")()
    enjoy(args, agent, device, env)
    env.close()