"""RGB frames drawn from the game state, for pixel-based agents (`render_mode="rgb_array"`).

A game launched by the Python client runs headless (no renderer), so frames are drawn here from the state
dict the game replies with. The same state and inputs always give the same pixels.

Layout of a `size` x `size` frame:
- HUD strip (top): pad locator (white tick = rocket, cyan block = pad, square-root distance scale up to
  `PAD_LOCATOR_RANGE` px of surface arc, pinned to the edge beyond), then propellant (orange), hull integrity
  (green) and legs extension (grey) bars.
- Main view: `view` px of world across, camera above the rocket with the local vertical pointing up. The ground
  sits near the bottom while the rocket is low and the camera climbs with it otherwise. Drawn: sky darkening
  with altitude through the atmosphere, the planet surface (stripes every `STRIPE` px of arc so sideways motion
  is visible), the landing pad (green once landed), the rocket (red nose, legs, flames for the inputs of the
  last step, explosion on crash), a magenta velocity marker (length grows with the square root of the speed)
  and an altitude gauge on the right edge (log scale up to `ALTITUDE_RANGE` px).
"""
import math
from typing import Mapping, Optional

import numpy as np
from PIL import Image, ImageDraw

# Geometry copied from the Godot scenes (rocket local space, px, y down, origin at the bottom of the hull).
ROCKET_HULL = [(16, 0), (16.5, -41.5), (11, -53), (11.5, -81.5), (8, -101.5), (0, -119), (-8, -101.5),
               (-10.5, -81), (-10.5, -53), (-16.5, -40.5), (-16.5, 0)]   # CollisionPolygon2D * 0.5
ROCKET_NOSE = [(8, -101.5), (0, -119), (-8, -101.5)]
ROCKET_TOP = 119.0
CENTER_OF_MASS = (0.0, -26.0)
LEG_HINGE = (13.0, -18.0)        # rocket.gd LEG_HINGE (right leg, mirrored for the left)
LEG_FOOT_X = 27.0                # rocket.gd LEG_FOOT_X
LEG_LENGTH = 30.0                # rocket.gd LEG_LENGTH
LEG_STOWED = (0.06, -1.0)        # legs_visual.gd STOWED_DIR
LEG_STOWED_LENGTH = 26.0         # legs_visual.gd STOWED_LENGTH
RCS_NOZZLE = (16.0, -73.5)       # ParticulesRT; the left nozzle is mirrored
PAD_DECK = 8.0                   # pad thickness above the surface (px)

PAD_LOCATOR_RANGE = 2000.0       # px of surface arc mapped onto the half width of the pad locator
ALTITUDE_RANGE = 20000.0         # px, top of the altitude gauge
STRIPE = 100.0                   # px of surface arc per ground stripe
NOMINAL_PROPELLANT = 100.0       # rocket.gd `propellant` at launch

SPACE, SKY, CRUST = np.array([6, 8, 18]), np.array([72, 122, 192]), np.array([196, 136, 92])
GROUND = (np.array([150, 92, 60]), np.array([126, 76, 50]))   # alternating stripes
HULL, OUTLINE, NOSE = (228, 230, 236), (36, 40, 48), (214, 56, 46)
LEG, FOOT = (150, 156, 168), (190, 194, 202)
FLAME, FLAME_CORE, RCS_FLAME = (255, 150, 40), (255, 236, 170), (190, 215, 255)
PAD, PAD_TOP, PAD_VICTORY = (40, 48, 60), (60, 230, 255), (90, 255, 120)
VELOCITY = (255, 80, 210)
HUD_BG, HUD_TRACK, HUD_TICK = (14, 16, 22), (70, 74, 86), (240, 240, 240)
PROPELLANT_BAR, INTEGRITY_BAR, LEGS_BAR, ALTITUDE_BAR = (255, 160, 40), (90, 220, 110), (200, 200, 212), (190, 205, 255)
EXPLOSION = ((255, 120, 30), (255, 210, 60), (255, 250, 220))

SUPERSAMPLE = 2

