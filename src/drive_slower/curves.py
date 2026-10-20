"""Tidy data frames of model output, for charting."""

from collections.abc import Iterable, Mapping
from dataclasses import replace

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from drive_slower import scenarios as sc
from drive_slower.speed_model import (
    COMPONENTS,
    Ranges,
    Scenario,
    Vehicle,
    cost_breakdown,
    monte_carlo,
    optimal_speed,
)

SPEEDS = np.arange(60.0, 150.5, 1.0)


def with_options(
    s: Scenario,
    *,
    energy_price: float | None = None,
    crash_scale: float = 1.0,
    maintenance: bool = True,
    refuel: bool = True,
    co2: bool = False,
) -> Scenario:
    """Apply the demo's toggles to a preset scenario."""
    return replace(
        s,
        energy_price=s.energy_price if energy_price is None else energy_price,
        crash=replace(s.crash, cost_per_km=s.crash.cost_per_km * crash_scale),
        maintenance=s.maintenance if maintenance else None,
        vehicle=s.vehicle if refuel else replace(s.vehicle, stop_minutes=0),
        co2_price=sc.CO2_SOCIAL_PRICE if co2 else 0.0,
    )


def cost_curve(
    s: Scenario, annual_km: float, speeds: Iterable[float] = SPEEDS
) -> pd.DataFrame:
    """Long frame: speed, component, annual cost, plus each speed's total regret."""
    best = optimal_speed(s)
    best_total = sum(cost_breakdown(s, best).values()) * annual_km
    rows = []
    for v in speeds:
        parts = cost_breakdown(s, v)
        regret = sum(parts.values()) * annual_km - best_total
        for c in COMPONENTS:
            rows.append(
                {
                    "speed": v,
                    "component": c,
                    "annual": parts[c] * annual_km,
                    "regret": regret,
                }
            )
    return pd.DataFrame(rows)


def tradeoff(s: Scenario, v: float, annual_km: float) -> pd.DataFrame:
    """Change in annual cost by component from driving v instead of the limit."""
    at_v, at_limit = cost_breakdown(s, v), cost_breakdown(s, s.road.limit)
    return pd.DataFrame(
        {"component": c, "change": (at_v[c] - at_limit[c]) * annual_km}
        for c in COMPONENTS
    )


def hours_saved(s: Scenario, v: float, annual_km: float) -> float:
    """Hours per year saved by driving v instead of the limit."""
    return annual_km * (1 / s.road.limit - 1 / v)


def waterfall(s: Scenario) -> pd.DataFrame:
    """Best speed as each cost is added in turn, ending at optimal_speed(s)."""
    bare = replace(
        s,
        crash=replace(s.crash, cost_per_km=0.0, deviation_penalty=0.0),
        maintenance=None,
        vehicle=replace(s.vehicle, stop_minutes=0),
        co2_price=0.0,
    )
    steps: list[tuple[str, Scenario]] = [("Time + fuel only", bare)]
    if s.vehicle.stop_minutes:
        steps.append(("+ refuelling stops", replace(steps[-1][1], vehicle=s.vehicle)))
    if s.maintenance:
        steps.append(
            ("+ wear & maintenance", replace(steps[-1][1], maintenance=s.maintenance))
        )
    if s.crash.cost_per_km:
        crash = replace(s.crash, deviation_penalty=0.0)
        steps.append(("+ crash risk", replace(steps[-1][1], crash=crash)))
        if s.crash.deviation_penalty:
            steps.append(
                ("+ slower-than-traffic risk", replace(steps[-1][1], crash=s.crash))
            )
    if s.co2_price:
        steps.append(("+ CO₂", replace(steps[-1][1], co2_price=s.co2_price)))

    rows, prev = [], None
    for i, (label, scn) in enumerate(steps):
        speed = optimal_speed(scn)
        start = speed if prev is None else prev
        rows.append({"order": i, "step": label, "start": start, "end": speed})
        prev = speed
    return pd.DataFrame(rows)


