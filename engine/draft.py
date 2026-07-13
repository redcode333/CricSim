"""
draft.py
11-round snake draft from the pool of all 250 players.
"""
from __future__ import annotations
import random
from engine.loader import list_players

# Sensible XI composition target: 1 keeper, ~5 batters, ~2 all-rounders, ~3 bowlers.
_ROLE_TARGETS = {"wicket_keeper": 1, "batter": 5, "all_rounder": 2, "bowler": 3}


def overall_rating(p: dict) -> float:
    s = p["skills"]
    b = p["bowling"]
    m = p["mental"]
    f = p["form"]["recent_form"]
    role = p.get("role", "batter")

    bat = (
        s["bat_power"] * 0.25 + s["bat_control"] * 0.30 + s["bat_aggression"] * 0.10
        + s["vs_pace"] * 0.10 + s["vs_spin"] * 0.10
        + m["consistency"] * 0.08 + m["pressure_handling"] * 0.07
    )
    bowl = (
        b["wicket_threat"] * 0.40 + b["economy_skill"] * 0.35
        + b["death_skill"] * 0.15 + f * 0.10
    )
    if role in ("batter", "wicket_keeper"):
        return bat * 0.75 + bowl * 0.25
    if role == "bowler":
        return bat * 0.25 + bowl * 0.75
    return bat * 0.5 + bowl * 0.5          # all_rounder


def get_draft_pool() -> list[dict]:
    """All 250 players sorted best-first by overall_rating."""
    return sorted(list_players(), key=overall_rating, reverse=True)


def _weighted_pick(candidates: list[dict]) -> dict:
    """Pick among candidates with randomness, still strongly favoring higher-rated ones."""
    if len(candidates) == 1:
        return candidates[0]
    weights = [max(0.01, overall_rating(p)) ** 4 for p in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def ai_pick(pool: list[dict], ai_xi: list[dict]) -> dict:
    """
    AI drafts by quality *and* team need, with weighted randomness so it
    doesn't draft the exact same XI every time a given pool state recurs.
    """
    picks_left = 11 - len(ai_xi)
    counts: dict[str, int] = {}
    for p in ai_xi:
        counts[p["role"]] = counts.get(p["role"], 0) + 1
    wk    = counts.get("wicket_keeper", 0)
    bowls = counts.get("bowler", 0)

    # Hard floor: force a WK / enough bowlers only once the draft is truly running out of room
    if wk == 0 and picks_left <= 2:
        candidates = [p for p in pool if p["role"] == "wicket_keeper"]
        if candidates:
            return _weighted_pick(candidates)

    if bowls < 3 and picks_left <= (3 - bowls):
        candidates = [p for p in pool if p["role"] == "bowler"]
        if candidates:
            return _weighted_pick(candidates)

    # Otherwise: blend quality with how much the squad still needs that role,
    # then pick with weighted randomness among the best few rather than always #1.
    def need_factor(role: str) -> float:
        deficit = _ROLE_TARGETS.get(role, 2) - counts.get(role, 0)
        return 1.0 + max(0.0, deficit) * 0.12

    ranked = sorted(pool, key=lambda p: overall_rating(p) * need_factor(p["role"]), reverse=True)
    return _weighted_pick(ranked[:6])


def print_draft_pool(pool: list[dict], top_n: int = 30):
    """Pretty-print top N available players for the user to pick from."""
    print(f"\n  {'#':<4} {'NAME':<24} {'TEAM':<6} {'ROLE':<14} {'RATING':>7}")
    print(f"  {'-'*60}")
    for i, p in enumerate(pool[:top_n], 1):
        rating = overall_rating(p)
        print(f"  {i:<4} {p['name']:<24} {p['team']:<6} {p['role']:<14} {rating:>7.3f}")


def print_xi(xi: list[dict], label: str):
    print(f"\n  {label}:")
    for i, p in enumerate(xi, 1):
        print(f"    {i:2}. {p['name']:<24} [{p['team']}] {p['role']}")
