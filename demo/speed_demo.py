import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="How fast should you drive?")


@app.cell
async def _():
    import sys

    import marimo as mo

    if "pyodide" in sys.modules:
        # Static (WebAssembly) build: install this project's wheel from public/.
        # Dependencies come from Pyodide's own builds rather than the wheel's pins.
        # Imported indirectly: a plain `import micropip` makes marimo's local
        # missing-package check look for it, which can crash the kernel on startup.
        import importlib

        micropip = importlib.import_module("micropip")
        await micropip.install(["numpy", "scipy", "pandas", "altair"])
        await micropip.install(
            str(
                mo.notebook_location()
                / "public"
                / "drive_slower-0.1.0-py3-none-any.whl"
            ),
            deps=False,
        )

    from drive_slower import charts, curves
    from drive_slower import scenarios as sc
    from drive_slower.speed_model import Ranges, cost_breakdown, optimal_speed

    return Ranges, charts, cost_breakdown, curves, mo, optimal_speed, sc


@app.cell
def _(mo, sc):
    vehicle = mo.ui.dropdown(
        {v.name: v for v in sc.VEHICLES}, value="F-150", label="Vehicle"
    )
    road = mo.ui.dropdown(
        list(sc.ROADS), value="BC Hwy 1 (Lower Mainland)", label="Road"
    )
    one_way = mo.ui.slider(
        5, 150, step=5, value=50, label="One-way commute (km)", show_value=True
    )
    days = mo.ui.slider(
        20, 365, step=5, value=240, label="Commuting days / year", show_value=True
    )
    free_flow = mo.ui.slider(
        0,
        100,
        step=5,
        value=100,
        label="Share in free-flowing traffic (%)",
        show_value=True,
    )
    wage = mo.ui.slider(
        15, 100, step=1, value=32, label="Gross wage ($/hr)", show_value=True
    )
    time_share = mo.ui.slider(
        25,
        100,
        step=2.5,
        value=62.5,
        label="Commute time worth (% of wage)",
        show_value=True,
    )
    crash_view = mo.ui.radio(
        {"Just mine": "private", "Everyone's": "social"},
        value="Everyone's",
        inline=True,
        label="Crash harm to count",
    )
    crash_scale = mo.ui.slider(
        0, 3, step=0.25, value=1, label="Crash cost (× estimate)", show_value=True
    )
    deviation = mo.ui.slider(
        0,
        40,
        step=1,
        value=0,
        label="Extra risk below traffic speed (k)",
        show_value=True,
    )
    maintenance = mo.ui.switch(value=True, label="Wear & maintenance")
    refuel = mo.ui.switch(value=True, label="Refuelling stops")
    co2 = mo.ui.switch(value=False, label="CO₂ (social cost of carbon)")
    return (
        co2,
        crash_scale,
        crash_view,
        days,
        deviation,
        free_flow,
        maintenance,
        one_way,
        refuel,
        road,
        time_share,
        vehicle,
        wage,
    )


@app.cell
def _(mo, road, sc, vehicle):
    # Recreated when vehicle or road changes, so the default matches the region and unit.
    _region, _ = sc.ROADS[road.value]
    _unit = vehicle.value.energy_unit
    _ev = _unit == "kWh"
    price = mo.ui.slider(
        0.05 if _ev else 1.00,
        0.60 if _ev else 2.50,
        step=0.01 if _ev else 0.05,
        value=sc.PRICES[(_region, _unit)],
        label=f"Energy price ($/{_unit})",
        show_value=True,
    )
    return (price,)


@app.cell
def _(
    co2,
    crash_scale,
    crash_view,
    days,
    deviation,
    free_flow,
    maintenance,
    mo,
    one_way,
    price,
    refuel,
    road,
    time_share,
    vehicle,
    wage,
):
    mo.sidebar(
        [
            mo.md("### Your commute"),
            vehicle,
            road,
            one_way,
            days,
            free_flow,
            mo.md("### Your time"),
            wage,
            time_share,
            mo.md(
                f"→ worth **\\${wage.value * time_share.value / 100:.0f}/hr** on the road"
            ),
            mo.md("### Costs"),
            price,
            crash_view,
            crash_scale,
            deviation,
            maintenance,
            refuel,
            co2,
        ],
        width="340px",
    )
    return


