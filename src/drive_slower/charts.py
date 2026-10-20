"""Altair chart builders for the demo. Each takes frames from `curves`."""

from collections.abc import Mapping

import altair as alt
import pandas as pd  # type: ignore[import-untyped]

from drive_slower.speed_model import COMPONENTS

LABELS = {
    "time": "Your time",
    "energy": "Fuel / electricity",
    "refuel": "Refuelling stops",
    "maintenance": "Wear & maintenance",
    "crash": "Crash risk",
    "co2": "CO₂",
}
# Categorical slots 1-6 of the dataviz reference palette, in fixed order (CVD-checked).
COLORS = {
    "time": "#2a78d6",
    "energy": "#eb6834",
    "refuel": "#1baf7a",
    "maintenance": "#eda100",
    "crash": "#e87ba4",
    "co2": "#008300",
}
# Mid-tone neutrals that stay legible on both light and dark backgrounds.
MUTED = "#8a8984"
FAINT = "#b9b8b2"
WIDTH = "container"  # fill the notebook column
SPEED_DOMAIN = [60, 150]

_component_scale = alt.Scale(
    domain=[LABELS[c] for c in COMPONENTS], range=[COLORS[c] for c in COMPONENTS]
)
_speed_scale = alt.Scale(domain=SPEED_DOMAIN, nice=False, clamp=True)
_speed_axis = alt.X("speed:Q", title="Cruising speed (km/h)", scale=_speed_scale)


def _labelled(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(label=df["component"].map(LABELS))


def speed_markers(markers: Mapping[str, float]) -> alt.LayerChart:
    """Dashed vertical rules with stacked labels, e.g. {"limit": 100, "best": 82}."""
    df = pd.DataFrame({"name": list(markers), "speed": list(markers.values())})
    df["text"] = df["name"] + " " + df["speed"].round().astype(int).astype(str)
    df["ypx"] = [8 + 14 * i for i in range(len(df))]
    x = alt.X("speed:Q", scale=_speed_scale)
    rules = alt.Chart(df).mark_rule(strokeDash=[4, 3], color=MUTED).encode(x=x)
    text = (
        alt.Chart(df)
        .mark_text(align="left", dx=4, fontSize=11, color=MUTED)
        .encode(x=x, y=alt.Y("ypx:Q", scale=None), text="text:N")
    )
    return rules + text


def regret_chart(curve: pd.DataFrame, markers: Mapping[str, float]) -> alt.LayerChart:
    """Extra cost per year vs the best speed: the U-shaped headline chart."""
    totals = curve.drop_duplicates("speed")[["speed", "regret"]]
    hover = alt.selection_point(
        fields=["speed"], nearest=True, on="pointerover", empty=False
    )
    base = alt.Chart(totals).encode(x=_speed_axis)
    line = base.mark_line(strokeWidth=2.5, color=COLORS["time"]).encode(
        y=alt.Y("regret:Q", title="Extra cost per year vs. best speed ($)")
    )
    close = totals[totals["regret"] <= 100]["speed"]
    near_best = (
        alt.Chart(pd.DataFrame({"lo": [close.min()], "hi": [close.max()]}))
        .mark_rect(opacity=0.15, color=COLORS["refuel"])
        .encode(
            x=alt.X("lo:Q", scale=_speed_scale),
            x2="hi:Q",
            tooltip=[
                alt.Tooltip("lo:Q", title="within $100/yr from", format=".0f"),
                alt.Tooltip("hi:Q", title="to", format=".0f"),
            ],
        )
    )
    points = (
        base.mark_point(size=80, filled=True, color=COLORS["time"])
        .encode(
            y="regret:Q",
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("speed:Q", title="km/h", format=".0f"),
                alt.Tooltip("regret:Q", title="extra $/yr", format=",.0f"),
            ],
        )
        .add_params(hover)
    )
    return (near_best + line + points + speed_markers(markers)).properties(
        width=WIDTH, height=280
    )


def components_chart(
    curve: pd.DataFrame, markers: Mapping[str, float]
) -> alt.LayerChart:
    """Total yearly cost stacked by component."""
    df = _labelled(curve[curve["annual"] > 0])
    area = (
        alt.Chart(df)
        .mark_area(opacity=0.95)
        .encode(
            x=_speed_axis,
            y=alt.Y("annual:Q", stack=True, title="Yearly cost ($)"),
            color=alt.Color(
                "label:N",
                scale=_component_scale,
                title=None,
                legend=alt.Legend(orient="bottom", columns=3, symbolType="square"),
            ),
            order=alt.Order("component_order:Q"),
            tooltip=[
                alt.Tooltip("label:N", title="cost"),
                alt.Tooltip("speed:Q", title="km/h", format=".0f"),
                alt.Tooltip("annual:Q", title="$/yr", format=",.0f"),
            ],
        )
        .transform_calculate(component_order=_order_expr())
    )
    return (area + speed_markers(markers)).properties(width=WIDTH, height=240)


