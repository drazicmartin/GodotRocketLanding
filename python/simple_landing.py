import asyncio
from utils import GRL

class SimpleLanding(GRL):
    def process(self, state: dict):
        """
        Processes the current state of the rocket.

        :param state: A dictionary representing the current state of the rocket.
        :return: A new dictionary that specifies the input for the rocket.
        """

        inputs = {
            "main_thrust": 0.4,
            "rcs_left_thrust": 0,
            "rcs_right_thrust": 0
        }

        print(state)

        return inputs

if __name__ == "__main__":
    rocket = SimpleLanding(
        uri="ws://127.0.0.1:65000"
    ) 
    try:
        asyncio.run(rocket.ignition())
    finally:
        asyncio.run(rocket.crash())