@app.cell
def _(
    co2,
    crash_scale,
    crash_view,
    curves,
    days,
    deviation,
    free_flow,
    maintenance,
    one_way,
    optimal_speed,
    price,
    refuel,
    road,
    sc,
    time_share,
    vehicle,
    wage,
):
    value_of_time = wage.value * time_share.value / 100
    annual_km = one_way.value * 2 * days.value * free_flow.value / 100
    toggles = {
        "crash_scale": crash_scale.value,
        "maintenance": maintenance.value,
        "refuel": refuel.value,
        "co2": co2.value,
    }

    def build(veh, energy_price=None):
        base = sc.scenario(
            veh, road.value, crash_view.value, value_of_time, deviation.value
        )
        return curves.with_options(base, energy_price=energy_price, **toggles)

    scn = build(vehicle.value, price.value)
    best = optimal_speed(scn)
    return annual_km, best, build, scn, value_of_time


@app.cell
def _(mo):
    mo.md("""
    # How fast should you drive to work?

    Driving faster saves time, but burns more fuel, wears out your vehicle faster and
    raises the chance of a crash. This page adds those up and finds the speed where
    your commute costs least. Change anything in the sidebar (☰) to make it about
    *your* commute; every chart updates.
    """)
    return


@app.cell
def _(mo):
    your_speed = mo.ui.slider(
        60, 150, step=1, value=120, label="Your speed (km/h)", show_value=True
    )
    return (your_speed,)


@app.cell
def _(annual_km, charts, curves, mo, one_way, scn, your_speed):
    _v, _lim = your_speed.value, scn.road.limit
    _min_each_way = abs(60 * one_way.value * (1 / _lim - 1 / _v))
    _hours = abs(curves.hours_saved(scn, _v, annual_km))
    _t = curves.tradeoff(scn, _v, annual_km).set_index("component")["change"]
    _other, _time_value = _t.drop("time").sum(), abs(_t["time"])
    if _v > _lim:
        _story = (
            f"Driving **{_v:.0f}** instead of **{_lim:.0f}** gets you to work "
            f"**{_min_each_way:.1f} minutes sooner** each way, about **{_hours:.0f} hours "
            f"a year**. It also adds about **\\${_other:,.0f} a year** in fuel, refuelling, wear "
            f"and crash risk. Is {_hours:.0f} hours worth \\${_other:,.0f}? The rest of this "
            "page works that out."
        )
    elif _v < _lim:
        _story = (
            f"Driving **{_v:.0f}** instead of **{_lim:.0f}** costs you "
            f"**{_min_each_way:.1f} minutes** each way, about **{_hours:.0f} hours a "
            f"year**. It saves about **\\${-_other:,.0f} a year** in fuel, refuelling, wear "
            "and crash risk. The rest of this page works out whether that's a good trade."
        )
    else:
        _story = "Move the slider to see what driving faster or slower changes."
    mo.vstack(
        [
            mo.md("## Pick a speed"),
            your_speed,
            charts.race_chart(curves.race(one_way.value, _v, _lim), one_way.value),
            mo.md(
                f"*Where each car is when the first one reaches work, "
                f"{one_way.value:.0f} km away.*\n\n{_story}"
            ),
        ]
    )
    return


@app.cell
def _(charts, curves, mo, one_way, scn, your_speed):
    _steps = curves.minutes_saved_steps(one_way.value)
    _first, _last = _steps.iloc[0], _steps.iloc[-1]
    _markers = {"limit": scn.road.limit, "you": your_speed.value}
    mo.vstack(
        [
            mo.md(
                "---\n## 1. Time: each km/h buys less\n"
                "Trip time is distance ÷ speed, so every extra km/h saves a little less "
                "than the one before."
            ),
            one_way,
            charts.trip_chart(curves.trip_minutes(one_way.value), _markers),
            charts.saved_steps_chart(_steps),
            mo.md(
                f"On a {one_way.value:.0f} km trip, going from {_first['band']} km/h saves "
                f"**{_first['saved']:.1f} minutes**; going from {_last['band']} saves "
                f"only **{_last['saved']:.1f}**."
            ),
        ]
    )
    return


