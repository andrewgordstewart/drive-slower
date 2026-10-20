"""Print the speed analysis: `uv run python -m drive_slower`."""

from dataclasses import replace

from drive_slower import scenarios as sc
from drive_slower.speed_model import (
    COMPONENTS,
    Ranges,
    cost_breakdown,
    cost_per_km,
    monte_carlo,
    optimal_speed,
)


def breakdown_table() -> None:
    s = sc.scenario()
    opt = optimal_speed(s)
    ref = cost_breakdown(s, s.road.limit)
    print(f"1) {s.vehicle.name} on {s.road.name}, private, ${s.value_of_time:.0f}/hr")
    print(
        f"   optimum {opt:.0f} km/h (limit {s.road.limit:.0f}, flow {s.road.flow:.0f})"
    )
    print(f"   annual change vs driving the limit, {sc.ANNUAL_KM:,} km at free flow")
    print(
        "   km/h "
        + "".join(f"{c:>12}" for c in COMPONENTS)
        + f"{'total':>9}{'hours':>8}"
    )
    for v in (80, 90, round(opt), 100, 110, 120):
        d = {c: (x - ref[c]) * sc.ANNUAL_KM for c, x in cost_breakdown(s, v).items()}
        hours = sc.ANNUAL_KM * (1 / v - 1 / s.road.limit)
        print(
            f"   {v:>4} "
            + "".join(f"{d[c]:>+12.0f}" for c in COMPONENTS)
            + f"{sum(d.values()):>+9.0f}{hours:>+8.0f}"
        )


def optimum_grid() -> None:
    print("\n2) Optimum km/h by vehicle, road and perspective")
    roads = list(sc.ROADS)
    print(f"   {'':<17}{'':<9}" + "".join(f"{r[:26]:>28}" for r in roads))
    for veh in sc.VEHICLES:
        for p in ("private", "social"):
            cells = []
            for r in roads:
                s = sc.scenario(veh, r, p)
                cells.append(f"{optimal_speed(s):.0f} (limit {s.road.limit:.0f})")
            print(f"   {veh.name:<17}{p:<9}" + "".join(f"{c:>28}" for c in cells))


def deviation_sensitivity() -> None:
    print("\n3) Solomon-style penalty for leaving the flow (F-150, private)")
    print(
        "   multiplier on crash risk = 1 + k*(v/flow - 1)^2; k=10 means 20% below flow -> 1.4x"
    )
    roads = list(sc.ROADS)
    print(f"   {'k':>4}" + "".join(f"{r[:26]:>28}" for r in roads))
    for k in (0, 5, 10, 20, 40):
        cells = [
            f"{optimal_speed(sc.scenario(road=r, deviation_penalty=k)):.0f}"
            for r in roads
        ]
        print(f"   {k:>4}" + "".join(f"{c:>28}" for c in cells))


def monte_carlo_table() -> None:
    print("\n4) Monte Carlo optimum km/h (2,000 draws; ranges in speed_model.Ranges)")
    print(f"   {'case':<44}{'P10':>6}{'P50':>6}{'P90':>6}{'>limit':>8}{'at bound':>10}")
    cases = [
        ("F-150, Hwy 1, private", sc.scenario(), Ranges()),
        (
            "F-150, Hwy 1, private, deviation k 0-20",
            sc.scenario(),
            Ranges(deviation_penalty=(0, 20)),
        ),
        ("F-150, Hwy 1, social", sc.scenario(perspective="social"), Ranges()),
        ("F-150, Coquihalla, private", sc.scenario(road="Coquihalla"), Ranges()),
        ("Sedan, Hwy 1, private", sc.scenario(sc.SEDAN), Ranges()),
        ("Lightning, Hwy 1, private", sc.scenario(sc.F150_LIGHTNING), Ranges()),
    ]
    for name, s, ranges in cases:
        mc = monte_carlo(s, ranges)
        p10, p50, p90 = mc.percentiles()
        print(
            f"   {name:<44}{p10:>6.0f}{p50:>6.0f}{p90:>6.0f}"
            f"{mc.share_above_limit:>8.0%}{mc.share_at_bound:>10.0%}"
        )


def flatness() -> None:
    s = sc.scenario()
    opt = optimal_speed(s)
    best = cost_per_km(s, opt)
    print("\n5) Annual cost of not driving the optimum (F-150, Hwy 1, private)")
    for v in (90, 100, 110, 120):
        print(f"   {v} km/h: +${(cost_per_km(s, v) - best) * sc.ANNUAL_KM:,.0f}/yr")
    no_crash = replace(s, crash=replace(s.crash, cost_per_km=0.0))
    print(f"   optimum with crash cost removed: {optimal_speed(no_crash):.0f} km/h")


def main() -> None:
    breakdown_table()
    optimum_grid()
    deviation_sensitivity()
    monte_carlo_table()
    flatness()


if __name__ == "__main__":
    main()
