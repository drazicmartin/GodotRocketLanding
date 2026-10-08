import asyncio
import json
import os
import signal
from abc import abstractmethod
from typing import Optional

import websockets

from .process import GameProcess, find_free_port

# Must match Settings.PROTOCOL_VERSION in scripts/settings.gd (see docs/protocol.md).
PROTOCOL_VERSION = 1


class GRL:
    """Low-level async client for one game instance. Subclass and override `process` for scripted control."""

    def __init__(
            self,
            port: Optional[int] = 65000,
            debug: bool = False,
            binary: Optional[os.PathLike] = None,
            config=None,
        ):
        # port=None picks a free port, which avoids collisions between parallel instances.
        self.port = find_free_port() if port is None else int(port)
        self.uri = f"ws://127.0.0.1:{self.port}"
        self.websocket = None
        self.debug = debug
        self.binary = binary
        # Launch config (dict {section: {key: value}} or path to a .cfg file), see grl/config.py
        self.config = config
        self.game: Optional[GameProcess] = None

        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:
            pass  # not the main thread (e.g. gym AsyncVectorEnv worker): can't install handlers

    def _handle_signal(self, sig, frame):
        print(f"Signal {sig} received")
        self.close()
        raise KeyboardInterrupt

    def close(self):
        """Synchronous cleanup: terminate the game subprocess we launched."""
        if self.game is not None:
            self.game.terminate()

    async def connect(self, retries: int = 60, delay: float = 0.5):
        """Connect to the game, retrying while it boots, then check the protocol version."""
        if self.websocket is not None and getattr(self.websocket, 'open', True):
            return
        for attempt in range(retries + 1):
            try:
                self.websocket = await websockets.connect(self.uri, open_timeout=60)
                break
            except (ConnectionRefusedError, OSError):
                if attempt == retries:
                    raise
                await asyncio.sleep(delay)
        await self.handshake()

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
        try:
            await self.quit_game()
        finally:
            self.close()

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
        self.game = GameProcess(self.port, show_window=show_window, debug=self.debug, binary=self.binary,
                                config=self.config)
        self.game.start()

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