@app.cell
def _(annual_km, charts, curves, mo, price, sc, scn, vehicle, your_speed):
    _veh = scn.vehicle
    _a, _b = _veh.use_per_km(100) * 100, _veh.use_per_km(120) * 100
    _energy = (
        curves.tradeoff(scn, your_speed.value, annual_km)
        .set_index("component")
        .loc["energy", "change"]
    )
    _more = "more" if _energy >= 0 else "less"
    mo.vstack(
        [
            mo.md(
                "---\n## 2. Fuel: pushing air gets expensive\n"
                "At highway speeds most of the engine's work goes into pushing air out of "
                "the way, and air resistance grows with the *square* of speed. Tall, boxy "
                "vehicles like pickups suffer most."
            ),
            vehicle,
            charts.fuel_chart(
                curves.fuel_curves(sc.VEHICLES),
                _veh.name,
                {"limit": scn.road.limit, "you": your_speed.value},
            ),
            mo.md(
                f"Your **{_veh.name}** uses about **{_a:.1f} {_veh.energy_unit}/100 km at "
                f"100 km/h** and **{_b:.1f} at 120** (+{(_b / _a - 1) * 100:.0f}%). At "
                f"\\${price.value:.2f}/{_veh.energy_unit}, driving {your_speed.value:.0f} "
                f"instead of {scn.road.limit:.0f} costs **\\${abs(_energy):,.0f} a year "
                f"{_more}**."
            ),
        ]
    )
    return


@app.cell
def _(charts, curves, mo, road, sc, time_share, value_of_time, wage):
    _region, _ = sc.ROADS[road.value]
    _df = curves.time_value_steps(
        wage.value, sc.MARGINAL_TAX[_region], time_share.value / 100
    )
    mo.vstack(
        [
            mo.md(
                "---\n## 3. What's your time worth?\n"
                "To compare minutes with dollars we need a price for your time. It's "
                "less than your wage: you can't usually turn 5 saved minutes into 5 "
                "minutes of paid work, and the fuel you'd save is paid from after-tax "
                "money. Studies of what people pay to save time (tolls, faster routes) "
                "put commute time at about **half of income**. Using household income "
                "instead of one person's pay puts it nearer 70%."
            ),
            wage,
            time_share,
            charts.time_value_chart(_df),
            mo.md(
                f"The median Canadian wage is about **\\${sc.MEDIAN_WAGE:.0f}/hr**. With "
                f"your settings, an hour on the road is worth **\\${value_of_time:.0f}**."
            ),
        ]
    )
    return


