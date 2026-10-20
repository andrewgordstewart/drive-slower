"""Cost-per-km model for choosing a highway cruising speed.

Units throughout: km, km/h, hours, $ (CAD), and the vehicle's energy unit (L or kWh).
Every cost is $ per km driven at a steady speed v:

  time         value_of_time / v
  energy       energy_price * use(v)                  use(v) = a + b*v^2  (rolling + aero)
  refuelling   value_of_time * stop_hours * use(v) / fill_size
  maintenance  tires * (v/100)^k + other * ((1 - s) + s * use(v) / use(100))
  crash        cost_at_flow * sum(share_i * (v/flow)^exp_i) * (1 + dev * (v/flow - 1)^2)
  co2          co2_price * kg_per_unit * use(v)

The crash term is Nilsson's power model anchored at the road's prevailing traffic
speed, not a fixed speed, so a road built for 120 km/h isn't penalised for being one.
`deviation_penalty` optionally adds Solomon-style risk for driving away from the flow
in either direction. The evidence for that is mixed, so it defaults to zero.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import minimize_scalar  # type: ignore[import-untyped]

SPEED_BOUNDS = (60.0, 150.0)


@dataclass(frozen=True)
class Vehicle:
    name: str
    energy_unit: str  # "L" or "kWh"
    use_100: float  # energy units per 100 km at 100 km/h
    use_120: float  # energy units per 100 km at 120 km/h
    co2_kg_per_unit: float
    fill_size: float  # energy units added per refuelling stop
    stop_minutes: float  # time per stop, including the detour; 0 for home charging

    @property
    def coeffs(self) -> tuple[float, float]:
        """Fit use/km = a + b*v^2 through the two calibration points."""
        b = (self.use_120 - self.use_100) / 100 / (120**2 - 100**2)
        return self.use_100 / 100 - b * 100**2, b

    def use_per_km(self, v: float) -> float:
        a, b = self.coeffs
        return a + b * v**2


@dataclass(frozen=True)
class Road:
    name: str
    limit: float  # km/h
    flow: float  # prevailing mean traffic speed, km/h


@dataclass(frozen=True)
class CrashModel:
    # Expected crash cost, $/km, when driving at the road's flow speed.
    cost_per_km: float
    # Serious and minor injuries use one and two less (Nilsson: 4/3/2).
    fatal_exponent: float = 4.0
    # Cost shares: fatal, serious, minor/property.
    shares: tuple[float, float, float] = (0.5, 0.3, 0.2)
    deviation_penalty: float = 0.0

    def cost(self, v: float, flow: float) -> float:
        r = v / flow
        exps = (self.fatal_exponent, self.fatal_exponent - 1, self.fatal_exponent - 2)
        power = sum(s * r**e for s, e in zip(self.shares, exps, strict=True))
        return self.cost_per_km * power * (1 + self.deviation_penalty * (r - 1) ** 2)


@dataclass(frozen=True)
class Maintenance:
    tire_per_km: float = 0.02  # $/km at 100 km/h
    tire_exponent: float = 1.5
    other_per_km: float = 0.04  # $/km, powertrain/brakes/etc.
    load_share: float = 0.3  # share of `other` that scales with energy use

    def cost(self, v: float, vehicle: Vehicle) -> float:
        load = vehicle.use_per_km(v) / vehicle.use_per_km(100)
        tires = self.tire_per_km * (v / 100) ** self.tire_exponent
        fixed = 1 - self.load_share
        return tires + self.other_per_km * (fixed + self.load_share * load)


@dataclass(frozen=True)
class Scenario:
    vehicle: Vehicle
    road: Road
    energy_price: float  # $ per energy unit
    value_of_time: float  # $/hr
    crash: CrashModel
    maintenance: Maintenance | None = Maintenance()
    co2_price: float = 0.0  # $/tonne


COMPONENTS = ("time", "energy", "refuel", "maintenance", "crash", "co2")


def cost_breakdown(s: Scenario, v: float) -> dict[str, float]:
    """$/km by component at speed v."""
    use = s.vehicle.use_per_km(v)
    stop_hours = s.vehicle.stop_minutes / 60
    return {
        "time": s.value_of_time / v,
        "energy": s.energy_price * use,
        "refuel": s.value_of_time * stop_hours * use / s.vehicle.fill_size,
        "maintenance": s.maintenance.cost(v, s.vehicle) if s.maintenance else 0.0,
        "crash": s.crash.cost(v, s.road.flow),
        "co2": s.co2_price / 1000 * s.vehicle.co2_kg_per_unit * use,
    }


def cost_per_km(s: Scenario, v: float) -> float:
    return sum(cost_breakdown(s, v).values())


def optimal_speed(s: Scenario, bounds: tuple[float, float] = SPEED_BOUNDS) -> float:
    res = minimize_scalar(lambda v: cost_per_km(s, v), bounds=bounds, method="bounded")
    return float(res.x)


@dataclass(frozen=True)
class Ranges:
    """Uniform ranges for Monte Carlo draws. Scales multiply the base scenario's value."""

    value_of_time: tuple[float, float] = (16.0, 23.0)
    energy_price_scale: tuple[float, float] = (0.88, 1.12)
    consumption_scale: tuple[float, float] = (0.9, 1.1)
    # Scales the increase in use from 100 to 120 km/h.
    drag_scale: tuple[float, float] = (0.85, 1.15)
    crash_cost_scale: tuple[float, float] = (0.5, 2.0)  # drawn log-uniform
    fatal_exponent: tuple[float, float] = (3.0, 4.5)
    deviation_penalty: tuple[float, float] = (0.0, 0.0)
    tire_per_km: tuple[float, float] = (0.015, 0.03)
    tire_exponent: tuple[float, float] = (1.0, 2.0)
    other_per_km: tuple[float, float] = (0.03, 0.05)
    load_share: tuple[float, float] = (0.2, 0.5)


