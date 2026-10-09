"""GodotRocketLanding's pixel environment; importing never starts a simulator."""
from .env import RocketLandingEnv, make_env

__all__ = ["RocketLandingEnv", "make_env"]
