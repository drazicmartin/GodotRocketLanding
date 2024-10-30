import websockets
import json
from abc import ABC, abstractmethod

class GRL:
    def __init__(self, uri):
        self.uri = uri
        self.websocket = None  # Initialize websocket as None

    async def connect(self):
        # Perform the async connection setup in a separate async method
        print(f"Connection to {self.uri}")
        self.websocket = await websockets.connect(self.uri)
        print("Connection succeed")

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

    async def crash(self):
        if self.websocket is not None:
            await self.websocket.close()

    async def ignition(self):
        await self.connect()
        while True:
            state = await self.receive_data()

            if "game_state" in state:
                print(state['game_state'])
                break

            inputs = self.process(state)
            await self.send_data(inputs)
        await self.crash()

    @abstractmethod
    def process(self, state: dict):
        """
        Processes the current state of the rocket.

        :param state: A dictionary representing the current state of the rocket.
        :return: A new dictionary that specifies the input for the rocket.
        """
        pass