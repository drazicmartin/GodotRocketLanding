import asyncio
from utils import GRL
from type import State

class SimpleLanding(GRL):
    def process(self, state: State):
        """
        Processes the current state of the rocket.

        :param state: A dictionary representing the current state of the rocket.
        :return: A new dictionary that specifies the input for the rocket.
        """

        main_thrust = 0
        rcs_left_thrust = 0
        rcs_right_thrust = 0

        action = {
            "main_thrust": main_thrust,
            "rcs_left_thrust": rcs_left_thrust,
            "rcs_right_thrust": rcs_right_thrust,
        }

        return action

async def main(rocket: GRL, level_name='level_1', show_window=False):
    rocket.start_game(show_window=show_window)
    await rocket.ignition(level_name=level_name)
    await rocket.stop()
    print("Done!")

if __name__ == "__main__":
    rocket = SimpleLanding(
        port=65000
    )
    asyncio.run(
        main(rocket, show_window=True),
    )