def sample(base: Scenario, ranges: Ranges, rng: np.random.Generator) -> Scenario:
    def u(r: tuple[float, float]) -> float:
        return float(rng.uniform(*r))

    veh = base.vehicle
    use_100 = veh.use_100 * u(ranges.consumption_scale)
    rise = (veh.use_120 - veh.use_100) * use_100 / veh.use_100 * u(ranges.drag_scale)
    lo, hi = np.log(ranges.crash_cost_scale)
    return replace(
        base,
        vehicle=replace(veh, use_100=use_100, use_120=use_100 + rise),
        energy_price=base.energy_price * u(ranges.energy_price_scale),
        value_of_time=u(ranges.value_of_time),
        crash=replace(
            base.crash,
            cost_per_km=base.crash.cost_per_km * float(np.exp(rng.uniform(lo, hi))),
            fatal_exponent=u(ranges.fatal_exponent),
            deviation_penalty=u(ranges.deviation_penalty),
        ),
        maintenance=Maintenance(
            u(ranges.tire_per_km),
            u(ranges.tire_exponent),
            u(ranges.other_per_km),
            u(ranges.load_share),
        )
        if base.maintenance
        else None,
    )


@dataclass(frozen=True)
class MonteCarloResult:
    speeds: np.ndarray
    limit: float

    def percentiles(self, qs: Sequence[float] = (10, 50, 90)) -> list[float]:
        return [float(x) for x in np.percentile(self.speeds, qs)]

    @property
    def share_above_limit(self) -> float:
        return float(np.mean(self.speeds > self.limit))

    @property
    def share_at_bound(self) -> float:
        lo, hi = SPEED_BOUNDS
        return float(np.mean((self.speeds < lo + 0.5) | (self.speeds > hi - 0.5)))


def monte_carlo(
    base: Scenario, ranges: Ranges | None = None, n: int = 2000, seed: int = 0
) -> MonteCarloResult:
    ranges = ranges or Ranges()
    rng = np.random.default_rng(seed)
    speeds = np.array([optimal_speed(sample(base, ranges, rng)) for _ in range(n)])
    return MonteCarloResult(speeds, base.road.limit)