def _order_expr() -> str:
    return (
        " : ".join(f"datum.component == '{c}' ? {i}" for i, c in enumerate(COMPONENTS))
        + f" : {len(COMPONENTS)}"
    )


def tradeoff_chart(df: pd.DataFrame, speed: float, limit: float) -> alt.LayerChart:
    """Change in yearly cost by component at `speed` vs driving the limit."""
    df = _labelled(df[df["change"].abs() >= 0.5])
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4, height=22)
        .encode(
            y=alt.Y("label:N", sort=[LABELS[c] for c in COMPONENTS], title=None),
            x=alt.X(
                "change:Q",
                title=f"Change in yearly cost at {speed:.0f} vs {limit:.0f} km/h "
                "($, negative = saving)",
            ),
            color=alt.Color("label:N", scale=_component_scale, legend=None),
            tooltip=[
                alt.Tooltip("label:N", title="cost"),
                alt.Tooltip("change:Q", title="$/yr", format="+,.0f"),
            ],
        )
    )

    def value_labels(positive: bool) -> alt.Chart:
        return (
            bars.transform_filter(f"datum.change {'>=' if positive else '<'} 0")
            .mark_text(align="left" if positive else "right", dx=4 if positive else -4)
            .encode(text=alt.Text("change:Q", format="+,.0f"), color=alt.value(MUTED))
        )

    text = value_labels(True) + value_labels(False)
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=MUTED).encode(x="x:Q")
    return (bars + text + zero).properties(width=WIDTH, height=36 * max(len(df), 1))


def waterfall_chart(df: pd.DataFrame, limit: float) -> alt.LayerChart:
    """Best speed as each cost is added: a dot per step, a bar for each move."""
    df = df.assign(
        lo=df[["start", "end"]].min(axis=1),
        hi=df[["start", "end"]].max(axis=1),
        change=(df["end"] - df["start"]).round(),
    )
    x = alt.X(
        "step:N",
        sort=list(df["step"]),
        title=None,
        axis=alt.Axis(labelAngle=0, labelLimit=150),
    )
    y_scale = alt.Scale(
        domain=[min(df["end"].min(), limit) - 5, max(df["end"].max(), limit) + 5]
    )
    moves = (
        alt.Chart(df[df["order"] > 0])
        .mark_bar(size=40, color=COLORS["time"], opacity=0.25)
        .encode(x=x, y=alt.Y("lo:Q", scale=y_scale), y2="hi:Q")
    )
    dots = (
        alt.Chart(df)
        .mark_point(size=120, filled=True, color=COLORS["time"])
        .encode(
            x=x,
            y=alt.Y("end:Q", title="Cheapest speed (km/h)", scale=y_scale),
            tooltip=[
                alt.Tooltip("step:N"),
                alt.Tooltip("end:Q", title="cheapest km/h", format=".0f"),
                alt.Tooltip("change:Q", title="change", format="+.0f"),
            ],
        )
    )
    labels = (
        alt.Chart(df)
        .mark_text(dx=14, align="left", color=MUTED, fontWeight="bold")
        .encode(x=x, y="end:Q", text=alt.Text("end:Q", format=".0f"))
    )
    limit_df = pd.DataFrame({"y": [limit], "t": [f"limit {limit:.0f}"]})
    rule = alt.Chart(limit_df).mark_rule(strokeDash=[4, 3], color=MUTED).encode(y="y:Q")
    rule_text = (
        alt.Chart(limit_df)
        .mark_text(align="right", dy=-6, color=MUTED, fontSize=11)
        .encode(y="y:Q", x=alt.XValue("width"), text="t:N")
    )
    return (moves + rule + rule_text + dots + labels).properties(
        width=WIDTH, height=260
    )


