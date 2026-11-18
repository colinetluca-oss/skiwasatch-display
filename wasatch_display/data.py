"""What the display shows: snow, drive times, road traffic and alerts.

Right now this only has sample situations. The next milestone replaces
`sample()` with live data from Open-Meteo / SNOTEL (snow), Mapbox (traffic)
and UDOT (closures). Everything else in the program reads this same shape,
so swapping in live data won't change the drawing code.
"""
from dataclasses import dataclass, field
from . import config

G, W, R, X = "good", "warn", "bad", "closed"


@dataclass
class DisplayData:
    when: str                      # text shown under the title
    snow: dict                     # resort id -> (new 24h, forecast 48h, base) in inches
    roads: dict                    # direction -> road piece -> traffic level
    times: dict                    # direction -> resort id -> minutes (None = closed)
    alerts: list = field(default_factory=list)   # (level, bold part, rest)
    is_sample: bool = True


def level(minutes, normal):
    """Turn a drive time into a traffic level by comparing it to normal."""
    if minutes is None:
        return "closed"
    ratio = minutes / normal
    if ratio < config.SLOW_AT:
        return "good"
    if ratio <= config.VERY_SLOW_AT:
        return "warn"
    return "bad"


ALL_GREEN = {k: G for k in ["foothill", "i215", "wasatch", "lccLow", "lccUp", "bccLow", "bccUp", "i80", "sr224"]}

SAMPLES = {
    "powder": DisplayData(
        when="Saturday · 7:40 AM",
        snow={"alta": (14, 6, 88), "snowbird": (13, 6, 84), "solitude": (9, 5, 68), "brighton": (10, 5, 70), "park": (4, 2, 52)},
        roads={"to": {**ALL_GREEN, "i215": W, "wasatch": R, "lccLow": R, "lccUp": W, "bccLow": W}, "from": dict(ALL_GREEN)},
        times={"to": {"alta": 94, "snowbird": 88, "solitude": 57, "brighton": 63, "park": 38},
               "from": {"alta": 42, "snowbird": 39, "solitude": 38, "brighton": 42, "park": 34}},
        alerts=[("warn", "SR-210 Little Cottonwood:", "traction law, 4WD or chains required"),
                ("warn", "SR-190 Big Cottonwood:", "traction law in effect")]),
    "bluebird": DisplayData(
        when="Tuesday · 10:15 AM",
        snow={"alta": (0, 0, 86), "snowbird": (0, 0, 82), "solitude": (0, 0, 66), "brighton": (0, 0, 68), "park": (0, 0, 50)},
        roads={"to": dict(ALL_GREEN), "from": dict(ALL_GREEN)},
        times={"to": {"alta": 41, "snowbird": 38, "solitude": 37, "brighton": 42, "park": 33},
               "from": {"alta": 40, "snowbird": 37, "solitude": 37, "brighton": 41, "park": 34}},
        alerts=[("good", "", "No canyon restrictions")]),
    "exodus": DisplayData(
        when="Sunday · 3:50 PM",
        snow={"alta": (2, 0, 90), "snowbird": (2, 0, 86), "solitude": (1, 0, 69), "brighton": (1, 0, 71), "park": (0, 0, 53)},
        roads={"to": dict(ALL_GREEN),
               "from": {**ALL_GREEN, "i215": W, "wasatch": R, "lccLow": R, "lccUp": W, "bccLow": W, "i80": W, "sr224": W}},
        times={"to": {"alta": 40, "snowbird": 37, "solitude": 37, "brighton": 41, "park": 34},
               "from": {"alta": 105, "snowbird": 98, "solitude": 56, "brighton": 62, "park": 49}},
        alerts=[("warn", "SR-210:", "heavy downhill traffic, about a 60 minute delay")]),
    "closed": DisplayData(
        when="Friday · 6:30 AM",
        snow={"alta": (22, 8, 96), "snowbird": (20, 8, 92), "solitude": (15, 6, 76), "brighton": (16, 6, 78), "park": (7, 3, 57)},
        roads={"to": {**ALL_GREEN, "wasatch": W, "lccLow": X, "lccUp": X, "bccLow": W, "bccUp": W},
               "from": {**ALL_GREEN, "lccLow": X, "lccUp": X}},
        times={"to": {"alta": None, "snowbird": None, "solitude": 52, "brighton": 58, "park": 36},
               "from": {"alta": None, "snowbird": None, "solitude": 40, "brighton": 44, "park": 34}},
        alerts=[("bad", "SR-210 closed", "for avalanche control. Next update 8:00 AM"),
                ("warn", "SR-190:", "traction law, 4WD or chains required")]),
}

SAMPLE_ORDER = ["powder", "bluebird", "exodus", "closed"]


def sample(name="powder"):
    return SAMPLES[name]
