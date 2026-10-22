import pytest

from drive_slower import charts, curves
from drive_slower import scenarios as sc
from drive_slower.speed_model import COMPONENTS, Ranges, optimal_speed


def test_cost_curve_has_every_component_and_zero_regret_at_best() -> None:
    s = sc.scenario()
    best = optimal_speed(s)
    df = curves.cost_curve(s, sc.ANNUAL_KM, speeds=[best, 100.0, 120.0])
    assert set(df["component"]) == set(COMPONENTS)
    assert len(df) == 3 * len(COMPONENTS)
    regret = df.drop_duplicates("speed").set_index("speed")["regret"]
    assert regret[best] == pytest.approx(0, abs=1e-6)
    assert (regret.drop(best) > 0).all()


def test_matches_report_for_default_scenario() -> None:
    s = sc.scenario()
    best = optimal_speed(s)
    df = curves.cost_curve(s, sc.ANNUAL_KM, speeds=[100.0])
    assert round(best) == 82
    assert df["regret"].iloc[0] == pytest.approx(449, abs=1)


def test_life_minutes_for_default_trip() -> None:
    # The demo's minutes-of-life lens: 120 vs 100 on a 50 km trip, deaths only.
    s = sc.scenario()
    assert curves.extra_death_risk(s, 120, 50) == pytest.approx(1 / 8.7e6, rel=0.01)
    assert curves.life_minutes_lost(s, 120, 50) == pytest.approx(1.7, abs=0.05)
    assert curves.life_minutes_lost(s, 120, 50, everyone=True) == pytest.approx(
        3.3, abs=0.05
    )
    assert curves.life_minutes_lost(s, 100, 50) == 0
    assert curves.life_minutes_lost(s, 90, 50) < 0


def test_tradeoff_is_zero_at_the_limit() -> None:
    s = sc.scenario()
    assert (curves.tradeoff(s, s.road.limit, sc.ANNUAL_KM)["change"] == 0).all()


def test_waterfall_ends_at_the_full_optimum_and_chains() -> None:
    s = curves.with_options(
        sc.scenario(deviation_penalty=10), crash_scale=1.0, co2=True
    )
    wf = curves.waterfall(s)
    assert wf["end"].iloc[-1] == pytest.approx(optimal_speed(s), abs=0.01)
    assert (wf["start"].iloc[1:].to_numpy() == wf["end"].iloc[:-1].to_numpy()).all()
    assert list(wf["step"])[-2:] == ["+ slower-than-traffic risk", "+ CO₂"]


def test_with_options_toggles() -> None:
    s = curves.with_options(
        sc.scenario(), crash_scale=0, maintenance=False, refuel=False, co2=True
    )
    assert s.crash.cost_per_km == 0
    assert s.maintenance is None
    assert s.vehicle.stop_minutes == 0
    assert s.co2_price == sc.CO2_SOCIAL_PRICE


def test_crash_multiplier_is_one_at_flow() -> None:
    s = sc.scenario()
    df = curves.crash_multiplier(s, speeds=[s.road.flow, s.road.flow * 1.1])
    assert df["multiplier"].iloc[0] == pytest.approx(1.0)
    assert df["fatal"].iloc[0] == pytest.approx(1.0)
    assert df["fatal"].iloc[1] == pytest.approx(1.1**4)
    assert df["fatal"].iloc[1] > df["multiplier"].iloc[1]


def test_charts_build_valid_specs() -> None:
    s = sc.scenario()
    curve = curves.cost_curve(s, sc.ANNUAL_KM)
    markers = {"cheapest": optimal_speed(s), "limit": 100.0}
    mc = curves.uncertainty({"F-150": s}, Ranges(), n=20)
    for chart in (
        charts.regret_chart(curve, markers),
        charts.components_chart(curve, markers),
        charts.tradeoff_chart(curves.tradeoff(s, 120, sc.ANNUAL_KM), 120, 100),
        charts.waterfall_chart(curves.waterfall(s), 100),
        charts.uncertainty_chart(mc, 100),
    ):
        chart.to_dict()  # raises on an invalid Vega-Lite spec


def test_minutes_saved_shrink_with_each_step() -> None:
    saved = curves.minutes_saved_steps(50)["saved"].to_numpy()
    assert saved[0] == pytest.approx(60 * 50 / 60 - 60 * 50 / 70)
    assert (saved[1:] < saved[:-1]).all()


def test_race_puts_faster_car_at_the_finish() -> None:
    df = curves.race(50, you=120, other=100).set_index("speed")["km"]
    assert df[120] == pytest.approx(50)
    assert df[100] == pytest.approx(50 * 100 / 120)


def test_time_value_steps() -> None:
    df = curves.time_value_steps(32, 0.34, 0.625).set_index("step")["value"]
    assert df["After tax"] == pytest.approx(21.12)
    assert df["This page uses"] == pytest.approx(20)


def test_wear_and_stops_rise_with_speed() -> None:
    s = sc.scenario()
    df = curves.wear_and_stops(s, sc.ANNUAL_KM, speeds=[100.0, 120.0])
    by = df.pivot(index="metric", columns="speed", values="value")
    assert (by[120.0] > by[100.0]).all()
    assert by.loc["Refuelling stops per year", 100.0] == pytest.approx(
        sc.ANNUAL_KM * 0.106 / 70
    )


def test_every_source_has_the_table_fields() -> None:
    for s in sc.SOURCES:
        assert set(s) == {"input", "value", "basis", "url"}


def test_story_charts_build_valid_specs() -> None:
    s = sc.scenario()
    markers = {"limit": 100.0, "you": 120.0}
    for chart in (
        charts.race_chart(curves.race(50, 120, 100), 50),
        charts.trip_chart(curves.trip_minutes(50), markers),
        charts.saved_steps_chart(curves.minutes_saved_steps(50)),
        charts.fuel_chart(curves.fuel_curves(sc.VEHICLES), "F-150", markers),
        charts.time_value_chart(curves.time_value_steps(32, 0.34, 0.625)),
        charts.crash_chart(curves.crash_multiplier(s), markers),
        *charts.wear_charts(curves.wear_and_stops(s, sc.ANNUAL_KM), markers),
    ):
        chart.to_dict()


def test_road_deaths_baseline_and_power_law() -> None:
    s = sc.scenario()
    df = curves.road_deaths(s, 100_000, 50, {"flow": s.road.flow, "limit": 100.0})
    vkm = 100_000 * 50 * 365
    assert df["deaths"].iloc[0] == pytest.approx(sc.FATALITY_RATE * vkm)
    assert df["deaths"].iloc[1] == pytest.approx(
        sc.FATALITY_RATE * vkm * (100 / s.road.flow) ** 4
    )
    charts.deaths_chart(df).to_dict()


def test_life_trade_parts_add_up_and_chart_builds() -> None:
    s = sc.scenario()
    df = curves.life_trade(s, 120, 50)
    assert df["end"].tolist() == pytest.approx([5.0, 1.7, 3.3])
    assert df.iloc[2]["start"] == df.iloc[1]["end"]
    assert "lost" in df.iloc[1]["bar"]
    assert "saved" in curves.life_trade(s, 90, 50).iloc[1]["bar"]
    charts.life_trade_chart(df).to_dict()
