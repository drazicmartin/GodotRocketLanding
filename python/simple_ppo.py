import argparse
import os
import time
from distutils.util import strtobool

import gymnasium as gym
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions.categorical import Categorical
from torch.utils.tensorboard import SummaryWriter
from utils import GRLGym
from math import exp
from tqdm import tqdm
from pathlib import Path
from type import State

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="gymnasium.wrappers.rendering")

def low_capped_cubic_video_schedule(episode_id: int) -> bool:
    r"""The default episode trigger.

    This function will trigger recordings at the episode indices :math:`\{0, 1, 4, 8, 27, ..., k^3, ..., 729, 1000, 2000, 3000, ...\}`

    Args:
        episode_id: The episode number

    Returns:
        If to apply a video schedule number
    """
    if episode_id < 100:
        return int(round(episode_id ** (1.0 / 3))) ** 3 == episode_id
    else:
        return episode_id % 100 == 0

def parse_args():
    # fmt: off
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp-name", type=str, default=os.path.basename(__file__).rstrip(".py"),
        help="the name of this experiment")
    parser.add_argument("--show-window", default=False, action="store_true",
        help="Display the godot window")
    parser.add_argument("--seed", type=int, default=1,
        help="seed of the experiment")
    parser.add_argument("--torch-deterministic", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
        help="if toggled, `torch.backends.cudnn.deterministic=False`")
    parser.add_argument("--cuda", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
        help="if toggled, cuda will be enabled by default")
    parser.add_argument("--capture-video", type=lambda x: bool(strtobool(x)), default=False, nargs="?", const=True,
        help="weather to capture videos of the agent performances (check out `videos` folder)")

    # Algorithm specific arguments
    parser.add_argument("--env-id", type=str, default="GRL", # LunarLander-v3
        help="the id of the environment")
    parser.add_argument("--total-timesteps", type=int, default=100000,
        help="total timesteps of the experiments")
    parser.add_argument("--learning-rate", type=float, default=2.5e-4,
        help="the learning rate of the optimizer")
    parser.add_argument("--num-envs", type=int, default=4,
        help="the number of parallel game environments")
    parser.add_argument("--num-steps", type=int, default=128,
        help="the number of steps to run in each environment per policy rollout")
    parser.add_argument("--anneal-lr", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
        help="Toggle learning rate annealing for policy and value networks")
    parser.add_argument("--gae", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
        help="Use GAE for advantage computation")
    parser.add_argument("--gamma", type=float, default=0.99,
        help="the discount factor gamma")
    parser.add_argument("--gae-lambda", type=float, default=0.95,
        help="the lambda for the general advantage estimation")
    parser.add_argument("--num-minibatches", type=int, default=4,
        help="the number of mini-batches")
    parser.add_argument("--update-epochs", type=int, default=4,
        help="the K epochs to update the policy")
    parser.add_argument("--norm-adv", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
        help="Toggles advantages normalization")
    parser.add_argument("--clip-coef", type=float, default=0.2,
        help="the surrogate clipping coefficient")
    parser.add_argument("--clip-vloss", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
        help="Toggles whether or not to use a clipped loss for the value function, as per the paper.")
    parser.add_argument("--ent-coef", type=float, default=0.01,
        help="coefficient of the entropy")
    parser.add_argument("--vf-coef", type=float, default=0.5,
        help="coefficient of the value function")
    parser.add_argument("--max-grad-norm", type=float, default=0.5,
        help="the maximum norm for the gradient clipping")
    parser.add_argument("--target-kl", type=float, default=None,
        help="the target KL divergence threshold")
    parser.add_argument("--ckpt", type=str, default=None,
        help="Path to checkpoint")

    args = parser.parse_args()
    args.batch_size = int(args.num_envs * args.num_steps)
    args.minibatch_size = int(args.batch_size // args.num_minibatches)
    # fmt: on
    return args

def layer_init(layer, std=np.sqrt(2), bias_const=0.0):
    torch.nn.init.orthogonal_(layer.weight, std)
    torch.nn.init.constant_(layer.bias, bias_const)
    return layer

class Agent(nn.Module):
    def __init__(self, envs):
        super().__init__()
        self.critic = nn.Sequential(
            layer_init(nn.Linear(np.array(envs.single_observation_space.shape).prod(), 64)),
            nn.Tanh(),
            layer_init(nn.Linear(64, 64)),
            nn.Tanh(),
            layer_init(nn.Linear(64, 1), std=1.0),
        )
        self.actor = nn.Sequential(
            layer_init(nn.Linear(np.array(envs.single_observation_space.shape).prod(), 64)),
            nn.Tanh(),
            layer_init(nn.Linear(64, 64)),
            nn.Tanh(),
            layer_init(nn.Linear(64, envs.single_action_space.n), std=0.01),
        )

    def get_value(self, x):
        return self.critic(x)

    def get_action_and_value(self, x, action=None):
        logits = self.actor(x)
        probs = Categorical(logits=logits)
        if action is None:
            action = probs.sample()
        return action, probs.log_prob(action), probs.entropy(), self.critic(x)

    def save(self, path):
        torch.save(self.state_dict(), path)
    
    def load(self, path):
        self.load_state_dict(torch.load(path, weights_only=True))

class CustomGRLGym(GRLGym):
    def setup_observation_space(self):
        from gymnasium import spaces

        self.observation_space_dict = {
            # Rocket position
            'position': {
                #        x    , y
                'low':  [-700 ,-700],
                'high': [700  , 200],
            },
            # Rocket linear velocity in pixels per second
            'linear_velocity': {
                #        x   , y
                'low':  [0   , 0  ],
                'high': [100 , 100],
            },
            # La vitesse de rotation de Rocket en radians par seconde.
            'angular_velocity': {
                'low':  [0],
                'high': [1],
            },
            # Rocket's rotation in radians
            'rotation': {
                'low':  [-3.1415926],
                'high': [ 3.1415926],
            },
            # Proppellant left in percent
            'propellant': {
                'low':  [0],
                'high': [1]
            },
            'left_leg_contact': {
                'low':  [0],
                'high': [1]
            },
            'right_leg_contact': {
                'low':  [0],
                'high': [1]
            }
        }

        self.observation_space_names = ['position', 'linear_velocity', 'angular_velocity', 'rotation', 'propellant', 'right_leg_contact', 'left_leg_contact']
        
        self.action_space = spaces.Discrete(4)  # Example: 4 possible actions, [main, left, right, nothing]
        # self.action_space = spaces.Discrete(2)  # Example: 2 possible actions, [nothing, main]
        return super().setup_observation_space()

    def decode_action(self, action):
        from gymnasium import spaces
        if self.action_space == spaces.Discrete(2):
            return {
                "main_thrust": int(action),
                "rcs_left_thrust": 0, 
                "rcs_right_thrust": 0
            }
        elif self.action_space == spaces.Discrete(4):
            {action_name: float(i==action) for i, action_name in enumerate(self.env.get_action_name())}
        else:
            raise NotImplementedError("implement your own action decoding, or send directly the dict action")

    def early_stop(self, state: State, obs: np.ndarray, reward: int, done: bool, truncation: bool):
        if state['num_frame_computed'] > 500:
            return done, True
        else:
            return done, truncation

    def compute_reward(self, state: State, obs: np.ndarray, done: bool, trunc: bool):
        """
        Computes the reward signal based on the current environment state and observation.

        Args:
            state (dict): The internal environment state, which may include variables 
                        not exposed to the agent (e.g., simulation internals).
            obs (nd.array): The observation received by the agent, typically a processed 
                    or partial view of the state.

        Returns:
            float: The computed reward value that will be used by the learning algorithm.

        Notes:
            This method must be implemented by subclasses. It allows custom reward
            shaping or task-specific reward design.
        """
        reward = 0

        raise NotImplementedError("TODO")
    
        return reward

def make_env(env_id="GRL", idx=0, show_window=False, level_name="level_1", seed=0, capture_video=False, output_dir="runs/debug"):
    def thunk():
        if env_id == "GRL":
            env = CustomGRLGym(idx=idx, port=65000, level_name=level_name, show_window=show_window)
        else:
            env = gym.make(env_id)
            if idx == 0:
                if capture_video:
                    env = gym.make(env_id,  render_mode="rgb_array")
                    env = gym.wrappers.RecordVideo(env, f"{output_dir}/video", episode_trigger=low_capped_cubic_video_schedule)
            
            env = gym.wrappers.RecordEpisodeStatistics(env)
            env.reset(seed=seed)
            env.action_space.seed(seed)
            env.observation_space.seed(seed)
        return env
    return thunk

def main_ppo(args):
    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")
    run_name = f"{args.env_id}__{args.exp_name}__{int(time.time())}"
    output_dir = f"runs/{run_name}"
    writer = SummaryWriter(output_dir)
    writer.add_text(
        "hyperparameters",
        "|param|value|\n|-|-|\n%s" % ("\n".join([f"|{key}|{value}|" for key, value in vars(args).items()])),
    )

    envs = gym.vector.AsyncVectorEnv(
        [make_env(env_id=args.env_id, idx=i, show_window=args.show_window, seed=args.seed + i, capture_video=args.capture_video, output_dir=output_dir) for i in range(args.num_envs)]
    )
    assert isinstance(envs.single_action_space, gym.spaces.Discrete), "only discrete action space is supported"

    agent = Agent(envs).to(device)
    if args.ckpt is not None:
        agent.load(args.ckpt)
    optimizer = optim.Adam(agent.parameters(), lr=args.learning_rate, eps=1e-5)

    # ALGO Logic: Storage setup
    obs = torch.zeros((args.num_steps, args.num_envs) + envs.single_observation_space.shape).to(device)
    actions = torch.zeros((args.num_steps, args.num_envs) + envs.single_action_space.shape).to(device)
    logprobs = torch.zeros((args.num_steps, args.num_envs)).to(device)
    rewards = torch.zeros((args.num_steps, args.num_envs)).to(device)
    dones = torch.zeros((args.num_steps, args.num_envs)).to(device)
    values = torch.zeros((args.num_steps, args.num_envs)).to(device)

    # TRY NOT TO MODIFY: start the game
    global_step = 0
    start_time = time.time()
    _obs, _ = envs.reset()
    next_obs = torch.Tensor(_obs).to(device)
    next_done = torch.zeros(args.num_envs).to(device)
    num_updates = args.total_timesteps // args.batch_size

    for update in tqdm(range(1, num_updates + 1)):
        # Annealing the rate if instructed to do so.
        if args.anneal_lr:
            frac = 1.0 - (update - 1.0) / num_updates
            lrnow = frac * args.learning_rate
            optimizer.param_groups[0]["lr"] = lrnow

        for step in range(0, args.num_steps):
            global_step += 1 * args.num_envs
            obs[step] = next_obs
            dones[step] = next_done

            # ALGO LOGIC: action logic
            with torch.no_grad():
                action, logprob, _, value = agent.get_action_and_value(next_obs)
                values[step] = value.flatten()
            actions[step] = action
            logprobs[step] = logprob

            # TRY NOT TO MODIFY: execute the game and log data.
            next_obs, reward, done, trunc, info = envs.step(action.cpu().numpy())
            rewards[step] = torch.tensor(reward).to(device).view(-1)
            next_obs, next_done = torch.Tensor(next_obs).to(device), torch.Tensor(done | trunc).to(device)
            
            if "episode" == info.keys():
                n = reward.shape[0]
                for i in range(n):
                    print(f"global_step={global_step}, episodic_return={info['episode']['r'][i]}")
                    writer.add_scalar("charts/episodic_return", info['episode']["r"][i], global_step)
                    writer.add_scalar("charts/episodic_length", info['episode']["l"][i], global_step)
                    break

        # bootstrap value if not done
        with torch.no_grad():
            next_value = agent.get_value(next_obs).reshape(1, -1)
            if args.gae:
                advantages = torch.zeros_like(rewards).to(device)
                lastgaelam = 0
                for t in reversed(range(args.num_steps)):
                    if t == args.num_steps - 1:
                        nextnonterminal = 1.0 - next_done
                        nextvalues = next_value
                    else:
                        nextnonterminal = 1.0 - dones[t + 1]
                        nextvalues = values[t + 1]
                    delta = rewards[t] + args.gamma * nextvalues * nextnonterminal - values[t]
                    advantages[t] = lastgaelam = delta + args.gamma * args.gae_lambda * nextnonterminal * lastgaelam
                returns = advantages + values
            else:
                returns = torch.zeros_like(rewards).to(device)
                for t in reversed(range(args.num_steps)):
                    if t == args.num_steps - 1:
                        nextnonterminal = 1.0 - next_done
                        next_return = next_value
                    else:
                        nextnonterminal = 1.0 - dones[t + 1]
                        next_return = returns[t + 1]
                    returns[t] = rewards[t] + args.gamma * nextnonterminal * next_return
                advantages = returns - values

        # flatten the batch
        b_obs = obs.reshape((-1,) + envs.single_observation_space.shape)
        b_logprobs = logprobs.reshape(-1)
        b_actions = actions.reshape((-1,) + envs.single_action_space.shape)
        b_advantages = advantages.reshape(-1)
        b_returns = returns.reshape(-1)
        b_values = values.reshape(-1)

        # Optimizing the policy and value network
        b_inds = np.arange(args.batch_size)
        clipfracs = []
        for epoch in range(args.update_epochs):
            np.random.shuffle(b_inds)
            for start in range(0, args.batch_size, args.minibatch_size):
                end = start + args.minibatch_size
                mb_inds = b_inds[start:end]

                _, newlogprob, entropy, newvalue = agent.get_action_and_value(
                    b_obs[mb_inds], b_actions.long()[mb_inds]
                )
                logratio = newlogprob - b_logprobs[mb_inds]
                ratio = logratio.exp()

                with torch.no_grad():
                    # calculate approx_kl http://joschu.net/blog/kl-approx.html
                    old_approx_kl = (-logratio).mean()
                    approx_kl = ((ratio - 1) - logratio).mean()
                    clipfracs += [((ratio - 1.0).abs() > args.clip_coef).float().mean().item()]

                mb_advantages = b_advantages[mb_inds]
                if args.norm_adv:
                    mb_advantages = (mb_advantages - mb_advantages.mean()) / (mb_advantages.std() + 1e-8)

                # Policy loss
                pg_loss1 = -mb_advantages * ratio
                pg_loss2 = -mb_advantages * torch.clamp(ratio, 1 - args.clip_coef, 1 + args.clip_coef)
                pg_loss = torch.max(pg_loss1, pg_loss2).mean()

                # Value loss
                newvalue = newvalue.view(-1)
                if args.clip_vloss:
                    v_loss_unclipped = (newvalue - b_returns[mb_inds]) ** 2
                    v_clipped = b_values[mb_inds] + torch.clamp(
                        newvalue - b_values[mb_inds],
                        -args.clip_coef,
                        args.clip_coef,
                    )
                    v_loss_clipped = (v_clipped - b_returns[mb_inds]) ** 2
                    v_loss_max = torch.max(v_loss_unclipped, v_loss_clipped)
                    v_loss = 0.5 * v_loss_max.mean()
                else:
                    v_loss = 0.5 * ((newvalue - b_returns[mb_inds]) ** 2).mean()

                entropy_loss = entropy.mean()
                loss = pg_loss - args.ent_coef * entropy_loss + v_loss * args.vf_coef

                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(agent.parameters(), args.max_grad_norm)
                optimizer.step()

            if args.target_kl is not None:
                if approx_kl > args.target_kl:
                    break

        y_pred, y_true = b_values.cpu().numpy(), b_returns.cpu().numpy()
        var_y = np.var(y_true)
        explained_var = np.nan if var_y == 0 else 1 - np.var(y_true - y_pred) / var_y

        # TRY NOT TO MODIFY: record rewards for plotting purposes
        writer.add_scalar("charts/learning_rate", optimizer.param_groups[0]["lr"], global_step)
        writer.add_scalar("losses/value_loss", v_loss.item(), global_step)
        writer.add_scalar("losses/policy_loss", pg_loss.item(), global_step)
        writer.add_scalar("losses/entropy", entropy_loss.item(), global_step)
        writer.add_scalar("losses/old_approx_kl", old_approx_kl.item(), global_step)
        writer.add_scalar("losses/approx_kl", approx_kl.item(), global_step)
        writer.add_scalar("losses/clipfrac", np.mean(clipfracs), global_step)
        writer.add_scalar("losses/explained_variance", explained_var, global_step)
        writer.add_scalar("charts/SPS", int(global_step / (time.time() - start_time)), global_step)

    envs.close()
    writer.close()

    agent.save(Path(output_dir, "checkpoint.pth"))

    eval_env = make_env(env_id=args.env_id, idx=0, show_window=True, seed=args.seed, capture_video=args.capture_video, output_dir=f"{output_dir}/eval")()

    from enjoy_ppo import enjoy
    enjoy(args, agent, device, eval_env=eval_env)
    eval_env.close()

    print("Done !")


if __name__ == "__main__":
    args = parse_args()
    
    main_ppo(args)
    