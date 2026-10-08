import asyncio

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .client import GRL


class GRLGym(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(
            self,
            idx=0,
            port=None,
            show_window = False,
            level_name="random_level_easy",
            frame_skip=1,
            binary=None,
            render_mode=None,
            config=None,
        ):
        super().__init__()
        # Gymnasium convention: render_mode="human" means "show the game window" (Godot renders it itself).
        self.render_mode = render_mode
        if render_mode == "human":
            show_window = True

        # Initialize the Godot environment. port=None picks a free port, so frameworks that create envs on
        # their own (SB3 SubprocVecEnv, RLlib workers, ...) never collide; an explicit port is offset by idx.
        self.env = GRL(port=None if port is None else port + idx, binary=binary, config=config)
        self.show_window = show_window if idx == 0 else False

        self.setup_observation_space()
        self.async_env_started = False
        # One private loop per env: asyncio.get_event_loop() no longer creates one implicitly
        self._loop = asyncio.new_event_loop()
        self.level_name = level_name
        self.frame_skip = frame_skip

    def setup_observation_space(self):
        self.define_observation_space()

    async def async_start(self):
        # Start game level
        self.env.start_game(show_window=self.show_window)
        await self.env.connect()
        await self.env.change_level(self.level_name)
        await self.env.set_scripted()

    def get_reward(self, state: dict, obs: np.ndarray, terminated: bool, truncated: bool) -> float:
        """Reward for the step that produced `state` (full game state, `game_state` set on the last step).

        Override it for custom reward shaping. Not named `compute_reward`: Stable-Baselines3 and HER treat any
        env with a `compute_reward` method as a goal-conditioned env. Subclasses written against the old name
        still work, they are called from here.
        """
        legacy = getattr(self, "compute_reward", None)
        if legacy is not None:
            return legacy(state, obs, terminated, truncated)
        raise NotImplementedError

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if not self.async_env_started:
            self._loop.run_until_complete(self.async_start())
            self.async_env_started = True
        return self._loop.run_until_complete(self.async_reset(seed=seed, options=options))

    def step(self, action):
        return self._loop.run_until_complete(self.async_step(action))

    def close(self):
        if self.async_env_started:
            self._loop.run_until_complete(self.async_close())
            self.async_env_started = False
        self.env.close()

    def state_to_observation(self, state):
        observation = []
        for name in self.observation_space_names:
            vue = state[name]
            if isinstance(vue, (list, tuple)):
                observation.extend(state[name])
            else:
                observation.append(state[name])
        
        ## TODO CHECK if the observation match the defined low and high
        return np.array(observation, dtype=np.float32)

    def define_observation_space(self):
        low = []
        high = []
        for name in self.observation_space_names:
            low.extend(self.observation_space_dict[name]['low'])
            high.extend(self.observation_space_dict[name]['high'])

        low = np.array(low, dtype=np.float32)
        high = np.array(high, dtype=np.float32)
        self.observation_space = spaces.Box(low=low, high=high, dtype=np.float32)

    def decode_action(self, action):
        if isinstance(action, np.int64) and self.action_space == spaces.Discrete(4):
            return {action_name: float(i==action) for i, action_name in enumerate(self.env.get_action_name()) }
        else:
            raise NotImplementedError("implement your own action decoding, or send directly the dict action")

    async def async_step(self, action):
        # Send action to the Godot server; exactly one reply comes back, with `game_state` set when the episode ended
        if not isinstance(action, dict):
            action = self.decode_action(action)

        state = await self.env.step(action, frame_skip=self.frame_skip)

        done = 'game_state' in state
        truncation = False
        obs = self.state_to_observation(state)
        reward = self.get_reward(state, obs, done, truncation)
        done, truncation = self.early_stop(obs, reward, done, truncation, state)
        return obs, float(reward), done, truncation, self.state_to_info(state)

    def state_to_info(self, state: dict) -> dict:
        """Info dict with the same keys on every step.

        Frameworks that stack infos into buffers (Tianshou, TorchRL, vector envs) choke on keys that only appear
        on the last step, so `game_state` is always present ("running" | "victory" | "crash"), and
        `is_success` is the standard success flag (logged by Stable-Baselines3 as success_rate).
        """
        info = {key: value for key, value in state.items() if key != 'score'}
        info['game_state'] = state.get('game_state', 'running')
        info['is_success'] = info['game_state'] == 'victory'
        return info

    def early_stop(self, obs, reward, done, truncation, state):
        return done, truncation

    async def async_reset(self, seed=None, options=None):
        if seed is not None:
            await self.env.set_seed(seed)
        await self.env.restart_level()

        # Get initial state
        state = await self.env.get_state()

        obs = self.state_to_observation(state)
        return obs, self.state_to_info(state)

    def render(self, mode="human"):
        pass  # Rendering handled in Godot

    async def async_close(self):
        await self.env.stop()

class GRLEnv(GRLGym):
    """Ready-to-train landing env: `gym.make("GRL/Landing-v0")`.

    Observation: position(2), linear_velocity(2), angular_velocity, rotation, propellant (0-100),
    left/right leg contact, landing_pad_distance (signed arc px to the pad). Victory requires touching down on
    the randomly placed pad with the legs deployed and staying still for 0.5 s; a landing elsewhere does not
    end the episode. Action: Box(4) adds a 4th "legs" command (> 0 deploys; deployed legs cost 15 % main
    thrust and 40 % RCS), legs_extension (0..1) is observed. Thrusters: Box(3) in [-1, 1] for (main, rcs_left, rcs_right), mapped to thrust
    (a + 1) / 2 so -1 = off and 1 = full (symmetric bounds are what SB3/Tianshou/RLlib policies expect), or
    Discrete(2) (main engine off/on) with `discrete_actions=True`.
    Reward: shaped towards the pad (see `get_reward`), override it for your own shaping.
    Episodes end on "victory"/"crash" (terminated) or after `max_steps` ticks (truncated).
    """

    observation_space_names = [
        'position', 'linear_velocity', 'angular_velocity', 'rotation',
        'propellant', 'left_leg_contact', 'right_leg_contact', 'landing_pad_distance', 'legs_extension',
    ]
    observation_space_dict = {
        'position': {'low': [-np.inf] * 2, 'high': [np.inf] * 2},
        'linear_velocity': {'low': [-np.inf] * 2, 'high': [np.inf] * 2},
        'angular_velocity': {'low': [-np.inf], 'high': [np.inf]},
        'rotation': {'low': [-np.inf], 'high': [np.inf]},
        'propellant': {'low': [0], 'high': [100]},
        'left_leg_contact': {'low': [0], 'high': [1]},
        'right_leg_contact': {'low': [0], 'high': [1]},
        # signed surface distance to the pad centre (px), > 0 when the pad is to the rocket's local right
        'landing_pad_distance': {'low': [-np.inf], 'high': [np.inf]},
        'legs_extension': {'low': [0], 'high': [1]},
    }

    def __init__(self, discrete_actions=False, max_steps=1000, **kwargs):
        self.discrete_actions = discrete_actions
        self.max_steps = max_steps
        super().__init__(**kwargs)

    def setup_observation_space(self):
        if self.discrete_actions:
            self.action_space = spaces.Discrete(2)
        else:
            # main, rcs_left, rcs_right, legs (> 0 deploys the landing legs)
            self.action_space = spaces.Box(-1.0, 1.0, shape=(4,), dtype=np.float32)
        self.define_observation_space()

    def decode_action(self, action):
        names = self.env.get_action_name() + ["legs"]
        if self.discrete_actions:
            # main engine only; legs kept deployed so a landing can count
            return {names[0]: float(action), names[1]: 0.0, names[2]: 0.0, "legs": 1.0}
        return {name: float((np.clip(value, -1.0, 1.0) + 1.0) / 2.0) for name, value in zip(names, action)}

    def early_stop(self, obs, reward, done, truncation, state):
        if not done and state['num_frame_computed'] >= self.max_steps:
            truncation = True
        return done, truncation

    def get_reward(self, state, obs, terminated, truncated):
        if state.get('game_state') == 'victory':
            return 100.0
        if state.get('game_state') == 'crash':
            return -100.0
        # Stay close to the pad, slow down, keep the hull intact.
        distance = float(np.linalg.norm(np.subtract(state['position'], state['landing_pad_position'])))
        speed = float(np.linalg.norm(state['linear_velocity']))
        return float(-0.001 * distance - 0.01 * speed) * state['rocket_integrity']


gym.register(id="GRL/Landing-v0", entry_point="grl.env:GRLEnv")