# Background palette, indexed per pixel: sky by atmosphere level, then both ground stripes by depth shade.
_SKY_LEVELS, _SHADE_LEVELS, _SHADE_MIN = 256, 64, 0.55
_GROUND_INDEX = _SKY_LEVELS
_CRUST_INDEX = _SKY_LEVELS + 2 * _SHADE_LEVELS
_PALETTE = np.concatenate([
    SPACE + (SKY - SPACE) * np.linspace(0.0, 1.0, _SKY_LEVELS)[:, None],
    GROUND[0] * np.linspace(_SHADE_MIN, 1.0, _SHADE_LEVELS)[:, None],
    GROUND[1] * np.linspace(_SHADE_MIN, 1.0, _SHADE_LEVELS)[:, None],
    CRUST[None],
]).round().astype(np.uint8)


def _rotate(point, angle):
    c, s = math.cos(angle), math.sin(angle)
    return point[0] * c - point[1] * s, point[0] * s + point[1] * c


class _Camera:
    """World (Godot, y down) -> supersampled pixel coordinates of the main view."""

    def __init__(self, center, up, scale, origin):
        self.cx, self.cy = center
        self.ux, self.uy = up
        self.rx, self.ry = -up[1], up[0]   # screen right: positive surface arc direction (landing_pad_distance)
        self.scale = scale
        self.ox, self.oy = origin           # pixel position of `center`

    def __call__(self, x, y):
        dx, dy = x - self.cx, y - self.cy
        return (self.ox + (dx * self.rx + dy * self.ry) * self.scale,
                self.oy - (dx * self.ux + dy * self.uy) * self.scale)


