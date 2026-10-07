import asyncio
import json
import platform
import subprocess
from abc import ABC, abstractmethod

import gymnasium as gym
import numpy as np
import websockets
from gymnasium import spaces
import signal

# Must match Settings.PROTOCOL_VERSION in scripts/settings.gd (see docs/protocol.md).
PROTOCOL_VERSION = 1


class GRL:
    def __init__(
            self, 
            port: int = 65000,
            debug: bool = False,
        ):
        self.port = port
        self.uri = f"ws://127.0.0.1:{int(port)}"
        self.websocket = None  # Initialize websocket as None
        self.exe_path = "GRL.exe" if platform.system() == "Windows" else "./GRL.x86_64"
        self.debug = debug

        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:
            pass  # not the main thread (e.g. gym AsyncVectorEnv worker): can't install handlers

    def _handle_signal(self, sig, frame):
        print(f"Signal {sig} received")
        self.stop()

    async def connect(self, max_retry=5):
        if self.websocket is not None and getattr(self.websocket, 'open', True):
            print("Already connected.")
        else:
            print("Not connected. Attempting to connect...")
            try:
                self.websocket = await websockets.connect(self.uri, open_timeout=60)
                await self.handshake()
                print("Connection Success : ready for lift off")
            except ConnectionRefusedError as e:
                if max_retry > 0:
                    await self.connect(max_retry-1)
                else:
                    raise e

    async def handshake(self, timeout: float = 10.0):
        """Fail loudly if the game binary does not speak the same protocol version."""
        await self.send_data({'action': 'hello'})
        try:
            reply = await asyncio.wait_for(self.receive_data(), timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(
                "No reply to 'hello': the GRL binary is older than this client, re-export it from Godot."
            )
        if reply.get('protocol') != PROTOCOL_VERSION:
            raise RuntimeError(
                f"Protocol mismatch: client={PROTOCOL_VERSION}, game={reply.get('protocol')}"
            )

    async def get_state(self):
        await self.send_data({
            'action': 'get_state'
        })
        state = await self.receive_data()
        return state

    async def send_data(self, data):
        if self.websocket is not None:
            json_data = json.dumps(data)
            # Send JSON data to the server
            await self.websocket.send(json_data)
    
    async def receive_data(self):
        response = await self.websocket.recv()
        # Deserialize the JSON string back into a Python object
        return self.read_state(json.loads(response))

    async def quit_game(self):
        await self.send_data(self.get_quit_game_input())

    async def stop(self):
        await self.quit_game()

    def read_state(self, state: dict):
        # Vectors arrive as [x, y] lists; planet_mass is a scientific-notation string ("2e24").
        if 'planet_mass' in state:
            state['planet_mass'] = float(state['planet_mass'])
        return state

    async def step(self, action: dict, frame_skip: int = 1):
        """Apply `action` for `frame_skip` physics ticks and return the resulting state.

        The state contains a `game_state` key ("victory" / "crash") when the episode ended.
        """
        await self.send_data({'action': 'step', 'inputs': action, 'frame_skip': frame_skip})
        return await self.receive_data()

    async def set_seed(self, seed: int):
        """Seed Godot's RNG; takes effect on the next restart_level / change_level."""
        await self.send_data({'action': 'set_seed', 'seed': int(seed)})

    async def ignition(self, level_name:str = "level_1"):
        await self.connect()
        await self.change_level(level_name)
        await self.set_scripted()
        state = await self.get_state()
        while True:
            action = self.process(state)
            state = await self.step(action)

            if "game_state" in state:
                print(f"Houston we have a problem : State={state['game_state']}")
                break

    def start_game(self, show_window=False):
        cmd = [self.exe_path, "-p", str(self.port)]
        if not show_window or platform.system() == "Linux":
            cmd.append("--headless")
        if self.debug:
            cmd.append("--debug")
        
        flags = 0
        if platform.system() == "Windows":
            flags = subprocess.DETACHED_PROCESS

        subprocess.Popen(cmd, creationflags=flags)

    @abstractmethod
    def process(self, state: dict):
        """
        Processes the current state of the rocket.

        :param state: A dictionary representing the current state of the rocket.
        :return: A new dictionary that specifies the input for the rocket.
        """
        pass

    async def change_level(self, level_name):
        input = self.get_change_level_input(level_name)
        await self.send_data(input)
        await self.wait_ack('change_level')
    
    async def restart_level(self):
        input = self.get_restart_level_input()
        await self.send_data(input)
        await self.wait_ack('restart_level')

    async def wait_ack(self, name: str):
        data = await self.receive_data()
        while data.get('ack') != name:
            data = await self.receive_data()

    async def set_scripted(self):
        await self.send_data({
            'action': 'set_scripted'
        })

    def get_change_level_input(self, level_name):
        return  {
            'action': 'change_level',
            'level_name': level_name,
        }
    
    def get_quit_game_input(self):
        return {
            'action':  'quit'
        }
    
    def get_restart_level_input(self):
        return {
            'action':  'restart_level'
        }

    def get_action_name(self):
        return ["main_thrust", "rcs_left_thrust", "rcs_right_thrust"]

class GRLGym(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(
            self,
            idx=0,
            port=65000,
            show_window = False,
            level_name="random_level_easy",
            frame_skip=1,
        ):
        super().__init__()
        
        # Initialize the Godot environment
        self.env = GRL(port=port+idx)
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

    @abstractmethod
    def compute_reward(self, state: dict, obs: np.ndarray, victory: bool, crash: bool):
        """
        Computes the reward signal based on the current environment state and observation.

        Args:
            state (Any): The internal environment state, which may include variables 
                        not exposed to the agent (e.g., simulation internals).
            obs (Any): The observation received by the agent, typically a processed 
                    or partial view of the state.

        Returns:
            float: The computed reward value that will be used by the learning algorithm.

        Notes:
            This method must be implemented by subclasses. It allows custom reward
            shaping or task-specific reward design.
        """

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if not self.async_env_started:
            self._loop.run_until_complete(self.async_start())
            self.async_env_started = True
        return self._loop.run_until_complete(self.async_reset(seed=seed, options=options))

    def step(self, action):
        return self._loop.run_until_complete(self.async_step(action))

    def close(self):
        return self._loop.run_until_complete(self.async_close())

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

    @abstractmethod
    def get_reward(self, state):
        """
        Computes the reward based on the given game state.

        This method should be implemented by the user to define a custom reward function.
        The reward function will determine how the agent learns by assigning positive or
        negative values based on the current state of the environment.

        :param state: A dictionary containing the current game state, including relevant 
                    information such as position, velocity, fuel level, etc.
        :return: A float representing the computed reward.
        """
        pass

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
        reward = self.compute_reward(state, obs, done, truncation)
        done, truncation = self.early_stop(obs, reward, done, truncation, state)
        return obs, reward, done, truncation, state

    def early_stop(self, obs, reward, done, truncation, state):
        return done, truncation

    async def async_reset(self, seed=None, options=None):
        if seed is not None:
            await self.env.set_seed(seed)
        await self.env.restart_level()

        # Get initial state
        state = await self.env.get_state()

        obs = self.state_to_observation(state)
        return obs, {}

    def render(self, mode="human"):
        pass  # Rendering handled in Godot

    async def async_close(self):
        await self.env.quit_game()