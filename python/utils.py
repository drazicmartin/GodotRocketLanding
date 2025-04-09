import asyncio
import json
import platform
import subprocess
from abc import ABC, abstractmethod

import gymnasium as gym
import numpy as np
import websockets
from gymnasium import spaces
import ast

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

    async def connect(self, max_retry=5):
        if self.websocket and self.websocket.open:
            print("Already connected.")
        else:
            print("Not connected. Attempting to connect...")
            try:
                self.websocket = await websockets.connect(self.uri, open_timeout=60)
                print("Connection Success : ready for lift off")
            except ConnectionRefusedError as e:
                if max_retry > 0:
                    await self.connect(max_retry-1)
                else:
                    raise e

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
        response_data = json.loads(response)
        if 'game_state' in response_data:
            return response_data
        else:
            state = self.read_state(response_data)
            return state

    async def quit_game(self):
        await self.send_data(self.get_quit_game_input())

    async def stop(self):
        await self.quit_game()

    def read_state(self, state: dict):
        return { key: ast.literal_eval(val) if isinstance(val, str) else val for key,val in state.items() }

    async def ignition(self, level_name:str = "level_1"):
        await self.connect()
        await self.change_level(level_name)
        await self.set_scripted()
        state = await self.get_state()
        while True:
            action = self.process(state)
            await self.send_data(action)

            state = await self.receive_data()

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
        await self.receive_data()
    
    async def restart_level(self):
        input = self.get_restart_level_input()
        await self.send_data(input)
        data = await self.receive_data()
        while data.get('game_state', None) != "restart":
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
        ):
        super().__init__()
        
        # Initialize the Godot environment
        self.env = GRL(port=port+idx)
        self.show_window = show_window if idx == 0 else False

        self.setup_observation_space()
        self.async_env_started = False
        self.level_name = level_name 

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

    def reset(self, **kwargs):
        if not self.async_env_started:
            asyncio.get_event_loop().run_until_complete(self.async_start())
        return asyncio.get_event_loop().run_until_complete(self.async_reset(**kwargs))

    def step(self, action):
        return asyncio.get_event_loop().run_until_complete(self.async_step(action))

    def close(self):
        return asyncio.get_event_loop().run_until_complete(self.async_close())

    def state_to_observation(self, state):
        observation = []
        for name in self.observation_space_names:
            vue = state[name]
            if isinstance(vue, tuple):
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
        # Send action to the Godot server
        if not isinstance(action, dict):
            action = self.decode_action(action)
        
        await self.env.send_data(action)
        data = await self.env.receive_data()

        truncation = False
        done = False
        obs = None
        if 'game_state' in data:
            done = True
            state = await self.env.receive_data()
            state = {
                **state,
                **data,
            }
        else:
            state = data

        obs = self.state_to_observation(state)
        reward = self.compute_reward(data, obs, done, truncation)
        done, truncation = self.early_stop(obs, reward, done, truncation, state)
        return obs, reward, done, truncation, state

    def early_stop(self, obs, reward, done, truncation, state):
        return done, truncation

    async def async_reset(self, seed=None, options=None):
        await self.env.restart_level()

        # Get initial state
        state = await self.env.get_state()

        obs = self.state_to_observation(state)
        return obs, {}

    def render(self, mode="human"):
        pass  # Rendering handled in Godot

    async def async_close(self):
        await self.env.quit_game()