def fuel_curves(
    vehicles: Iterable[Vehicle], speeds: Iterable[float] = SPEEDS
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "vehicle": veh.name,
            "unit": veh.energy_unit,
            "speed": v,
            "per_100km": veh.use_per_km(v) * 100,
            "vs_100": veh.use_per_km(v) / veh.use_per_km(100),
        }
        for veh in vehicles
        for v in speeds
    )


def trip_minutes(km: float, speeds: Iterable[float] = SPEEDS) -> pd.DataFrame:
    return pd.DataFrame({"speed": v, "minutes": 60 * km / v} for v in speeds)


def minutes_saved_steps(km: float, step: float = 10) -> pd.DataFrame:
    """Minutes saved on a km-long trip by each extra `step` km/h."""
    lows = np.arange(SPEEDS[0], SPEEDS[-1], step)
    return pd.DataFrame(
        {
            "band": f"{lo:.0f}→{lo + step:.0f}",
            "low": lo,
            "saved": 60 * km / lo - 60 * km / (lo + step),
        }
        for lo in lows
    )


def race(km: float, you: float, other: float) -> pd.DataFrame:
    """Where each car is when the first one arrives."""
    t = km / max(you, other)
    return pd.DataFrame(
        [
            {"car": f"You ({you:.0f})", "speed": you, "km": min(you * t, km)},
            {"car": f"Limit ({other:.0f})", "speed": other, "km": min(other * t, km)},
        ]
    )


def time_value_steps(wage: float, marginal_tax: float, share: float) -> pd.DataFrame:
    """Gross wage → after-tax → what the demo values commute time at, $/hr."""
    return pd.DataFrame(
        [
            {"step": "Your wage (before tax)", "value": wage},
            {"step": "After tax", "value": wage * (1 - marginal_tax)},
            {"step": "Typical commute value (research)", "value": wage * 0.5},
            {"step": "This page uses", "value": wage * share},
        ]
    )


def wear_and_stops(
    s: Scenario, annual_km: float, speeds: Iterable[float] = SPEEDS
) -> pd.DataFrame:
    """Maintenance $/yr and refuelling stops/yr by speed."""
    rows = []
    for v in speeds:
        maint = s.maintenance.cost(v, s.vehicle) if s.maintenance else 0.0
        stops = annual_km * s.vehicle.use_per_km(v) / s.vehicle.fill_size
        rows.append(
            {
                "speed": v,
                "metric": "Wear & maintenance ($/yr)",
                "value": maint * annual_km,
            }
        )
        rows.append({"speed": v, "metric": "Refuelling stops per year", "value": stops})
    return pd.DataFrame(rows)


def crash_multiplier(s: Scenario, speeds: Iterable[float] = SPEEDS) -> pd.DataFrame:
    """Crash risk relative to driving at the flow of traffic: all harm, and deaths."""
    unit = replace(s.crash, cost_per_km=1.0)
    deaths = replace(unit, shares=(1.0, 0.0, 0.0))
    return pd.DataFrame(
        {
            "speed": v,
            "multiplier": unit.cost(v, s.road.flow),
            "fatal": deaths.cost(v, s.road.flow),
        }
        for v in speeds
    )


def road_deaths(
    s: Scenario, vehicles_per_day: float, length_km: float, speeds: Mapping[str, float]
) -> pd.DataFrame:
    """Expected deaths per year on a stretch if all traffic averaged each speed.

    This is the power model's home turf: it was built from changes in the average
    speed of all traffic on a road.
    """
    vkm = vehicles_per_day * length_km * 365
    fatal = replace(s.crash, cost_per_km=1.0, shares=(1.0, 0.0, 0.0))
    return pd.DataFrame(
        {
            "label": label,
            "speed": v,
            "deaths": sc.FATALITY_RATE * vkm * fatal.cost(v, s.road.flow),
        }
        for label, v in speeds.items()
    )


def uncertainty(
    cases: Mapping[str, Scenario], ranges: Ranges, n: int = 1000, seed: int = 0
) -> pd.DataFrame:
    """Monte Carlo best speeds, one row per draw per case."""
    return pd.DataFrame(
        {"case": name, "speed": v}
        for name, s in cases.items()
        for v in monte_carlo(s, ranges, n=n, seed=seed).speeds
    )
