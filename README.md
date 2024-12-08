# GodotRocketLanding (GRL)
A simple programmable rocket landing environment

![](assets/thumbnail.png)

## Usage

### Python usage
```bash
# in your virtual env
pip install websockets

python python/simple_landing.py
# Or 
python python/batch_simple_landing.py
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

### Rocket State
```python
{
    'position': tuple(x,y),
    'velocity': tuple(x,y),
    'rotation': float(-pi - pi),
    'num_frame_computed': int,
    'rocket_integrity': float(0-1),
    'propellant': int,
    'wind': tuple(x,y),
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
- [ ] Atmospheric system
    - [X] Visual Atmosphere
    - [ ] Atmospheric damage
    - [ ] Atmospheric viscosity
- [ ] Levels

## Thanks
- [The1Muneeb](https://deep-fold.itch.io/space-background-generator), for space background generator.
- [Simon Celeste](https://github.com/Celeste-VANDAMME), for the design of the rocket !
- [Kenney.nl](https://www.kenney.nl/), for the particules sprite
- [Sinestesia Studio](https://itch.io/profile/sinestesia), for explosion animation