def uncertainty_chart(df: pd.DataFrame, limit: float) -> alt.LayerChart:
    """Monte Carlo best speeds per case, jittered dots plus median tick."""
    y = alt.Y("case:N", title=None, sort=list(dict.fromkeys(df["case"])))
    dots = (
        alt.Chart(df)
        .mark_circle(size=14, opacity=0.25, color=COLORS["time"])
        .encode(
            x=alt.X(
                "speed:Q",
                title="Best speed across 1,000 simulations (km/h)",
                scale=alt.Scale(zero=False),
            ),
            y=y,
            yOffset=alt.YOffset("jitter:Q", scale=alt.Scale(domain=[-1, 1])),
        )
        .transform_calculate(jitter="sqrt(-2*log(random()))*cos(2*PI*random()) / 3")
    )
    medians = (
        alt.Chart(df)
        .mark_tick(thickness=3, size=34, color=COLORS["energy"])
        .encode(
            x="median(speed):Q",
            y=y,
            tooltip=[
                alt.Tooltip("case:N"),
                alt.Tooltip("median(speed):Q", title="median km/h", format=".0f"),
                alt.Tooltip("q1(speed):Q", title="25th pct", format=".0f"),
                alt.Tooltip("q3(speed):Q", title="75th pct", format=".0f"),
            ],
        )
    )
    rule = (
        alt.Chart(pd.DataFrame({"speed": [limit]}))
        .mark_rule(strokeDash=[4, 3], color=MUTED)
        .encode(x="speed:Q")
    )
    return (dots + medians + rule).properties(
        width=WIDTH, height=60 * df["case"].nunique()
    )


# --- Story sections ------------------------------------------------------------------


def race_chart(df: pd.DataFrame, km: float) -> alt.LayerChart:
    """Two cars on the road at the moment the first one arrives."""
    y = alt.Y("car:N", title=None, sort=list(df["car"]))
    x_scale = alt.Scale(domain=[0, km * 1.04], nice=False)
    car_color = alt.Color(
        "car:N",
        scale=alt.Scale(domain=list(df["car"]), range=[COLORS["time"], MUTED]),
        legend=None,
    )
    track = (
        alt.Chart(df.assign(start=0.0, end=km))
        .mark_rule(strokeWidth=10, color=FAINT, opacity=0.35, strokeCap="round")
        .encode(
            x=alt.X("start:Q", scale=x_scale, title="km travelled"), x2="end:Q", y=y
        )
    )
    driven = (
        alt.Chart(df.assign(start=0.0))
        .mark_rule(strokeWidth=10, strokeCap="round")
        .encode(
            x=alt.X("start:Q", scale=x_scale),
            x2="km:Q",
            y=y,
            color=car_color,
        )
    )
    cars = (
        alt.Chart(df)
        .mark_point(shape="triangle-right", size=420, filled=True, opacity=1)
        .encode(x=alt.X("km:Q", scale=x_scale), y=y, color=car_color)
    )
    finish = (
        alt.Chart(pd.DataFrame({"km": [km], "t": ["work"]}))
        .mark_rule(strokeDash=[2, 2], color=MUTED)
        .encode(x=alt.X("km:Q", scale=x_scale))
    )
    return (track + driven + finish + cars).properties(width=WIDTH, height=130)


def _line_with_markers(
    df: pd.DataFrame,
    y: alt.Y,
    markers: Mapping[str, float],
    tooltip_fmt: str,
    height: int = 220,
) -> alt.LayerChart:
    line = (
        alt.Chart(df)
        .mark_line(strokeWidth=2.5, color=COLORS["time"])
        .encode(
            x=_speed_axis,
            y=y,
            tooltip=[
                alt.Tooltip("speed:Q", title="km/h", format=".0f"),
                alt.Tooltip(f"{y.shorthand}", format=tooltip_fmt),
            ],
        )
    )
    return (line + speed_markers(markers)).properties(width=WIDTH, height=height)


def trip_chart(df: pd.DataFrame, markers: Mapping[str, float]) -> alt.LayerChart:
    return _line_with_markers(
        df, alt.Y("minutes:Q", title="Minutes per one-way trip"), markers, ".1f"
    )


def saved_steps_chart(df: pd.DataFrame) -> alt.Chart:
    """Minutes saved by each extra 10 km/h: a shrinking staircase."""
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=COLORS["time"])
        .encode(
            x=alt.X(
                "band:N",
                sort=list(df["band"]),
                title="Speeding up from → to (km/h)",
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("saved:Q", title="Minutes saved per trip"),
            tooltip=[
                alt.Tooltip("band:N"),
                alt.Tooltip("saved:Q", title="min", format=".1f"),
            ],
        )
        .properties(width=WIDTH, height=200)
    )


