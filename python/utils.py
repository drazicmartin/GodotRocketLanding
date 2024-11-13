import websockets
import json
from abc import ABC, abstractmethod
import subprocess
import time

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
                    self.connect(max_retry-1)
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
        state = await self.get_state()
        while True:
            if "game_state" in state:
                print(state['game_state'])
                break

            inputs = self.process(state)
            await self.send_data(inputs)

            state = await self.receive_data()

    def start_game(self):
        subprocess.Popen([self.exe_path, "-p", str(self.port)], creationflags=subprocess.DETACHED_PROCESS)

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