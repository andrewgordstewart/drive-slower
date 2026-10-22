"""Preset inputs. Each constant notes whether it's sourced or an estimate.

Two perspectives:
  private  your own costs only: your share of crash harm, no CO2.
  social   everyone's costs: full crash harm plus CO2 at Canada's social cost of carbon.
"""

import math
from typing import Literal

from drive_slower.speed_model import (
    CrashModel,
    Maintenance,
    Road,
    Scenario,
    TicketRules,
    Tickets,
    Vehicle,
)

Perspective = Literal["private", "social"]

ANNUAL_KM = 24_000  # 50 km each way, 240 workdays, all at free flow (an upper bound)

# Value of commute time, $/hr. US DOT values local personal travel at 50% of hourly
# income; 50% of a ~$32 gross individual wage is $16, and DOT's own method (household
# income, ~$96k gross est. from StatCan's 2023 $74.2k after-tax median) gives ~$23.
VOT_LOW, VOT_DEFAULT, VOT_HIGH = 16.0, 20.0, 23.0

# Median gross wage, $/hr: StatCan reported ~$30 for 2024; ~$32 for 2026 is extrapolated.
MEDIAN_WAGE = 32.0
# Combined federal + provincial + CPP/EI marginal rate at ~$62k. Federal and Ontario
# brackets are sourced (CRA, KPMG); BC's 7.7% second bracket wasn't confirmed.
MARGINAL_TAX = {"BC": 0.34, "ON": 0.36}

# Energy prices, $/unit. Estimates: no current pump prices were found.
PRICES = {
    ("BC", "L"): 1.70,
    ("ON", "L"): 1.45,
    ("BC", "kWh"): 0.14,  # BC Hydro residential, rough
    ("ON", "kWh"): 0.13,  # rough
}

# Crash cost at the road's flow speed, $/km. Estimate: ~0.5 deaths per 100M vehicle-km
# on Canadian highways x ~$9M value of a statistical life = ~$0.045/km fatal; injuries
# and property bring the comprehensive total to ~2-3x. Your own share is roughly half.
CRASH_PRIVATE = 0.05
CRASH_SOCIAL = 0.11

# Minutes of life: a typical 40-year-old's remaining waking hours, ~43 years left
# (StatCan 2023: 41.4 for men at 40, women a few more) x 16 hours a day.
REMAINING_WAKING_HOURS = 43 * 365 * 16

# Transport Canada, Canadian Motor Vehicle Traffic Collision Statistics 2023.
ROAD_DEATHS, ROAD_DEATHS_YEAR = 1964, 2023

CO2_SOCIAL_PRICE = 250.0  # $/t, approx. ECCC social cost of carbon

# Fuel use at 100 and 120 km/h. Sedan matches NRCan's "~20% more at 120"; the F-150 gas
# figures are estimates that agree with a drag + rolling-resistance physics check; the
# Lightning figures are estimates.
SEDAN = Vehicle(
    "Sedan", "L", 7.5, 9.0, co2_kg_per_unit=2.3, fill_size=40, stop_minutes=10
)
F150 = Vehicle(
    "F-150", "L", 10.6, 13.3, co2_kg_per_unit=2.3, fill_size=70, stop_minutes=10
)
F150_LIGHTNING = Vehicle(
    "F-150 Lightning",
    "kWh",
    28.0,
    36.0,
    co2_kg_per_unit=0.012,
    fill_size=100,
    stop_minutes=0,
)
VEHICLES = (SEDAN, F150, F150_LIGHTNING)

# Flow speeds are estimates of typical free-flow traffic, not measurements.
ROADS = {
    "BC Hwy 1 (Lower Mainland)": ("BC", Road("BC Hwy 1", limit=100, flow=105)),
    "Coquihalla": ("BC", Road("Coquihalla", limit=120, flow=120)),
    "Ontario 401": ("ON", Road("Ontario 401", limit=100, flow=110)),
}

# Traffic on each stretch: (vehicles per day, km). Rough estimates, not counts.
TRAFFIC = {
    "BC Hwy 1 (Lower Mainland)": (100_000, 50),
    "Coquihalla": (12_000, 200),
    "Ontario 401": (150_000, 100),
}

# Deaths per vehicle-km at the road's normal traffic speed; the same figure underlies
# CRASH_*. Transport Canada puts all roads at 4.3-4.9 per billion vehicle-km (2018-22);
# divided freeways are probably safer, so this likely overstates their risk.
FATALITY_RATE = 0.5e-8
# Drivers were 52% of Canada's road deaths in 2023 (Transport Canada, Table S10).
DRIVER_SHARE = 0.52