def fuel_chart(
    df: pd.DataFrame, selected: str, markers: Mapping[str, float]
) -> alt.LayerChart:
    """Extra energy vs 100 km/h for each vehicle, highlighting the selected one."""
    df = df.assign(extra=(df["vs_100"] - 1) * 100, chosen=df["vehicle"] == selected)
    base = alt.Chart(df).encode(
        x=_speed_axis,
        y=alt.Y("extra:Q", title="Energy used vs. 100 km/h (%)"),
        detail="vehicle:N",
    )
    lines = base.mark_line().encode(
        color=alt.condition(
            "datum.chosen", alt.value(COLORS["time"]), alt.value(FAINT)
        ),
        strokeWidth=alt.condition("datum.chosen", alt.value(3), alt.value(1.5)),
        tooltip=[
            alt.Tooltip("vehicle:N"),
            alt.Tooltip("speed:Q", title="km/h", format=".0f"),
            alt.Tooltip("per_100km:Q", title="per 100 km", format=".1f"),
            alt.Tooltip("unit:N"),
        ],
    )
    labels = (
        base.transform_filter(f"datum.speed == {df['speed'].max()}")
        .mark_text(align="left", dx=6, fontSize=11)
        .encode(text="vehicle:N", color=alt.value(MUTED))
    )
    return (lines + labels + speed_markers(markers)).properties(width=WIDTH, height=240)


def time_value_chart(df: pd.DataFrame) -> alt.LayerChart:
    """Wage → after tax → research value → the value this page uses."""
    last = df["step"].iloc[-1]
    y = alt.Y(
        "step:N", sort=list(df["step"]), title=None, axis=alt.Axis(labelLimit=220)
    )
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4, height=22)
        .encode(
            y=y,
            x=alt.X("value:Q", title="$ per hour"),
            color=alt.condition(
                f"datum.step == '{last}'",
                alt.value(COLORS["time"]),
                alt.value(FAINT),
            ),
        )
    )
    text = bars.mark_text(align="left", dx=4, color=MUTED).encode(
        text=alt.Text("value:Q", format="$.0f"), color=alt.value(MUTED)
    )
    return (bars + text).properties(width=WIDTH, height=36 * len(df))


def crash_chart(df: pd.DataFrame, markers: Mapping[str, float]) -> alt.LayerChart:
    """Risk of a fatal crash, and of any crash harm, vs keeping pace with traffic."""
    long = df.melt(
        id_vars="speed",
        value_vars=["fatal", "multiplier"],
        var_name="kind",
        value_name="x",
    )
    long["series"] = long["kind"].map(
        {"fatal": "Deaths", "multiplier": "All crash harm"}
    )
    deaths = "datum.series == 'Deaths'"
    base = alt.Chart(long).encode(
        x=_speed_axis,
        y=alt.Y("x:Q", title="Risk vs. keeping pace with traffic (×)"),
        detail="series:N",
    )
    lines = base.mark_line().encode(
        color=alt.condition(deaths, alt.value(COLORS["crash"]), alt.value(FAINT)),
        strokeWidth=alt.condition(deaths, alt.value(3), alt.value(1.5)),
        tooltip=[
            alt.Tooltip("series:N"),
            alt.Tooltip("speed:Q", title="km/h", format=".0f"),
            alt.Tooltip("x:Q", title="×", format=".2f"),
        ],
    )
    labels = (
        base.transform_filter(f"datum.speed == {long['speed'].max()}")
        .mark_text(align="left", dx=6, fontSize=11)
        .encode(text="series:N", color=alt.value(MUTED))
    )
    one = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(color=MUTED).encode(y="y:Q")
    return (one + lines + labels + speed_markers(markers)).properties(
        width=WIDTH, height=240
    )


def deaths_chart(df: pd.DataFrame) -> alt.LayerChart:
    """Expected deaths per year on the stretch at each average speed."""
    y = alt.Y(
        "label:N", sort=list(df["label"]), title=None, axis=alt.Axis(labelLimit=260)
    )
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4, height=22, color=COLORS["crash"])
        .encode(
            y=y,
            x=alt.X("deaths:Q", title="Expected deaths per year (estimate)"),
            tooltip=[
                alt.Tooltip("label:N", title="if everyone drove"),
                alt.Tooltip("deaths:Q", title="deaths/yr", format=".1f"),
            ],
        )
    )
    text = bars.mark_text(align="left", dx=4, color=MUTED).encode(
        text=alt.Text("deaths:Q", format=".1f"), color=alt.value(MUTED)
    )
    return (bars + text).properties(width=WIDTH, height=36 * len(df))


def wear_charts(df: pd.DataFrame, markers: Mapping[str, float]) -> list[alt.LayerChart]:
    """Small multiples, one per metric: maintenance $/yr and refuelling stops/yr."""
    return [
        _line_with_markers(
            df[df["metric"] == metric],
            alt.Y("value:Q", title=metric, scale=alt.Scale(zero=False)),
            markers,
            ",.0f",
            height=180,
        )
        for metric in df["metric"].unique()
    ]
