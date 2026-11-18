"""Settings for the display. Change things here, not deep in the code."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# Where drive times start and end.
HOME_NAME = "Home"

# The five resorts, in the order they are listed in the code.
# "normal" is the typical empty-road drive time from home, in minutes.
# These are starting guesses; once live traffic works we'll measure real ones.
RESORTS = [
    {"id": "alta",     "name": "Alta",      "normal": 40},
    {"id": "snowbird", "name": "Snowbird",  "normal": 37},
    {"id": "solitude", "name": "Solitude",  "normal": 37},
    {"id": "brighton", "name": "Brighton",  "normal": 41},
    {"id": "park",     "name": "Park City", "normal": 33},
]

# Camera: looking east from above the valley.
PITCH_DEGREES = 55        # 0 = looking straight down, 90 = looking at the horizon
FIELD_OF_VIEW = 42        # vertical field of view, degrees
HEIGHT_STRETCH = 1.35     # makes mountains 35% taller so they read from across the room

# How much of the screen width the map takes (the rest is the resort panel).
MAP_SHARE = 0.69

# Road colors: drive time compared to normal.
SLOW_AT = 1.25            # 25% slower than normal -> orange
VERY_SLOW_AT = 1.75       # 75% slower than normal -> red

# Colors (red, green, blue)
COLORS = {
    "night": (11, 17, 26),
    "panel": (15, 24, 36),
    "line": (31, 44, 59),
    "ink": (233, 239, 246),
    "muted": (135, 152, 173),
    "snow": (166, 220, 255),
    "good": (54, 196, 111),
    "warn": (255, 162, 46),
    "bad": (255, 79, 79),
    "sky_top": (6, 11, 20),
    "sky_low": (29, 44, 64),
}
