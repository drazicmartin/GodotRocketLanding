import gymnasium as gym
import numpy as np
from utils import GRLGym

def custom_reward(state):
    distance_to_target = state["distance_to_target"]
    velocity = state["velocity"]
    
    return -distance_to_target + 0.1 * velocity  # Example: Encourage moving toward target

if __name__ == "__main__":
    env = GRLGym()

    obs, _ = env.reset()
    done = False

    while not done:
        action = np.random.uniform(0, 1, size=(3,))  # Example action
        obs, _, done, _, state = env.step(action)
        
        reward = custom_reward(state)  # User-defined reward
        print(f"Reward: {reward}")