@app.cell
def _(
    annual_km,
    charts,
    cost_breakdown,
    crash_view,
    curves,
    mo,
    sc,
    scn,
    your_speed,
):
    _mult = curves.crash_multiplier(scn).set_index("speed")
    _you, _lim = round(your_speed.value), round(scn.road.limit)
    _change = _mult.loc[_you, "fatal"] / _mult.loc[_lim, "fatal"] - 1
    _yearly = cost_breakdown(scn, scn.road.limit)["crash"] * annual_km
    _whose = "your own share of the" if crash_view.value == "private" else "all the"
    if _you == _lim:
        _effect = "Move the speed slider to see how the risk changes."
    else:
        _how = (
            f"about **{1 + _change:.1f} times as likely**"
            if _change >= 0.5
            else f"about **{abs(_change):.0%} {'more' if _change > 0 else 'less'} likely**"
        )
        _effect = (
            f"Driving **{_you}** instead of **{_lim}** makes a crash that kills "
            f"someone {_how}."
        )
    mo.vstack(
        [
            mo.md(
                "---\n## 4. Crash risk: the cost that matters most\n"
                f"In {sc.ROAD_DEATHS_YEAR}, **{sc.ROAD_DEATHS:,} people died on Canada's "
                "roads**, and many thousands more were seriously hurt. Each was "
                "someone's parent, child, partner or friend.\n\n"
                "Speed is one of the clearest levers we have. Faster crashes happen "
                "more often *and* hurt more: decades of studies of speed-limit changes "
                "find deaths rise roughly with the **fourth power** of speed. Going 10% "
                "faster means about 46% more deaths."
            ),
            charts.crash_chart(
                _mult.reset_index(),
                {"traffic": scn.road.flow, "limit": scn.road.limit, "you": _you},
            ),
            mo.md(
                f"*Compared with keeping pace with traffic at {scn.road.flow:.0f} km/h.*"
                f"\n\n{_effect}"
            ),
            mo.callout(
                mo.md(
                    "**Why put a dollar figure on this?** It can feel wrong, and no amount "
                    "of money makes up for a life. We do it for one reason: it puts risk "
                    "on the same scale as minutes and fuel, so you can see what a few "
                    "minutes saved really trade against. Governments do the same when "
                    "deciding which road-safety measures to fund. The figure (about \\$9 "
                    "million per life) isn't a price on anyone. It reflects what people "
                    "are willing to pay, together, to make small risks smaller."
                ),
                kind="neutral",
            ),
            crash_view,
            mo.md(
                f"Counting {_whose} harm, that comes to about **\\${_yearly:,.0f} a year** "
                "at the limit: a small chance of something terrible, averaged over "
                "years of driving."
            ),
        ]
    )
    return