def render_state(state: Mapping, inputs: Optional[Mapping] = None, size: int = 128, view: float = 640.0) -> np.ndarray:
    """Draw `state` (a GRL state dict) as a `(size, size, 3)` uint8 RGB array.

    `inputs` are the thruster inputs applied during the step that produced `state` (drawn as flames).
    `view` is the width of the main view in world px (the rocket is 119 px tall).
    """
    if size < 16:
        raise ValueError("size must be at least 16 px")
    inputs = inputs or {}
    ss = SUPERSAMPLE
    S = size * ss
    hud_h = max(4, round(size * 0.14)) * ss
    main_h = S - hud_h
    scale = S / float(view)                     # supersampled px per world px

    planet = np.asarray(state["planet_position"], dtype=np.float64)
    radius = float(state["planet_radius"])
    atmosphere = max(float(state.get("planet_atmosphere_size", 600.0)), 1.0)
    pos = np.asarray(state["position"], dtype=np.float64)
    rel = pos - planet
    dist = float(np.hypot(*rel)) or 1.0
    up = rel / dist
    altitude = dist - radius
    phi = math.atan2(rel[1], rel[0])

    # Camera above the rocket's surface point: ground at 85 % of the main view while the rocket fits,
    # otherwise it follows the rocket (nose kept below a top margin).
    view_h = main_h / scale
    cam_alt = max(0.35 * view_h, altitude + ROCKET_TOP + 0.08 * view_h - 0.5 * view_h)
    center = planet + up * (radius + cam_alt)
    cam = _Camera(center, up, scale, (S / 2.0, hud_h + main_h / 2.0))

    # Background, per pixel: distance to the planet centre gives sky / ground, the angle gives the stripes.
    # float32 is precise to ~0.01 px here, even for the largest planets.
    f32 = np.float32
    cols = ((np.arange(S) + 0.5 - S / 2.0) / scale).astype(f32)[None, :]                        # screen right
    radial = (radius + cam_alt - (np.arange(hud_h, S) + 0.5 - (hud_h + main_h / 2.0)) / scale).astype(f32)[:, None]
    alt = np.hypot(radial, cols) - f32(radius)
    sky = np.clip(f32(1.0) - alt / f32(atmosphere), 0.0, 1.0)
    index = (sky * sky * f32(_SKY_LEVELS - 1) + f32(0.5)).astype(np.int16)
    underground = alt < 0.0
    if underground.any():
        stripes = max(1, round(2.0 * math.pi * radius / STRIPE))
        angle = np.arctan2(cols, radial) + f32(phi + math.pi)
        stripe = (np.floor(angle * f32(stripes / (2.0 * math.pi))).astype(np.int32) % 2).astype(np.int16)
        shade = np.clip(alt / f32(0.6 * view_h) + f32(1.0 - _SHADE_MIN), 0.0, 1.0 - _SHADE_MIN)   # darker deeper
        ground = (_GROUND_INDEX + stripe * _SHADE_LEVELS
                  + (shade * f32((_SHADE_LEVELS - 1) / (1.0 - _SHADE_MIN)) + f32(0.5)).astype(np.int16))
        crust = 1.5 * ss / scale            # world px of a 1.5 output px crust line, whatever the zoom
        ground[alt > -crust] = _CRUST_INDEX
        index = np.where(underground, ground, index)

    canvas = np.empty((S, S, 3), dtype=np.uint8)
    canvas[:hud_h] = HUD_BG
    canvas[hud_h:] = _PALETTE[index]
    image = Image.fromarray(canvas)
    draw = ImageDraw.Draw(image)

    def width(world_px, minimum=1.0):
        return max(1, round(max(world_px * scale, minimum * ss)))

    # Landing pad, flush with the surface
    if "landing_pad_position" in state:
        pad = np.asarray(state["landing_pad_position"], dtype=np.float64)
        normal = (pad - planet) / (float(np.hypot(*(pad - planet))) or 1.0)
        tangent = np.array([-normal[1], normal[0]])
        half = float(state.get("landing_pad_width", 90.0)) / 2.0
        corners = [pad - tangent * half, pad + tangent * half,
                   pad + tangent * half + normal * PAD_DECK, pad - tangent * half + normal * PAD_DECK]
        draw.polygon([cam(*c) for c in corners], fill=PAD)
        top = PAD_VICTORY if state.get("game_state") == "victory" else PAD_TOP
        draw.line([cam(*corners[3]), cam(*corners[2])], fill=top, width=width(3.0))
        for side in (-1.0, 1.0):
            base = pad + tangent * side * half
            draw.line([cam(*base), cam(*(base + normal * 18.0))], fill=top, width=width(3.0))

    rotation = float(state.get("rotation", 0.0))

    def to_screen(local):
        x, y = _rotate(local, rotation)
        return cam(pos[0] + x, pos[1] + y)

    crashed = state.get("game_state") == "crash" or float(state.get("rocket_integrity", 1.0)) <= 0.0
    if not crashed:
        # Velocity marker from the centre of mass, drawn first so the rocket stays visible on top of it
        vx, vy = (float(v) for v in state.get("linear_velocity", (0.0, 0.0)))
        speed = math.hypot(vx, vy)
        if speed > 1e-3:
            length = min(12.0 * math.sqrt(speed), 0.45 * view)
            com_x, com_y = _rotate(CENTER_OF_MASS, rotation)
            start = (pos[0] + com_x, pos[1] + com_y)
            end = cam(start[0] + vx / speed * length, start[1] + vy / speed * length)
            draw.line([cam(*start), end], fill=VELOCITY, width=width(0.0, 1.0))
            dot = 1.2 * ss
            draw.ellipse([end[0] - dot, end[1] - dot, end[0] + dot, end[1] + dot], fill=VELOCITY)

    can_thrust = (not crashed and float(state.get("propellant", 1.0)) > 0.0
                  and float(state.get("rocket_integrity", 1.0)) >= 0.05)
    if can_thrust:
        main = float(np.clip(inputs.get("main_thrust", 0.0), 0.0, 1.0))
        if main > 0.02:
            length = 14.0 + 56.0 * main
            draw.polygon([to_screen(p) for p in ((-8.0, 0.0), (8.0, 0.0), (0.0, length))], fill=FLAME)
            draw.polygon([to_screen(p) for p in ((-4.0, 0.0), (4.0, 0.0), (0.0, length * 0.55))], fill=FLAME_CORE)
        for key, side in (("rcs_left_thrust", -1.0), ("rcs_right_thrust", 1.0)):
            power = float(np.clip(inputs.get(key, 0.0), 0.0, 1.0))
            if power > 0.02:
                # rcs_left pushes the rocket to the right: its exhaust leaves on the left side
                nx, ny = RCS_NOZZLE[0] * side, RCS_NOZZLE[1]
                tip = nx + side * (8.0 + 26.0 * power)
                draw.polygon([to_screen(p) for p in ((nx, ny - 4.0), (nx, ny + 4.0), (tip, ny))], fill=RCS_FLAME)

    # Legs: strut from the hinge to the foot, swinging from stowed to deployed with legs_extension
    t = float(np.clip(state.get("legs_extension", 0.0), 0.0, 1.0))
    t = t * t * (3.0 - 2.0 * t)   # smoothstep, as in legs_visual.gd
    deployed = (LEG_FOOT_X - LEG_HINGE[0], LEG_LENGTH)
    stowed_angle = math.atan2(LEG_STOWED[1], LEG_STOWED[0])
    leg_angle = stowed_angle + (math.atan2(deployed[1], deployed[0]) - stowed_angle) * t
    leg_length = LEG_STOWED_LENGTH + (math.hypot(*deployed) - LEG_STOWED_LENGTH) * t
    for side in (-1.0, 1.0):
        hinge = (LEG_HINGE[0] * side, LEG_HINGE[1])
        foot = (hinge[0] + side * math.cos(leg_angle) * leg_length, hinge[1] + math.sin(leg_angle) * leg_length)
        draw.line([to_screen(hinge), to_screen(foot)], fill=LEG, width=width(4.0))
        if t > 0.5:
            draw.line([to_screen((foot[0] - 6.0, foot[1])), to_screen((foot[0] + 6.0, foot[1]))],
                      fill=FOOT, width=width(3.0))

    hull = [to_screen(p) for p in ROCKET_HULL]
    draw.polygon(hull, fill=HULL)
    draw.line(hull + [hull[0]], fill=OUTLINE, width=width(1.5, 0.5))
    draw.polygon([to_screen(p) for p in ROCKET_NOSE], fill=NOSE)

    if crashed:
        com = to_screen(CENTER_OF_MASS)
        for color, r in zip(EXPLOSION, (70.0, 45.0, 20.0)):
            rr = r * scale
            draw.ellipse([com[0] - rr, com[1] - rr, com[0] + rr, com[1] + rr], fill=color)

    # Altitude gauge (right edge of the main view, log scale)
    gauge_w = max(2 * ss, round(size / 40) * ss)
    fill = math.log1p(max(altitude, 0.0)) / math.log1p(ALTITUDE_RANGE)
    top = S - round(min(fill, 1.0) * (main_h - 2 * ss)) - ss
    draw.rectangle([S - gauge_w, hud_h, S - 1, S - 1], fill=HUD_BG)
    if top < S - ss:
        draw.rectangle([S - gauge_w + ss // 2, top, S - 1 - ss // 2, S - 1 - ss], fill=ALTITUDE_BAR)

    # HUD strip: pad locator, then propellant / integrity / legs bars
    margin = 2 * ss
    row = hud_h // 2
    left, right = margin, S - margin
    mid = (left + right) / 2.0
    draw.line([(left, row / 2.0), (right, row / 2.0)], fill=HUD_TRACK, width=ss)
    if "landing_pad_distance" in state:
        d = float(state["landing_pad_distance"])
        offset = math.copysign(math.sqrt(min(abs(d), PAD_LOCATOR_RANGE) / PAD_LOCATOR_RANGE), d)
        x = mid + offset * (right - left - 4 * ss) / 2.0
        draw.rectangle([x - 2 * ss, ss, x + 2 * ss, row - ss], fill=PAD_TOP)
    draw.rectangle([mid - ss / 2.0, 0, mid + ss / 2.0, row], fill=HUD_TICK)
    gauges = (
        (float(state.get("propellant", 0.0)) / NOMINAL_PROPELLANT, PROPELLANT_BAR),
        (float(state.get("rocket_integrity", 0.0)), INTEGRITY_BAR),
        (t, LEGS_BAR),
    )
    slot = (right - left) / len(gauges)
    for i, (value, color) in enumerate(gauges):
        x0 = left + i * slot + ss
        x1 = left + (i + 1) * slot - ss
        draw.rectangle([x0, row + ss, x1, hud_h - ss], fill=HUD_TRACK)
        value = min(max(value, 0.0), 1.0)
        if value > 0.0:
            draw.rectangle([x0, row + ss, x0 + (x1 - x0) * value, hud_h - ss], fill=color)

    return np.asarray(image.reduce(ss), dtype=np.uint8)
