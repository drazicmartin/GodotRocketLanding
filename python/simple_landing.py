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

        rcs_left_thrust = 0
        rcs_right_thrust = 0

        if state['rotation'] > 0:
            rcs_right_thrust = 0.5
        else:
            rcs_left_thrust = 0.5

        t = 0.4
        if position[1] > -200:
            t = 0.8
        if position[1] > -10:
            t = 0

        inputs = {
            "main_thrust": t,
            "rcs_left_thrust": rcs_left_thrust,
            "rcs_right_thrust": rcs_right_thrust,
        }

        return inputs

async def main(rocket: GRL):
    rocket.start_game(show_window=True)
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
