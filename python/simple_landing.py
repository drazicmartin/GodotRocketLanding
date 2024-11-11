import asyncio
from utils import GRL
import ast

class SimpleLanding(GRL):
    def process(self, state: dict):
        """
        Processes the current state of the rocket.

        :param state: A dictionary representing the current state of the rocket.
        :return: A new dictionary that specifies the input for the rocket.
        """
        position = ast.literal_eval(state['position'])
        velocity = ast.literal_eval(state['velocity'])

        inputs = {
            "main_thrust": 0.8,
            "rcs_left_thrust": 0,
            "rcs_right_thrust": 1
        }

        print(state)

        return inputs

async def main(rocket: GRL):
    rocket.start_game()
    await rocket.ignition(level_name="level_1")
    await rocket.stop()
    print("Done!")

if __name__ == "__main__":
    rocket = SimpleLanding(
        port=65000
    )
    asyncio.run(
        main(rocket)
    )