@app.cell
def _(charts, curves, mo, one_way, sc, scn, your_speed):
    _v, _lim, _km = your_speed.value, scn.road.limit, one_way.value
    _saved = 60 * _km * (1 / _lim - 1 / _v)
    # Round first so the two parts add up to the total as shown.
    _mine = round(curves.life_minutes_lost(scn, _v, _km), 1)
    _total = round(curves.life_minutes_lost(scn, _v, _km, everyone=True), 1)
    _others = _total - _mine
    if _v > _lim:
        _body = (
            f"Driving **{_v:.0f}** instead of **{_lim:.0f}** gets you to work "
            f"**{_saved:.1f} minutes** sooner on this {_km:.0f} km trip. But those "
            "minutes aren't added to your life: you'd have lived them anyway, in "
            "traffic, with music, a podcast or the news. Getting there sooner just "
            "upgrades them.\n\n"
            "Driving faster also makes a deadly crash more likely. Averaged over all "
            f"your trips, that costs about **{_mine:.1f} minutes of your own life** each "
            "trip. On almost every trip nothing happens; very rarely, something "
            f"terrible does. It also costs about **{_others:.1f} minutes** of other "
            f"people's lives, for a total of **{_total:.1f} minutes of life lost to save "
            f"{_saved:.1f} minutes off a commute**.\n\n"
            f"So you're trading {_saved:.1f} minutes of upgraded life for "
            f"{_total:.1f} whole minutes of life, and that counts only deaths. Add "
            "injuries, extra fuel, wear and the chance of a ticket, and driving faster "
            "starts to look like a clear loser."
        )
    elif _v < _lim:
        _body = (
            f"Driving **{_v:.0f}** instead of **{_lim:.0f}** adds **{-_saved:.1f} "
            f"minutes** to this {_km:.0f} km trip: minutes you'd still live, with music, "
            "a podcast or the news. In return, the lower chance of a deadly crash saves "
            f"about **{-_mine:.1f} minutes of your own life** each trip, averaged over "
            f"all your trips, and about **{-_others:.1f} minutes** of other people's "
            f"lives: **{-_total:.1f} whole minutes of life** for {-_saved:.1f} minutes of "
            "slower commute. That counts only deaths, not injuries or other harm."
        )
    else:
        _body = "Move the speed slider to compare minutes saved with minutes of life."
    _chart = (
        [charts.life_trade_chart(curves.life_trade(scn, _v, _km))] if _v != _lim else []
    )
    _section = mo.vstack(
        [
            mo.md(f"### Another way to see it: minutes of life\n{_body}"),
            *_chart,
        ]
    )

    _details = []
    if _v != _lim:
        _url = {s["input"]: s["url"] for s in sc.SOURCES}
        _rate_url = _url["Highway deaths per km driven"]
        _drivers_url = _url["Drivers' share of road deaths"]
        _power_url = _url["Crash risk rises ~speed⁴ (power model)"]
        _life_url = _url["Remaining life at 40"]
        _risk = curves.crash_multiplier(scn, [_lim, _v]).set_index("speed")["fatal"]
        _dp_mine = curves.extra_death_risk(scn, _v, _km)
        _dp_all = curves.extra_death_risk(scn, _v, _km, everyone=True)
        _per_km = 1 / (sc.FATALITY_RATE * sc.DRIVER_SHARE)
        _minutes_left = sc.REMAINING_WAKING_HOURS * 60
        _change = "higher" if _dp_mine > 0 else "lower"

        def _odds(p):
            n = 1 / abs(p) / 1e6
            return f"1 in {n:.1f} million" if n < 10 else f"1 in {n:,.0f} million"

        _calc = mo.md(
            f"**1. Time.** {_km:.0f} km takes {60 * _km / _lim:.1f} minutes at "
            f"{_lim:.0f} km/h and {60 * _km / _v:.1f} at {_v:.0f}: a difference of "
            f"{abs(_saved):.1f} minutes.\n\n"
            "**2. Your chance of dying per km.** Canada has about 0.5 road deaths per "
            f"100 million vehicle-km ([Transport Canada]({_rate_url})), and drivers are "
            f"52% of them ([Transport Canada]({_drivers_url})). So a driver's chance of "
            f"dying is about 1 in {_per_km / 1e6:.0f} million per km, at the usual speed "
            f"of traffic ({scn.road.flow:.0f} km/h here).\n\n"
            "**3. How that changes with speed.** Deaths rise roughly with the fourth "
            f"power of speed ([Nilsson's power model, Elvik et al. 2019]({_power_url})). "
            f"Compared with traffic speed, the risk is {_risk[_lim]:.2f}× at "
            f"{_lim:.0f} km/h and {_risk[_v]:.2f}× at {_v:.0f}. Over {_km:.0f} km, your "
            f"chance of dying is {_change} by {_km:.0f} × 1/{_per_km / 1e6:.0f} million "
            f"× ({_risk[_v]:.2f} − {_risk[_lim]:.2f}) ≈ **{_odds(_dp_mine)}**. Counting "
            f"everyone who could be killed, it's {_change} by about **{_odds(_dp_all)}**."
            "\n\n"
            "**4. Into minutes of life.** A 40-year-old has about 43 years left "
            f"([Statistics Canada]({_life_url})): about {_minutes_left / 1e6:.1f} million "
            "waking minutes (43 years × 365 days × 16 hours × 60). Yours: "
            f"{_minutes_left / 1e6:.1f} million × {_odds(_dp_mine)} ≈ "
            f"**{abs(_mine):.1f} minutes**. Everyone's: {_minutes_left / 1e6:.1f} million "
            f"× {_odds(_dp_all)} ≈ **{abs(_total):.1f}**. Other people's: "
            f"{abs(_total):.1f} − {abs(_mine):.1f} = **{abs(_others):.1f}**.\n\n"
            "*Not counted: injuries, which are far more common than deaths, and other "
            "harm. These are rough estimates. The death rate is Canada's all-roads "
            "average (freeways are probably safer), the power model comes from changes "
            "in whole roads' average speeds, and the other people killed may have more "
            "or fewer years left than a 40-year-old.*"
        )
        _details = [mo.accordion({"Show the calculation": _calc})]
    mo.vstack([_section, *_details])
    return


