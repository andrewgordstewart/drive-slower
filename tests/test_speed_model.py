from dataclasses import replace

import pytest

from drive_slower import scenarios as sc
from drive_slower.speed_model import (
    CrashModel,
    Ranges,
    Road,
    Scenario,
    cost_breakdown,
    monte_carlo,
    optimal_speed,
)


def bare(vot: float = 20.0, flow: float = 100.0) -> Scenario:
    """Time + energy only."""
    return Scenario(
        vehicle=sc.F150,
        road=Road("test", limit=100, flow=flow),
        energy_price=1.70,
        value_of_time=vot,
        crash=CrashModel(0.0),
        maintenance=None,
    )


def test_fuel_curve_passes_through_calibration_points() -> None:
    assert sc.F150.use_per_km(100) * 100 == pytest.approx(10.6)
    assert sc.F150.use_per_km(120) * 100 == pytest.approx(13.3)


def test_time_plus_energy_matches_closed_form() -> None:
    s = replace(bare(), vehicle=replace(sc.F150, stop_minutes=0))
    _, b = sc.F150.coeffs
    expected = (s.value_of_time / (2 * s.energy_price * b)) ** (1 / 3)
    assert optimal_speed(s) == pytest.approx(expected, abs=0.1)


def test_crash_cost_is_anchored_at_each_roads_flow() -> None:
    crash = CrashModel(0.05)
    assert crash.cost(105, flow=105) == pytest.approx(0.05)
    assert crash.cost(120, flow=120) == pytest.approx(0.05)
    assert crash.cost(120, flow=105) > 0.05


def test_deviation_penalty_pulls_optimum_toward_flow() -> None:
    s = replace(bare(), crash=CrashModel(0.05))
    with_penalty = replace(s, crash=CrashModel(0.05, deviation_penalty=20))
    assert optimal_speed(s) < optimal_speed(with_penalty) < s.road.flow


def test_refuel_time_is_proportional_to_energy_use() -> None:
    s = bare()
    got = cost_breakdown(s, 100)["refuel"]
    stops_per_km = sc.F150.use_per_km(100) / sc.F150.fill_size
    assert got == pytest.approx(s.value_of_time * 10 / 60 * stops_per_km)


def test_private_perspective_has_no_co2_cost() -> None:
    assert cost_breakdown(sc.scenario(perspective="private"), 100)["co2"] == 0
    assert cost_breakdown(sc.scenario(perspective="social"), 100)["co2"] > 0


def test_monte_carlo_is_reproducible_and_inside_bounds() -> None:
    a = monte_carlo(sc.scenario(), Ranges(), n=50, seed=1)
    b = monte_carlo(sc.scenario(), Ranges(), n=50, seed=1)
    assert (a.speeds == b.speeds).all()
    assert a.share_at_bound == 0
