"""
stadium.py
Loads cricket_stadiums.json and exposes:
  - list_stadiums()         -> print selection menu
  - get_stadium(id)         -> return stadium dict
  - stadium_modifiers(...)  -> per-ball probability multipliers

Rating scale in JSON: 0-100
  spin_advantage    : 0 = no spin help,  100 = extreme turner
  pace_advantage    : 0 = no pace help,  100 = green seamer
  batting_advantage : 0 = bowler's track, 100 = flat belter
  swing_factor      : 0 = no movement,   100 = heavy swing
  bounce            : 0 = slow/low,      100 = steep/high
  dew_factor        : 0 = negligible,    100 = heavy dew (2nd innings)
"""

import json
import os
from typing import Optional

_DATA_FILE = os.path.join(
    os.path.dirname(__file__), "..", "cricket_stadiums.json"
)

_cache: list[dict] = []


def _load() -> list[dict]:
    global _cache
    if _cache:
        return _cache
    with open(os.path.abspath(_DATA_FILE), "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache = data["stadiums"]
    return _cache


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_stadiums() -> list[dict]:
    return _load()


def get_stadium(stadium_id: int) -> dict:
    for s in _load():
        if s["id"] == stadium_id:
            return s
    raise KeyError(f"Stadium id {stadium_id} not found.")


def print_stadium_menu():
    """Print the interactive selection table."""
    stadiums = _load()
    print("\n  CHOOSE STADIUM")
    print(f"  {'#':<4} {'Stadium':<42} {'City':<14} {'Favours'}")
    print(f"  {'-'*76}")
    for s in stadiums:
        favours = s["favoured_discipline"].capitalize()
        avg     = s["avg_first_innings_t20"]
        print(
            f"  {s['id']:<4} {s['name']:<42} {s['city']:<14} "
            f"{favours:<10}  (avg 1st inn: {avg})"
        )


def print_stadium_card(s: dict):
    """Print a brief venue card before the match starts."""
    r = s["ratings"]
    print(f"\n  VENUE: {s['name']}, {s['city']}")
    print(f"  Pitch : {s['pitch_type']}")
    print(f"  Capacity: {s['capacity']:,}  |  Avg 1st innings: {s['avg_first_innings_t20']}")
    print(f"  Toss bias: {s['toss_decision_bias'].capitalize()}")
    print(f"\n  Conditions (0-100 scale):")
    print(f"    Batting advantage : {r['batting_advantage']:>3}")
    print(f"    Spin advantage    : {r['spin_advantage']:>3}")
    print(f"    Pace advantage    : {r['pace_advantage']:>3}")
    print(f"    Swing factor      : {r['swing_factor']:>3}")
    print(f"    Bounce            : {r['bounce']:>3}")
    print(f"    Dew factor (eve.) : {r['dew_factor']:>3}")
    print(f"\n  Note: {s['notes']}")


# ---------------------------------------------------------------------------
# Probability modifier
# ---------------------------------------------------------------------------

# Outcome keys that exist in the probability engine
_OUTCOMES = ["0", "1", "2", "3", "4", "6", "W", "Wd", "Nb"]


def stadium_modifiers(
    stadium: dict,
    bowler_type: str,       # "pace" or "spin"
    over: int,              # 0-indexed
    second_innings: bool,
) -> dict[str, float]:
    """
    Return a multiplier for every outcome based on stadium conditions.
    All modifiers are centred at 1.0 (neutral = no effect).
    After applying these, the caller must re-normalise probabilities.
    """
    r = stadium["ratings"]

    # Normalise ratings to usable scales
    bat_adv  = (r["batting_advantage"] - 50) / 50  # -1.0 (bowling) to +1.0 (batting)
    spin_adv = r["spin_advantage"]   / 100          # 0.0 -> 1.0
    pace_adv = r["pace_advantage"]   / 100
    swing    = r["swing_factor"]     / 100
    bounce   = r["bounce"]           / 100
    dew      = r["dew_factor"]       / 100

    mods = {k: 1.0 for k in _OUTCOMES}

    # ------------------------------------------------------------------
    # 1. Batting advantage — shifts base run/wicket balance for ALL bowlers
    # ------------------------------------------------------------------
    # bat_adv  > 0  (flat pitch) -> more runs, fewer wickets
    # bat_adv  < 0  (bowling pitch) -> fewer runs, more wickets
    mods["0"] *= max(0.55, 1 - bat_adv * 0.22)   # dots decrease on flat pitch
    mods["W"] *= max(0.55, 1 - bat_adv * 0.28)   # wickets decrease on flat pitch
    mods["4"] *= max(0.20, 1 + bat_adv * 0.22)   # boundaries increase
    mods["6"] *= max(0.20, 1 + bat_adv * 0.18)
    mods["1"] *= max(0.60, 1 + bat_adv * 0.08)
    mods["2"] *= max(0.60, 1 + bat_adv * 0.10)

    # ------------------------------------------------------------------
    # 2. Bowler-type specific: spin
    # ------------------------------------------------------------------
    if bowler_type == "spin":
        eff = spin_adv

        # Dew in 2nd innings degrades spin effectiveness significantly
        if second_innings:
            dew_penalty = dew * 0.55
            eff = max(0.0, eff - dew_penalty)

        mods["W"] *= 1 + eff * 0.30
        mods["0"] *= 1 + eff * 0.20
        mods["4"] *= max(0.20, 1 - eff * 0.14)
        mods["6"] *= max(0.20, 1 - eff * 0.12)

    # ------------------------------------------------------------------
    # 3. Bowler-type specific: pace
    # ------------------------------------------------------------------
    elif bowler_type == "pace":
        eff = pace_adv

        # Swing boosts pace in the powerplay (new-ball movement)
        if over < 6:
            eff = min(1.0, eff + swing * 0.30)

        # Bounce always helps pace bowlers generate edges and top-edges
        eff = min(1.0, eff + bounce * 0.12)

        mods["W"] *= 1 + eff * 0.25
        mods["0"] *= 1 + eff * 0.15
        mods["4"] *= max(0.20, 1 - eff * 0.10)

    # ------------------------------------------------------------------
    # 4. Extras: swing / pace conditions slightly raise wides for swing bowlers
    # ------------------------------------------------------------------
    if bowler_type == "pace" and swing > 0.5:
        mods["Wd"] *= 1 + (swing - 0.5) * 0.40

    return mods
