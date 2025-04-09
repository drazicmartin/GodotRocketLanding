from ast import parse
import torch
from simple_ppo import make_env, Agent, parse_args
from pathlib import Path
import gymnasium as gym
import numpy as np

def is_done(done, trunc):
    if isinstance(done, bool):
        return done or trunc
    else:
        return done.any() or trunc.any()

def enjoy(args, agent, device, eval_env=None):
    """
    This function allows to interact with an environment using a trained agent.

    Parameters:
        args (ArgumentParser object): Command-line arguments provided by the user.
        agent (Agent object): The trained RL agent that will take actions based on observations.
        device (torch.device object): The device where the computations will be performed (CPU or GPU).
        eval_env (gymnasium environment, optional): The evaluation environment. If None, it creates a new one. Default is None.
    """
    # Create the evaluation environment if not provided
    if eval_env is None:
        eval_env = make_env(env_id=args.env_id, idx=0, show_window=args.show_window, seed=args.seed, capture_video=args.capture_video, output_dir="debug/eval")

    next_obs, _ = eval_env.reset()
    while True:
        obs = torch.Tensor(next_obs).to(device)
        action, *_ = agent.get_action_and_value(obs)
        next_obs, reward, done, trunc, info = eval_env.step(action.cpu().numpy())

        if is_done(done, trunc):
            break

    if 'game_state' in info:
        print(f"{info['game_state']=}")
    else:
        print(info)

if __name__ == "__main__":
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    eval_env = gym.vector.AsyncVectorEnv(
        [make_env(env_id=args.env_id, idx=0, show_window=True, seed=args.seed, capture_video=args.capture_video, output_dir="debug/eval")]
    )

    agent = Agent(eval_env).to(device)
    agent.load(r"runs\GRL__simple_ppo__1744210038\checkpoint.pth")

    # env = make_env(env_id=args.env_id, idx=0, show_window=True, seed=args.seed, capture_video=args.capture_video, output_dir="debug/eval")()
    enjoy(args, agent, device, eval_env)
    eval_env.close()