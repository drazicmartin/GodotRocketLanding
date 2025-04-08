import asyncio
from simple_landing import main as run_simple_landing
from simple_landing import SimpleLanding

async def main():
    starting_port = 6500
    tasks = []
    for k in range(4):
        rocket = SimpleLanding(port=starting_port+k)
        tasks.append(run_simple_landing(rocket, level_name='random_level_easy', show_window=False))
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(
        main()
    )
