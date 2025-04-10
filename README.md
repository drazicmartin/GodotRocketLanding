# GodotRocketLanding (GRL)
A simple programmable rocket landing environment

![](assets/thumbnail.png)

## Lore

In 2147, Earth’s orbital elevators collapsed during a solar storm, severing all high-bandwidth connections to Mars. With a fleet of 1,000 automated rockets en route, each carrying critical resources, manual control from Earth became impossible. Only a narrow data channel remains, just enough to send one final program. You must design a landing algorithm capable of autonomously guiding every rocket through Mars atmosphere, without a single mistake. **Failure isn’t an option. One mistake, and years of progress would crash and burn.**

## Usage

### Python usage
```bash
# in your virtual env
pip install websockets
pip install gymnasium

# For simple handmade landing
python python/simple_landing.py

# For PPO learning landing, see
python python/simple_ppo.py --help
# then evaluate with
python python/enjoy.py --ckpt CHECKPOINT_PATH

# Or implement your own RL algo (DQ-learning, ...)
```

### Rocket control
You can control only 3 Thrusters
```python
{
    "main_thrust"     : float(0-1),
    "rcs_left_thrust" : float(0-1),
    "rcs_right_thrust": float(0-1)
}
```

### Environment State
```python
{
    ## Rocket State
    'position': tuple(x,y),          # Rocket position
    'linear_velocity': tuple(x,y),   # Rocket linear velocity in pixels per second
    'angular_velocity': float,       # La vitesse de rotation de Rocket en radians par seconde.
    'rotation': float(-pi - pi),     # Rocket's rotation in radians
    'num_frame_computed': int,       # Number of frame since start
    'rocket_integrity': float(0-1),  # Integrity of the rocket, at 0.05, BOOOOOM...
    'propellant': int,               # Proppellant remaining
    'temperature': float,            # Rocket's temperature, at somepoint it will melt
    'mass': float,                   # The total mass of the rocket, change according to propellant left.
    'left_leg_contact': bool,        # Rocket left  leg on ground ?
    'right_leg_contact': bool,       # Rocket right leg on ground ?

    ## Planet State
    'planet_radius': float,
    'planet_atmosphere_size': float,
    'planet_mass': str,
    'planet_position': tuple(x,y),

    ## Wind State
    'wind_force': tuple(x,y),
    'wind_direction': tuple(x,y),
}
```

## Roadmap

- [X] Rocket control and state
- [X] Python controllable
    - [X] Control by overriding `GRL.process` method
    - [X] run in batch mode
- [X] Thruster and RCS
- [X] Propellant System
    - [X] Propellant Tank
    - [X] Mass updating
- [X] Wind System
- [X] Planet as sphere and dynamic gravity
- [X] Support Big Number
- [X] Atmospheric system
    - [X] Visual Atmosphere (Shader)
    - [X] Atmospheric damage
        - [X] Hull stress damage
        - [X] Thermal damage
    - [X] Atmospheric drag
        - $F_d​=\frac{1}{2} * ​C_d * ρ * v^2 * A$
            - C_d​: Drag coefficient (depends on the rocket's shape and surface roughness)
            - ρ: Air density (varies with altitude)
            - v: Rocket velocity relative to the air
            - A: Cross-sectional area of the rocket
        - $ρ=ρ_0 * ​exp(−\frac{h}{H​})$
- [ ] Add an emergency ejection with parachute
- [X] Levels
    - Level 1
    - Level 2
    - Level 3
    - Level 4
    - Random
      - [X] easy
      - [X] moderate
      - [X] hard

## Thanks
- [The1Muneeb](https://deep-fold.itch.io/space-background-generator), for space background generator.
- [Simon Celeste](https://github.com/Celeste-VANDAMME), for the design of the rocket !
- [Kenney.nl](https://www.kenney.nl/), for the particules sprite
- [Sinestesia Studio](https://itch.io/profile/sinestesia), for explosion animation
- [ChronoDK](https://github.com/ChronoDK/GodotBigNumberClass), for Big Number class
- [chatGPT](https://chatgpt.com/), for wise advice and tips