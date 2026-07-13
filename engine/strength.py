"""
strength.py
Computes BatStrength, BowlStrength, and NetStrength for a given
batsman vs bowler matchup.

All values stay in [0, 1] (net strength in [-1, 1]).
"""

from engine.loader import bat_skills, bowl_skills, mental, form, bowling_type


# -------------------------------------------------------------------
# Weights — must each group sum to 1.0
# -------------------------------------------------------------------

BAT_WEIGHTS = {
    "bat_power":        0.30,
    "bat_control":      0.25,
    "bat_aggression":   0.15,
    "matchup":          0.10,   # vs_pace or vs_spin depending on bowler
    "recent_form":      0.10,
    "pressure_handling":0.05,
    "consistency":      0.05,
}

BOWL_WEIGHTS = {
    "wicket_threat":  0.40,
    "economy_skill":  0.30,
    "death_skill":    0.20,
    "recent_form":    0.10,
}


# -------------------------------------------------------------------
# Core formulas
# -------------------------------------------------------------------

def bat_strength(batsman: dict, bowler: dict) -> float:
    """
    Calculate batting strength [0, 1] for this specific matchup.
    The matchup component switches between vs_pace / vs_spin
    depending on the bowler's type.
    """
    skills = bat_skills(batsman)
    m = mental(batsman)
    f = form(batsman)

    btype = bowling_type(bowler)
    matchup = skills["vs_pace"] if btype == "pace" else skills["vs_spin"]

    strength = (
        BAT_WEIGHTS["bat_power"]         * skills["bat_power"]
        + BAT_WEIGHTS["bat_control"]     * skills["bat_control"]
        + BAT_WEIGHTS["bat_aggression"]  * skills["bat_aggression"]
        + BAT_WEIGHTS["matchup"]         * matchup
        + BAT_WEIGHTS["recent_form"]     * f
        + BAT_WEIGHTS["pressure_handling"] * m["pressure_handling"]
        + BAT_WEIGHTS["consistency"]     * m["consistency"]
    )
    return round(min(max(strength, 0.0), 1.0), 4)


def bowl_strength(bowler: dict) -> float:
    """
    Calculate bowling strength [0, 1].
    """
    bskills = bowl_skills(bowler)
    f = form(bowler)

    strength = (
        BOWL_WEIGHTS["wicket_threat"]  * bskills["wicket_threat"]
        + BOWL_WEIGHTS["economy_skill"] * bskills["economy_skill"]
        + BOWL_WEIGHTS["death_skill"]   * bskills["death_skill"]
        + BOWL_WEIGHTS["recent_form"]   * f
    )
    return round(min(max(strength, 0.0), 1.0), 4)


def net_strength(batsman: dict, bowler: dict) -> float:
    """
    NetStrength = BatStrength - BowlStrength
    Positive  → batsman advantage
    Negative  → bowler advantage
    Range: approximately [-1, 1]
    """
    bs = bat_strength(batsman, bowler)
    bws = bowl_strength(bowler)
    return round(bs - bws, 4)


# -------------------------------------------------------------------
# Debug helper
# -------------------------------------------------------------------

def matchup_summary(batsman: dict, bowler: dict) -> dict:
    """Return a full breakdown for inspection / debugging."""
    bs = bat_strength(batsman, bowler)
    bws = bowl_strength(bowler)
    ns = net_strength(batsman, bowler)

    if ns >= 0.15:
        verdict = "Batsman dominates"
    elif ns >= 0.05:
        verdict = "Slight batting advantage"
    elif ns >= -0.05:
        verdict = "Balanced contest"
    elif ns >= -0.15:
        verdict = "Bowler advantage"
    else:
        verdict = "Bowler dominates"

    return {
        "batsman": batsman["name"],
        "bowler": bowler["name"],
        "bowler_type": bowling_type(bowler),
        "bat_strength": bs,
        "bowl_strength": bws,
        "net_strength": ns,
        "verdict": verdict,
    }
