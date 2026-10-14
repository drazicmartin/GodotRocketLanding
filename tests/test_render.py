"""State -> RGB renderer (render_mode="rgb_array"); pure functions, no game binary needed."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grl import render  # noqa: E402
from grl.render import render_state  # noqa: E402


def state(**overrides):
    s = {
        "position": [0.0, -150.0],            # 150 px above the surface of the default planet
        "linear_velocity": [0.0, 0.0],
        "angular_velocity": 0.0,
        "rotation": 0.0,
        "rocket_integrity": 1.0,
        "propellant": 100.0,
        "legs_extension": 0.0,
        "planet_radius": 50000.0,
        "planet_atmosphere_size": 600.0,
        "planet_position": [0.0, 50000.0],
        "landing_pad_position": [100.0, -0.1],
        "landing_pad_width": 90.0,
        "landing_pad_distance": 100.0,
    }
    s.update(overrides)
    return s


def count(image, color, tol=12):
    return int((np.abs(image.astype(int) - np.array(color)).max(axis=-1) <= tol).sum())


def main_view(image, size):
    return image[max(4, round(size * 0.14)):]


def test_shape_dtype_and_determinism():
    for size in (16, 64, 100):
        image = render_state(state(), size=size)
        assert image.shape == (size, size, 3) and image.dtype == np.uint8
    a = render_state(state(), {"main_thrust": 1.0}, size=64)
    assert np.array_equal(a, render_state(state(), {"main_thrust": 1.0}, size=64))
    assert not np.array_equal(a, render_state(state(), size=64))   # the flame is drawn
    with pytest.raises(ValueError):
        render_state(state(), size=8)


def test_pad_rocket_ground_and_hud_are_drawn():
    image = render_state(state(), size=128)
    view = main_view(image, 128)
    pad_cols = np.nonzero((np.abs(view.astype(int) - render.PAD_TOP).max(-1) <= 12).any(0))[0]
    # pad 100 px right of the rocket, 640 px across the view: ~20 px right of the centre
    assert pad_cols.size and 70 < pad_cols.mean() < 100
    assert count(view, render.HULL) > 20 and count(view, render.NOSE) > 0
    assert count(view, render.GROUND[0], 30) + count(view, render.GROUND[1], 30) > 500
    hud = image[:round(128 * 0.14)]
    assert count(hud, render.PROPELLANT_BAR) > 20 and count(hud, render.INTEGRITY_BAR) > 20
    assert count(hud, render.LEGS_BAR) == 0   # legs retracted


def test_far_pad_only_in_locator_and_high_rocket_sees_space():
    image = render_state(state(landing_pad_position=[1500.0, -22.5], landing_pad_distance=1500.0), size=128)
    hud_h = round(128 * 0.14)
    assert count(image[hud_h:], render.PAD_TOP) == 0
    locator = np.nonzero((np.abs(image[:hud_h].astype(int) - render.PAD_TOP).max(-1) <= 12).any(0))[0]
    assert locator.size and locator.mean() > 96   # right part of the locator
    space = main_view(render_state(state(position=[0.0, -5000.0]), size=64), 64)
    assert count(space, render.GROUND[0], 30) + count(space, render.GROUND[1], 30) == 0
    assert np.median(space.reshape(-1, 3), axis=0).max() < 30   # black sky above the atmosphere


def test_crash_victory_and_legs():
    assert count(render_state(state(game_state="crash", rocket_integrity=0.0), size=64), render.EXPLOSION[1]) > 10
    on_pad = state(position=[100.0, -12.0], landing_pad_distance=0.0, legs_extension=1.0, game_state="victory")
    image = render_state(on_pad, size=64)
    view = main_view(image, 64)   # the HUD pad locator stays cyan
    assert count(view, render.PAD_VICTORY) > 0 and count(view, render.PAD_TOP) == 0
    assert count(image[:round(64 * 0.14)], render.LEGS_BAR) > 0


def test_small_planet_surface_is_curved_and_pad_is_optional():
    small = state(planet_radius=1200.0, planet_position=[0.0, 1200.0])
    for key in ("landing_pad_position", "landing_pad_width", "landing_pad_distance"):
        small.pop(key)   # scenes without a pad (debug)
    view = main_view(render_state(small, size=128), 128)
    ground = (np.abs(view.astype(int) - render.CRUST).max(-1) <= 30)
    first_row = [np.argmax(ground[:, c]) for c in (2, 64, 120)]
    assert first_row[1] < first_row[0] - 3 and first_row[1] < first_row[2] - 3   # higher in the middle