@app.cell
def _(annual_km, charts, curves, mo, scn, your_speed):
    _df = curves.wear_and_stops(
        scn, annual_km, speeds=sorted({scn.road.limit, your_speed.value})
    )
    _by = _df.pivot(index="metric", columns="speed", values="value")
    _d = (_by[your_speed.value] - _by[scn.road.limit]).to_dict()
    _wear = _d["Wear & maintenance ($/yr)"]
    _note = " (charged at home, so no stops)" if scn.vehicle.stop_minutes == 0 else ""
    mo.vstack(
        [
            mo.md(
                "---\n## 5. Wear and refuelling\n"
                "Two smaller costs: tires and parts wear faster at speed, and more fuel "
                "means more trips to the pump."
            ),
            mo.hstack(
                [
                    # Side by side when there's room, stacked on narrow screens.
                    mo.as_html(_c).style({"flex": "1 1 280px", "min-width": "0"})
                    for _c in charts.wear_charts(
                        curves.wear_and_stops(scn, annual_km),
                        {"limit": scn.road.limit, "you": your_speed.value},
                    )
                ],
                wrap=True,
                gap=1.5,
            ),
            mo.md(
                f"At {your_speed.value:.0f} instead of {scn.road.limit:.0f}: "
                f"**{'+' if _wear >= 0 else '−'}\\${abs(_wear):,.0f}/yr** in wear and "
                f"**{_d['Refuelling stops per year']:+.0f} stops a year**{_note}."
            ),
        ]
    )
    return


@app.cell
def _(
    annual_km,
    curves,
    mo,
    one_way,
    road,
    sc,
    scn,
    value_of_time,
    your_speed,
):
    _lim = scn.road.limit
    _region, _ = sc.ROADS[road.value]
    _tix = sc.tickets(road.value)
    # Below the limit, illustrate the delay with a speed that would risk a ticket.
    _v = your_speed.value if your_speed.value > _lim else _lim + 20
    _saved = 60 * one_way.value * (1 / _lim - 1 / _v)

    if your_speed.value <= _lim:
        _dollars = (
            "At or below the limit there's nothing to count. Move the speed slider "
            f"above {_lim:.0f} to see what tickets would add."
        )
    else:
        _per_year = _tix.per_year(_v, _lim, annual_km)
        _cost = _tix.annual_cost(_v, _lim, annual_km, value_of_time)
        _other = (
            curves.tradeoff(scn, _v, annual_km)
            .set_index("component")["change"]
            .drop("time")
            .sum()
        )
        _share = _cost / _other if _other > 0 else 0.0
        _size = (
            "a rounding error"
            if _share < 0.03
            else "small"
            if _share < 0.25
            else "a real cost"
        )
        _often = (
            f"about one ticket every **{1 / _per_year:.0f} years**"
            if _per_year * 50 >= 1
            else "a ticket less than once in 50 years"
        )
        _dollars = (
            f"At {_v:.0f} km/h you'd expect {_often} on this commute. Fines, insurance "
            f"and the time it takes come to about **\\${_cost:,.0f} a year**, next to "
            f"**\\${_other:,.0f}** in extra fuel, wear and crash risk: {_size}."
        )
        if _v - _lim > _tix.rules.severe_over:
            _dollars += (
                f" Past {_lim + _tix.rules.severe_over:.0f} it stops being an ordinary "
                "ticket: your vehicle is impounded at the roadside."
            )

    if _region == "ON":
        _insurance = (
            "In Ontario, most of a ticket's cost is insurance: one conviction typically raises "
            "your premium for three years. **The only way to dodge that is to fight the "
            "ticket:** hours of your time, months of waiting and no guarantee of "
            "winning. It's far easier not to get the ticket at all: stay within a few "
            "km/h of the limit."
        )
    else:
        _insurance = (
            "In BC, one ticket won't raise your insurance, but a second within a year "
            "will. **The only way to keep it off your record is to fight it:** hours of "
            "your time, and no guarantee of winning. It's easier not to get the "
            "ticket: stay within a few km/h of the limit."
        )

    mo.callout(
        mo.md(
            "### Side note: what about speeding tickets?\n"
            f"{_dollars}\n\n"
            f"{_insurance}\n\n"
            "**The cost you'll feel most is being late.** A stop takes about "
            f"{sc.STOP_MINUTES} minutes, and it lands on the trip where you were "
            f"trying to save time. Driving {_v:.0f} instead of {_lim:.0f} saves "
            f"**{_saved:.1f} minutes** on this {one_way.value:.0f} km trip; one stop "
            f"costs about {sc.STOP_MINUTES}. If you need to be somewhere on time, "
            f"leave {_saved:.0f} minutes earlier and drive the limit: you arrive just "
            "as soon, every time, without the risk. And the faster you go, the likelier "
            "the stop, so speeding hard because you're late is when you're most likely "
            "to be pulled over.\n\n"
            "*Tickets aren't counted in the cheapest speed: they depend on how heavily "
            "your route is patrolled, which nobody publishes, and they barely move the "
            "answer.*"
        ),
        kind="info",
    )
    return


