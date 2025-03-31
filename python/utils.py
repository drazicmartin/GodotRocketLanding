import asyncio
import json
import subprocess
from abc import ABC, abstractmethod

import gymnasium as gym
import numpy as np
import websockets
from gymnasium import spaces


class GRL:
    def __init__(
            self, 
            port: int = 65000, 
            exe_path: str = "GRL.exe"
        ):
        self.port = port
        self.uri = f"ws://127.0.0.1:{int(port)}"
        self.websocket = None  # Initialize websocket as None
        self.exe_path = exe_path

    async def connect(self, max_retry=5):
        if self.websocket and self.websocket.open:
            print("Already connected.")
        else:
            print("Not connected. Attempting to connect...")
            try:
                self.websocket = await websockets.connect(self.uri, timeout=60)
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
        return response_data

    async def quit_game(self):
        await self.send_data(self.get_quit_game_input())

    async def stop(self):
        await self.quit_game()

    async def ignition(self, level_name:str = "level_1"):
        await self.connect()
        await self.change_level(level_name)
        await self.set_scripted()
        state = await self.get_state()
        while True:
            if "game_state" in state:
                print(state['game_state'])
                break

            inputs = self.process(state)
            await self.send_data(inputs)

            state = await self.receive_data()

    def start_game(self, show_window=False):
        cmd = [self.exe_path, "-p", str(self.port)]
        if not show_window:
            cmd.append("--headless")
        subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS)

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

class GRLGym(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(
            self, 
            action_space_mode="discrete" #  discrete or continious
        ):
        super().__init__()
        
        # Initialize the Godot environment
        self.env = GRL()
        
        if action_space_mode == "discrete":
            # Define action and observation spaces
            self.action_space = spaces.Discrete(3)  # Example: 4 possible actions
            self.observation_space = spaces.Box(low=0, high=255, shape=(84, 84, 3), dtype=np.uint8)
        else:
            self.action_space = spaces.Box(low=0.0, high=1.0, shape=(3,), dtype=np.float32)
            self.observation_space = spaces.Box(low=0, high=255, shape=(84, 84, 3), dtype=np.uint8)

        # Start game
        self.env.start_game(show_window=False)
        asyncio.run(self.env.connect())

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

    def step(self, action):
        # Send action to the Godot server
        asyncio.run(self.env.send_data(action))

        # Receive state
        state = asyncio.run(self.env.receive_data())

        # Extract data from state
        obs = np.array(state["observation"])
        reward = state.get("reward", 0)
        done = state.get("done", False)

        return obs, reward, done, False, {}

    def reset(self, seed=None, options=None):
        # Reset game level
        asyncio.run(self.env.change_level("random_level"))

        # Get initial state
        state = asyncio.run(self.env.get_state())
        return np.array(state["observation"]), {}

    def render(self, mode="human"):
        pass  # Rendering handled in Godot

    def close(self):
        asyncio.run(self.env.quit_game())