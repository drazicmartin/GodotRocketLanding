import asyncio
from utils import GRL

class SimpleLanding(GRL):
    def process(self, state: dict):
        """
        Processes the current state of the rocket.

        :param state: A dictionary representing the current state of the rocket.
        :return: A new dictionary that specifies the input for the rocket.
        """
        position = state['position']
        velocity = state['linear_velocity']

        rcs_left_thrust = 0
        rcs_right_thrust = 0

        if state['rotation'] > 0:
            rcs_right_thrust = 0.5
        else:
            rcs_left_thrust = 0.5

        t = 0.1
        if position[1] > -200:
            t = 0.5
        if position[1] > -10:
            t = 0

        action = {
            "main_thrust": 0,
            "rcs_left_thrust": 0,
            "rcs_right_thrust": 0,
        }

        return action

async def main(rocket: GRL, level_name='random_level_easy', show_window=False):
    rocket.start_game(show_window=show_window)
    await rocket.ignition(level_name=level_name)
    await rocket.stop()
    print("Done!")

if __name__ == "__main__":
    rocket = SimpleLanding(
        port=3012
    )
    asyncio.run(
        main(rocket, show_window=True),
    )