# Speeding tickets: shown on the side, not in the cheapest speed (see Tickets).
# Enforcement is an estimate, about one ticket per 100,000 km driven well past police
# tolerance; nobody publishes patrol density or tolerance.
TICKETS_PER_10K_KM = 0.1
TICKET_TOLERANCE = 15.0  # km/h over
# Routine stops mostly take 10-15 min. Add ~10 min to pay, and the ~16% of BC tickets
# that are disputed (~30% of those reach a ~4 h hearing): ~40 min per ticket on average.
STOP_MINUTES = 15
TICKET_HOURS = 40 / 60
IMPOUND_HOURS = 10.0  # estimate: getting home, a week without the vehicle, the lot

TICKET_RULES = {
    # Fines over 40 km/h over are sourced (gov.bc.ca); lower tiers only from secondary
    # sources. One 3-point ticket adds no ICBC premium, but two in a year cost $367, so
    # ~$50 expected per ticket (estimate). Beyond 40 over: 7-day impound plus Driver
    # Risk Premium, ~$1,500 (estimate).
    "BC": TicketRules(
        fines=((20, 138, 0), (40, 196, 0), (60, 368, 0), (math.inf, 483, 0)),
        insurance=50,
        severe_over=40,
        severe_cost=1_500,
        hours=TICKET_HOURS,
        severe_hours=IMPOUND_HOURS,
    ),
    # Fines ~$2.50-3.75 per km/h over plus ~$25 in surcharges (law-firm sources). One
    # minor conviction raised a sample driver's premium ~11%, ~$1,000 over three years
    # (Ratehub); some insurers forgive a first. 50+ over is stunt driving: $2,000+ fine,
    # 14-day impound, a large premium increase (~$5,000 all-in, estimate).
    "ON": TicketRules(
        fines=((15, 25, 2.5), (29, 25, 3.0), (math.inf, 25, 3.75)),
        insurance=1_000,
        severe_over=49,
        severe_cost=5_000,
        hours=TICKET_HOURS,
        severe_hours=IMPOUND_HOURS,
    ),
}


def tickets(road: str = "BC Hwy 1 (Lower Mainland)") -> Tickets:
    region, _ = ROADS[road]
    return Tickets(TICKET_RULES[region], TICKETS_PER_10K_KM, TICKET_TOLERANCE)


def scenario(
    vehicle: Vehicle = F150,
    road: str = "BC Hwy 1 (Lower Mainland)",
    perspective: Perspective = "private",
    value_of_time: float = VOT_DEFAULT,
    deviation_penalty: float = 0.0,
) -> Scenario:
    region, r = ROADS[road]
    social = perspective == "social"
    return Scenario(
        vehicle=vehicle,
        road=r,
        energy_price=PRICES[(region, vehicle.energy_unit)],
        value_of_time=value_of_time,
        crash=CrashModel(
            CRASH_SOCIAL if social else CRASH_PRIVATE,
            deviation_penalty=deviation_penalty,
        ),
        # EVs skip oil changes and most engine work; tires wear about the same or faster.
        maintenance=Maintenance(
            other_per_km=0.025 if vehicle.energy_unit == "kWh" else 0.04
        ),
        co2_price=CO2_SOCIAL_PRICE if social else 0.0,
    )