@app.cell
def _(annual_km, best, curves, mo, scn, your_speed):
    _curve = curves.cost_curve(
        scn, annual_km, speeds=[best, scn.road.limit, your_speed.value]
    )
    _regret = dict(zip(_curve["speed"], _curve["regret"], strict=False))
    _hours = curves.hours_saved(scn, your_speed.value, annual_km)
    _limit = scn.road.limit
    mo.vstack(
        [
            mo.md(
                "---\n## 6. Putting it together\n"
                "Add every cost up for each speed and one of them comes out cheapest. "
                "Everything below responds to the sidebar."
            ),
            mo.hstack(
                [
                    mo.stat(
                        f"{best:.0f} km/h",
                        label="Cheapest speed",
                        bordered=True,
                        caption=f"{scn.vehicle.name} on {scn.road.name}",
                    ),
                    mo.stat(
                        f"+${_regret[_limit]:,.0f}/yr",
                        label=f"Driving the limit ({_limit:.0f})",
                        bordered=True,
                        caption="vs. the cheapest speed",
                    ),
                    mo.stat(
                        f"+${_regret[your_speed.value]:,.0f}/yr",
                        label=f"Driving {your_speed.value:.0f}",
                        bordered=True,
                        caption=f"{_hours:+.0f} hours/yr saved vs. the limit",
                    ),
                ],
                widths="equal",
                wrap=True,
            ),
            your_speed,
        ]
    )
    return


@app.cell
def _(mo, road, sc):
    # Recreated when the road changes, so defaults match that stretch.
    _per_day, _km = sc.TRAFFIC[road.value]
    traffic = mo.ui.slider(
        2_000,
        300_000,
        step=1_000,
        value=_per_day,
        label="Vehicles per day",
        show_value=True,
    )
    stretch = mo.ui.slider(
        10, 400, step=10, value=_km, label="Length of stretch (km)", show_value=True
    )
    return stretch, traffic


@app.cell
def _(best, charts, curves, mo, scn, stretch, traffic, your_speed):
    _flow, _limit = scn.road.flow, scn.road.limit
    _speeds = {
        f"Keeping pace with traffic ({_flow:.0f})": _flow,
        f"The limit ({_limit:.0f})": _limit,
        f"The cheapest speed ({best:.0f})": best,
        f"Your speed ({your_speed.value:.0f})": your_speed.value,
    }
    _df = curves.road_deaths(scn, traffic.value, stretch.value, _speeds)
    _now, _at_limit, _at_best = _df["deaths"].iloc[:3]
    mo.vstack(
        [
            mo.md(
                f"### Lives on {scn.road.name}\n"
                "Your speed doesn't only matter to you. Here is what the same model "
                f"says for everyone driving this stretch, if traffic on average drove "
                "each speed."
            ),
            mo.hstack([traffic, stretch], justify="start", gap=2),
            charts.deaths_chart(_df),
            mo.md(
                f"Today, with traffic averaging about {_flow:.0f} km/h, this model "
                f"expects about **{_now:.1f} deaths a year** here. If everyone kept to "
                f"the {_limit:.0f} km/h limit, that falls by about **"
                f"{_now - _at_limit:.1f} lives a year**; at {best:.0f} km/h, by about "
                f"**{_now - _at_best:.1f}**."
            ),
            mo.callout(
                mo.md(
                    "These are rough estimates: traffic volumes and the death rate are "
                    "approximate, so read them as orders of magnitude. The speed effect "
                    "itself is the best-established part: the power model was built "
                    "from what happened to deaths when whole roads' average speeds "
                    "changed. Those changes were mostly modest, so the further a speed "
                    "is from today's traffic, the less precise its number."
                ),
                kind="neutral",
            ),
        ]
    )
    return


