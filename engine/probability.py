"""
probability.py
Converts a matchup's NetStrength + match context + stadium conditions into a
normalized probability distribution over all possible ball outcomes, then samples one.

Outcomes: 0 (dot), 1, 2, 3, 4, 6, 'W' (wicket), 'Wd' (wide), 'Nb' (no-ball)
"""

import random
from engine.strength import net_strength
from engine.loader import bat_skills, bowling_type
from engine.stadium import stadium_modifiers
from typing import Optional


# -------------------------------------------------------------------
# Average T20 base probabilities
# -------------------------------------------------------------------

BASE_PROBS: dict[str, float] = {
    "0":  0.38,
    "1":  0.32,
    "2":  0.08,
    "3":  0.01,
    "4":  0.13,
    "6":  0.04,
    "W":  0.03,
    "Wd": 0.008,
    "Nb": 0.002,
}

OUTCOMES = list(BASE_PROBS.keys())


# -------------------------------------------------------------------
# Match phase constants
# -------------------------------------------------------------------

POWERPLAY_END     = 6
DEATH_START       = 16
PRESSURE_BASE_RRR = 8.0


# -------------------------------------------------------------------
# Matchup modifiers (player skill based)
# -------------------------------------------------------------------

def _boundary_modifier(ns: float) -> float:
    return 1.0 + (ns * 0.6)

def _wicket_modifier(ns: float) -> float:
    return 1.0 - (ns * 0.5)

def _economy_modifier(ns: float) -> float:
    return 1.0 - (ns * 0.4)

def _aggression_modifier(batsman: dict) -> float:
    aggression = bat_skills(batsman)["bat_aggression"]
    return 1.0 + (aggression - 0.5) * 0.5

def _pressure_modifier(runs_needed: int, balls_remaining: int) -> float:
    if balls_remaining <= 0 or runs_needed <= 0:
        return 1.0
    rrr = runs_needed / (balls_remaining / 6.0)
    return 1.0 + (rrr - PRESSURE_BASE_RRR) * 0.05

def _phase_modifiers(over: int) -> dict[str, float]:
    mods = {k: 1.0 for k in OUTCOMES}
    if over < POWERPLAY_END:
        mods["4"] = 1.15
        mods["6"] = 1.10
    elif over >= DEATH_START:
        mods["6"] = 1.40
        mods["W"] = 1.30
        mods["0"] = 0.85
    return mods


# -------------------------------------------------------------------
# Main probability engine
# -------------------------------------------------------------------

def compute_probs(
    batsman: dict,
    bowler: dict,
    over: int,
    runs_needed: int = 0,
    balls_remaining: int = 120,
    second_innings: bool = False,
    stadium: Optional[dict] = None,
) -> dict[str, float]:
    """
    Compute a normalized probability dict for every possible outcome
    on this specific delivery.

    Parameters
    ----------
    batsman        : player dict (striker)
    bowler         : player dict (current bowler)
    over           : current over number (0-indexed)
    runs_needed    : runs still needed to win (2nd innings only)
    balls_remaining: balls left in the innings
    second_innings : whether this is the chase
    stadium        : stadium dict from cricket_stadiums.json (optional)
    """
    ns = net_strength(batsman, bowler)

    bm       = _boundary_modifier(ns)
    wm       = _wicket_modifier(ns)
    em       = _economy_modifier(ns)
    am       = _aggression_modifier(batsman)
    pm       = _phase_modifiers(over)
    pressure = _pressure_modifier(runs_needed, balls_remaining) if second_innings else 1.0

    # Stadium modifiers — if no stadium selected, all = 1.0
    if stadium:
        btype = bowling_type(bowler)
        sm = stadium_modifiers(stadium, btype, over, second_innings)
    else:
        sm = {k: 1.0 for k in OUTCOMES}

    # Apply all modifiers to base probabilities
    probs = {}
    for outcome, base in BASE_PROBS.items():
        p = base

        if outcome == "0":
            p *= em * pm["0"] * sm["0"]
        elif outcome == "1":
            p *= (1.0 + ns * 0.1) * pm["1"] * sm["1"]
        elif outcome == "2":
            p *= (1.0 + ns * 0.2) * pm["2"] * sm["2"]
        elif outcome == "3":
            p *= pm["3"] * sm["3"]
        elif outcome == "4":
            p *= bm * pm["4"] * sm["4"]
        elif outcome == "6":
            p *= bm * am * pm["6"] * sm["6"] * (pressure if second_innings else 1.0)
        elif outcome == "W":
            p *= wm * pm["W"] * sm["W"] * pressure
        elif outcome in ("Wd", "Nb"):
            p *= (1.0 + (0.2 if over >= DEATH_START else 0.0)) * sm[outcome]

        probs[outcome] = max(p, 0.0)

    # Normalize
    total = sum(probs.values())
    return {k: round(v / total, 6) for k, v in probs.items()}


def sample_outcome(probs: dict[str, float]) -> str:
    return random.choices(list(probs.keys()), weights=list(probs.values()), k=1)[0]


def ball_outcome(
    batsman: dict,
    bowler: dict,
    over: int,
    runs_needed: int = 0,
    balls_remaining: int = 120,
    second_innings: bool = False,
    stadium: Optional[dict] = None,
) -> tuple[str, dict[str, float]]:
    """Compute probs and sample in one call. Returns (outcome, probs_dict)."""
    probs = compute_probs(
        batsman, bowler, over, runs_needed, balls_remaining, second_innings, stadium
    )
    return sample_outcome(probs), probs