# Shown in the demo's "Assumptions and sources" table.
SOURCES = [
    {
        "input": "Median wage",
        "value": "≈$30/hr (2024), ≈$32 assumed for 2026",
        "basis": "sourced",
        "url": "https://newsinteractives.cbc.ca/embeds/2025/wages-inflation",
    },
    {
        "input": "Commute time worth ~50% of income",
        "value": "$16–23/hr, default $20",
        "basis": "sourced",
        "url": "https://www.faa.gov/regulations_policies/policy_guidance/benefit_cost/econ-value-section-1-tx-time.pdf",
    },
    {
        "input": "Median household after-tax income",
        "value": "$74,200 (2023)",
        "basis": "sourced",
        "url": "https://www150.statcan.gc.ca/n1/daily-quotidien/250501/dq250501b-eng.htm",
    },
    {
        "input": "Marginal tax at ~$62k",
        "value": "≈34% BC, ≈36% Ontario",
        "basis": "mostly sourced",
        "url": "https://assets.kpmg.com/content/dam/kpmg/ca/pdf/2026/01/ca-federal-and-provincial-territorial-income-tax-rates-and-brackets-for-2026.pdf",
    },
    {
        "input": "Fuel use rises ~20% from 100 to 120 km/h (cars)",
        "value": "sedan 7.5 → 9.0 L/100 km",
        "basis": "sourced",
        "url": "https://greenactioncentre.ca/?p=2298",
    },
    {
        "input": "F-150 fuel use",
        "value": "10.6 → 13.3 L/100 km",
        "basis": "estimate (agrees with a physics check)",
        "url": "",
    },
    {
        "input": "F-150 Lightning energy use",
        "value": "28 → 36 kWh/100 km",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Gas and electricity prices",
        "value": "BC $1.70/L, ON $1.45/L, ~$0.13–0.14/kWh",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Crash risk rises ~speed⁴ (power model)",
        "value": "exponent 4 fatal / 3 serious / 2 minor",
        "basis": "sourced",
        "url": "https://toi.brage.unit.no/toi-xmlui/bitstream/11250/2602278/1/Elvik_10.1016_j.aap.2018.11.014.pdf",
    },
    {
        "input": "Remaining life at 40",
        "value": "≈43 years (41.4 for men)",
        "basis": "partly sourced",
        "url": "https://www.lifetable.de/File/GetDocument/data%5CCAN%5CCAN000020232023CU1.pdf",
    },
    {
        "input": "Road deaths in Canada",
        "value": "1,964 (2023)",
        "basis": "sourced",
        "url": "https://tc.canada.ca/en/road-transportation/statistics-data/canadian-motor-vehicle-traffic-collision-statistics/2023/canadian-motor-vehicle-traffic-collision-statistics-2023",
    },
    {
        "input": "Highway deaths per km driven",
        "value": "≈0.5 per 100 million vehicle-km (Canada, all roads: 0.43–0.49)",
        "basis": "sourced (all roads)",
        "url": "https://tdih-cdit.tc.canada.ca/sites/default/files/addendum-tables/2023/S7-en.pdf",
    },
    {
        "input": "Drivers' share of road deaths",
        "value": "52% (2023)",
        "basis": "sourced",
        "url": "https://tdih-cdit.tc.canada.ca/sites/default/files/addendum-tables/2024/S10-en.pdf",
    },
    {
        "input": "Traffic on each stretch",
        "value": "Hwy 1: 100k/day × 50 km; Coquihalla: 12k × 200 km; 401: 150k × 100 km",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Crash cost at traffic speed",
        "value": "$0.05/km (yours), $0.11/km (everyone's)",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Slower-than-traffic risk",
        "value": "off by default; evidence is mixed",
        "basis": "contested",
        "url": "https://en.wikipedia.org/wiki/Solomon_curve",
    },
    {
        "input": "Traffic flow speeds",
        "value": "Hwy 1: 105, Coquihalla: 120, 401: 110 km/h",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Wear & maintenance",
        "value": "tires ~$0.02/km, other ~$0.04/km",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Refuelling stop",
        "value": "10 min per ~70 L",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Speeding fines (BC)",
        "value": "$138 / $196 / $368–483 by km/h over",
        "basis": "partly sourced",
        "url": "https://www2.gov.bc.ca/gov/content/transportation/driving-and-cycling/roadsafetybc/high-risk/speed",
    },
    {
        "input": "ICBC points premium",
        "value": "$0 for one ticket, $367 for two in a year",
        "basis": "sourced",
        "url": "https://icbc.com/driver-licensing/tickets/Driver-Penalty-Points",
    },
    {
        "input": "Insurance after a ticket (Ontario)",
        "value": "≈+11%, ~$1,000 over 3 years (one sample driver)",
        "basis": "sourced (comparison site)",
        "url": "https://www.ratehub.ca/blog/total-cost-traffic-ticket-ontario/",
    },
    {
        "input": "Time lost per ticket",
        "value": "~15 min stop; ~40 min average incl. paying and disputes",
        "basis": "partly sourced",
        "url": "https://news.gov.bc.ca/releases/2021AG0107-001312",
    },
    {
        "input": "Ticket enforcement",
        "value": "~1 per 100,000 km driven >15 km/h over",
        "basis": "estimate",
        "url": "",
    },
    {
        "input": "Social cost of carbon",
        "value": "≈$250/t CO₂",
        "basis": "approximate",
        "url": "",
    },
]
