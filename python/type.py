from typing import Tuple, TypedDict

class RocketState(TypedDict):
    position: Tuple[float, float]
    linear_velocity: Tuple[float, float]
    angular_velocity: float
    rotation: float  # from -pi to pi
    num_frame_computed: int
    rocket_integrity: float  # 0 to 1
    propellant: int
    temperature: float
    mass: float
    left_leg_contact: bool
    right_leg_contact: bool

class PlanetState(TypedDict):
    planet_radius: float
    planet_atmosphere_size: float
    planet_mass: str
    planet_position: Tuple[float, float]

class WindState(TypedDict):
    wind_force: Tuple[float, float]
    wind_direction: Tuple[float, float]

class State(RocketState, PlanetState, WindState):
    pass