@app.cell
def _(annual_km, best, charts, curves, mo, scn, your_speed):
    _curve = curves.cost_curve(scn, annual_km)
    _markers = {
        "cheapest": best,
        "limit": scn.road.limit,
        "traffic": scn.road.flow,
        "you": your_speed.value,
    }
    mo.vstack(
        [
            mo.md(
                "### What each speed costs you\n"
                "Extra yearly cost compared with the cheapest speed. The shaded band is "
                "within \\$100/yr of it — the curve is flat near the bottom and steep "
                "above the limit."
            ),
            charts.regret_chart(_curve, _markers),
            mo.md(
                f"### Where the money goes at {your_speed.value:.0f} km/h\n"
                f"Each cost compared with driving the {scn.road.limit:.0f} km/h limit. "
                "Your time shows as a saving when you go faster."
            ),
            charts.tradeoff_chart(
                curves.tradeoff(scn, your_speed.value, annual_km),
                your_speed.value,
                scn.road.limit,
            ),
            mo.md(
                "### Your whole commute bill\n"
                "Total yearly cost by type. Time is the biggest piece, but it shrinks "
                "slowly while the others grow."
            ),
            charts.components_chart(_curve, _markers),
        ]
    )
    return


@app.cell
def _(charts, curves, mo, scn):
    mo.vstack(
        [
            mo.md(
                "## Why the naive answer is wrong\n"
                "Counting only time and fuel points much higher than this model's answer. "
                "Each step adds one more real cost; the shaded bar shows how far the "
                "cheapest speed moves."
            ),
            charts.waterfall_chart(curves.waterfall(scn), scn.road.limit),
        ]
    )
    return


@app.cell
def _(mo):
    run_mc = mo.ui.run_button(label="Run 1,000 simulations per vehicle")
    return (run_mc,)


@app.cell
def _(
    Ranges,
    build,
    charts,
    curves,
    deviation,
    mo,
    price,
    run_mc,
    sc,
    scn,
    value_of_time,
):
    mo.stop(
        not run_mc.value,
        mo.vstack(
            [
                mo.md(
                    "## How sure are we?\n"
                    "Many inputs are estimates. This reruns the model with each one "
                    "varied across a plausible range, and shows where the cheapest speed "
                    "lands for each vehicle."
                ),
                run_mc,
            ]
        ),
    )
    _cases = {
        v.name: build(v, price.value if v.name == scn.vehicle.name else None)
        for v in sc.VEHICLES
    }
    _ranges = Ranges(
        value_of_time=(value_of_time * 0.8, value_of_time * 1.15),
        deviation_penalty=(deviation.value, deviation.value),
    )
    _df = curves.uncertainty(_cases, _ranges, n=1000)
    _above = (
        _df.assign(above=_df["speed"] > scn.road.limit)
        .groupby("case")["above"]
        .mean()
        .reindex(list(_cases))
    )
    mo.vstack(
        [
            mo.md("## How sure are we?"),
            charts.uncertainty_chart(_df, scn.road.limit),
            mo.md(
                "Each dot is one simulation; the orange tick is the median. Share of runs "
                "where driving above the limit pays off: "
                + ", ".join(f"**{k}** {v:.0%}" for k, v in _above.items())
            ),
            run_mc,
        ]
    )
    return


@app.cell
def _(mo, sc):
    _rows = "\n".join(
        f"| {s['input']} | {s['value'].replace('$', chr(92) + '$')} | {s['basis']} | "
        + (f"[link]({s['url']})" if s["url"] else "—")
        + " |"
        for s in sc.SOURCES
    )
    mo.md(
        "---\n## Assumptions and sources\n"
        "Every number on this page comes from one of these. Estimates are my best "
        "judgment; change them in the sidebar where you can.\n\n"
        "| Input | Value | Basis | Source |\n|---|---|---|---|\n" + _rows
    )
    return


if __name__ == "__main__":
    app.run()
