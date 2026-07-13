"""
ai_manager.py
AI team building and silent/interactive match runner.
"""
from __future__ import annotations
import random
import time
from typing import Optional, Callable

from engine.loader import get_team
from engine.stadium import get_stadium
from engine.simulator import simulate_innings
from engine.controls import SpeedControl
from engine.tournament import MatchResult, TEAM_STADIUM


class InvalidXI(ValueError):
    """Raised when a user-supplied playing XI is malformed."""


# ---------------------------------------------------------------------------
# XI / bowling order builders
# ---------------------------------------------------------------------------

_ROLE_ORDER = {"wicket_keeper": 0, "batter": 1, "all rounder": 2, "bowler": 3}


MAX_OVERSEAS = 4


def _player_score(p: dict) -> float:
    s = p["skills"]
    b = p["bowling"]
    return (
        s["bat_control"] * 0.30 + s["bat_power"] * 0.20
        + b["wicket_threat"] * 0.30 + b["economy_skill"] * 0.20
    )


def _is_overseas(p: dict) -> bool:
    return p.get("nationality", "IND") != "IND"


def build_xi(squad: list[dict]) -> list[dict]:
    """Build best playing XI from a full squad. Enforces max 4 overseas
    players and at least 1 wicket-keeper — the same rules a real XI needs."""
    ordered = sorted(squad, key=lambda p: (_ROLE_ORDER.get(p["role"], 4), -_player_score(p)))
    xi = list(ordered[:11])

    # Cap wicket-keepers at 1 — a real XI never fields more than one, but
    # sorting keepers ahead of every other role can let several strong ones
    # dominate the initial top-11 slice, crowding out bowlers/all-rounders.
    keepers_in = sorted(
        [p for p in xi if p["role"] == "wicket_keeper"], key=_player_score, reverse=True,
    )
    if len(keepers_in) > 1:
        excess = keepers_in[1:]
        xi_ids = {p["id"] for p in xi}
        replacements = sorted(
            [p for p in ordered[11:] if p["id"] not in xi_ids],
            key=_player_score, reverse=True,
        )
        for i, out_player in enumerate(excess):
            if i < len(replacements):
                xi.remove(out_player)
                xi.append(replacements[i])

    # Guarantee at least 3 genuine bowlers
    bowlers_in = [p for p in xi if p["bowling"]["wicket_threat"] > 0.25]
    if len(bowlers_in) < 3:
        extras = sorted(
            [p for p in ordered[11:] if p["bowling"]["wicket_threat"] > 0.25],
            key=lambda p: -p["bowling"]["wicket_threat"],
        )
        weakest = sorted(
            [p for p in xi if p["bowling"]["wicket_threat"] <= 0.25 and p["role"] == "batter"],
            key=_player_score,
        )
        for i in range(min(3 - len(bowlers_in), len(extras), len(weakest))):
            xi.remove(weakest[i])
            xi.append(extras[i])

    xi_ids = {p["id"] for p in xi}

    # Guarantee at least 1 wicket-keeper
    if not any(p["role"] == "wicket_keeper" for p in xi):
        wk_candidates = sorted(
            [p for p in squad if p["role"] == "wicket_keeper" and p["id"] not in xi_ids],
            key=_player_score, reverse=True,
        )
        removable = sorted(
            [p for p in xi if p["role"] in ("batter", "all rounder")],
            key=_player_score,
        )
        if wk_candidates and removable:
            xi.remove(removable[0])
            xi.append(wk_candidates[0])
            xi_ids = {p["id"] for p in xi}

    # Enforce max 4 overseas players — never at the cost of the only keeper
    # (an overseas keeper who's simply the weakest-scoring overseas player
    # would otherwise get bumped for a batter, leaving the XI with none).
    overseas_in_xi = [p for p in xi if _is_overseas(p)]
    if len(overseas_in_xi) > MAX_OVERSEAS:
        excess = len(overseas_in_xi) - MAX_OVERSEAS
        weakest_overseas = sorted(
            [p for p in overseas_in_xi if p["role"] != "wicket_keeper"], key=_player_score,
        )[:excess]
        indian_candidates = sorted(
            [p for p in squad if not _is_overseas(p) and p["id"] not in xi_ids],
            key=_player_score, reverse=True,
        )
        for i, out_player in enumerate(weakest_overseas):
            if i < len(indian_candidates):
                xi.remove(out_player)
                xi.append(indian_candidates[i])

    xi.sort(key=lambda p: (_ROLE_ORDER.get(p["role"], 4), -_player_score(p)))
    return xi[:11]


def _bowl_score(p: dict) -> float:
    b = p["bowling"]
    return b["wicket_threat"] * 0.45 + b["economy_skill"] * 0.35 + b["death_skill"] * 0.20


def build_bowling_order(xi: list[dict]) -> list[dict]:
    """Pick and rank bowlers from XI. A 20-over innings needs at least 5
    distinct bowlers to stay within the 4-overs-per-bowler cap; with exactly
    5, uneven over-distribution can still force the same bowler into
    back-to-back overs late in the innings, so guarantee 6 (5 bowlers can
    cover at most 19 overs before a 6th is mathematically required for the
    20th over's pick, so 6 makes a same-bowler-twice-in-a-row impossible)."""
    candidates = [
        p for p in xi
        if p["bowling"]["wicket_threat"] > 0.1 or p["role"] in ("bowler", "all rounder")
    ]
    if len(candidates) < 6:
        have = {p["id"] for p in candidates}
        rest = sorted((p for p in xi if p["id"] not in have), key=lambda p: -_bowl_score(p))
        candidates += rest[: 6 - len(candidates)]

    candidates.sort(key=lambda p: -_bowl_score(p))
    return candidates[:7]


def resolve_xi(team_code: str, user_team: str, user_xi_ids: Optional[list[str]]) -> list[dict]:
    """Build the playing XI for team_code. If team_code is the user's own team
    and they supplied a hand-picked XI, use exactly that; otherwise auto-build."""
    squad = get_team(team_code)
    if team_code != user_team or not user_xi_ids:
        return build_xi(squad)
    if len(user_xi_ids) != 11:
        raise InvalidXI("Playing XI must have exactly 11 players.")
    by_id = {p["id"]: p for p in squad}
    xi = []
    for pid in user_xi_ids:
        if pid not in by_id:
            raise InvalidXI(f"Player {pid} is not in the {team_code} squad.")
        xi.append(by_id[pid])
    return xi


# ---------------------------------------------------------------------------
# AI XI suggestion (pitch + opponent matchup aware)
# ---------------------------------------------------------------------------

def suggest_xi(squad: list[dict], stadium: dict, opponent_squad: list[dict]) -> tuple[list[str], dict[str, str], str]:
    """Suggest a playing XI for `squad`, biased by the stadium's pace/spin
    conditions and the opponent's likely bowling attack. Returns
    (suggested_ids, {id: short_reason}, matchup_note)."""
    r = stadium["ratings"]
    pace_adv = r["pace_advantage"] / 100
    spin_adv = r["spin_advantage"] / 100

    opp_xi = build_xi(opponent_squad)
    opp_bowlers = build_bowling_order(opp_xi)
    opp_pace = sum(1 for b in opp_bowlers if b["bowling"]["type"] == "pace")
    opp_spin = len(opp_bowlers) - opp_pace

    def pitch_score(p: dict) -> float:
        s = p["skills"]
        bonus = s.get("vs_pace", 0.5) * pace_adv + s.get("vs_spin", 0.5) * spin_adv
        bowl_bonus = 0.0
        if p["bowling"]["wicket_threat"] > 0.1:
            favours_pace = pace_adv >= spin_adv
            bowl_bonus = 0.15 if (p["bowling"]["type"] == "pace") == favours_pace else 0.0
        return _player_score(p) + bonus * 0.20 + bowl_bonus

    ordered = sorted(squad, key=lambda p: (_ROLE_ORDER.get(p["role"], 4), -pitch_score(p)))
    xi = list(ordered[:11])

    bowlers_in = [p for p in xi if p["bowling"]["wicket_threat"] > 0.25]
    if len(bowlers_in) < 3:
        extras = sorted(
            [p for p in ordered[11:] if p["bowling"]["wicket_threat"] > 0.25],
            key=lambda p: -p["bowling"]["wicket_threat"],
        )
        weakest = sorted(
            [p for p in xi if p["bowling"]["wicket_threat"] <= 0.25 and p["role"] == "batter"],
            key=pitch_score,
        )
        for i in range(min(3 - len(bowlers_in), len(extras), len(weakest))):
            xi.remove(weakest[i])
            xi.append(extras[i])

    xi_ids = {p["id"] for p in xi}
    if not any(p["role"] == "wicket_keeper" for p in xi):
        wk_candidates = sorted(
            [p for p in squad if p["role"] == "wicket_keeper" and p["id"] not in xi_ids],
            key=pitch_score, reverse=True,
        )
        removable = sorted(
            [p for p in xi if p["role"] in ("batter", "all rounder")],
            key=pitch_score,
        )
        if wk_candidates and removable:
            xi.remove(removable[0])
            xi.append(wk_candidates[0])
            xi_ids = {p["id"] for p in xi}

    overseas_in_xi = [p for p in xi if _is_overseas(p)]
    if len(overseas_in_xi) > MAX_OVERSEAS:
        excess = len(overseas_in_xi) - MAX_OVERSEAS
        weakest_overseas = sorted(overseas_in_xi, key=pitch_score)[:excess]
        indian_candidates = sorted(
            [p for p in squad if not _is_overseas(p) and p["id"] not in xi_ids],
            key=pitch_score, reverse=True,
        )
        for i, out_player in enumerate(weakest_overseas):
            if i < len(indian_candidates):
                xi.remove(out_player)
                xi.append(indian_candidates[i])

    xi.sort(key=lambda p: (_ROLE_ORDER.get(p["role"], 4), -pitch_score(p)))
    xi = xi[:11]

    favoured = "pace" if pace_adv >= spin_adv else "spin"
    reasons: dict[str, str] = {}
    for p in xi:
        s = p["skills"]
        if p["bowling"]["wicket_threat"] > 0.25:
            if (p["bowling"]["type"] == "pace") == (favoured == "pace"):
                reasons[p["id"]] = f"{p['bowling']['type'].capitalize()} bowler — suits this pitch"
            else:
                reasons[p["id"]] = f"{p['bowling']['type'].capitalize()} bowling option"
        elif s.get("vs_pace", 0.5) >= s.get("vs_spin", 0.5) and favoured == "pace":
            reasons[p["id"]] = f"Strong vs pace ({s.get('vs_pace', 0.5):.2f}) — suits this pitch"
        elif s.get("vs_spin", 0.5) > s.get("vs_pace", 0.5) and favoured == "spin":
            reasons[p["id"]] = f"Strong vs spin ({s.get('vs_spin', 0.5):.2f}) — suits this pitch"
        else:
            reasons[p["id"]] = "Balanced top-order/all-round pick"

    pace_pct = round(opp_pace / len(opp_bowlers) * 100) if opp_bowlers else 0
    matchup_note = (
        f"{stadium['name']} favours {favoured} "
        f"({r['pace_advantage'] if favoured == 'pace' else r['spin_advantage']}/100) — "
        f"the opponent's likely attack is {opp_pace} pace / {opp_spin} spin bowlers "
        f"({pace_pct}% pace), so {'spin survival' if opp_spin >= opp_pace else 'facing the new ball'} "
        f"in this XI matters most."
    )

    return [p["id"] for p in xi], reasons, matchup_note


# ---------------------------------------------------------------------------
# Match runners
# ---------------------------------------------------------------------------

def _overs_float(state) -> float:
    return round(state.legal_balls / 6, 2)


def _resolve_match(batting_first: str, bowling_first: str, inn1, inn2) -> tuple[Optional[str], str]:
    """Return (winner_team_code, margin_str)."""
    if inn2.result_note == "target reached":
        w = bowling_first
        ww = 10 - inn2.wickets
        return w, f"{ww} wicket{'s' if ww != 1 else ''}"
    elif inn2.runs < inn1.runs:
        diff = inn1.runs - inn2.runs
        return batting_first, f"{diff} run{'s' if diff != 1 else ''}"
    return None, "Tied"


def do_toss(user_label: str, opp_label: str, stadium: dict) -> bool:
    """
    Interactive toss ceremony.
    Returns True if the user's side bats first.
    user_label / opp_label are display names (e.g. "CSK" or "Your XI").
    """
    print(f"\n{'─'*62}")
    print(f"  TOSS  |  {user_label} vs {opp_label}")
    print(f"  {stadium['name']}, {stadium['city']}")
    print(f"  Pitch: {stadium['pitch_type']}  |  Avg 1st innings: {stadium['avg_first_innings_t20']}")
    print(f"{'─'*62}")

    while True:
        raw = input("\n  Your call — [H]eads or [T]ails: ").strip().lower()
        if raw in ("h", "heads"):
            user_call = "HEADS"
            break
        if raw in ("t", "tails"):
            user_call = "TAILS"
            break
        print("  Enter H or T.")

    print("\n  Tossing ", end="", flush=True)
    frames = ["H", "T"] * 5
    for f in frames:
        print(f"\b{f}", end="", flush=True)
        time.sleep(0.12)

    result = random.choice(["HEADS", "TAILS"])
    print(f"\r  The coin lands on... {result}!        ")

    if user_call == result:
        print(f"\n  You called {user_call} — YOU WIN THE TOSS!")
        print()
        while True:
            ch = input("    1. Bat first\n    2. Field first (bowl)\n  Choose [1/2]: ").strip()
            if ch == "1":
                print(f"\n  {user_label} will bat first.")
                return True
            if ch == "2":
                print(f"\n  {opp_label} will bat first.")
                return False
            print("  Enter 1 or 2.")
    else:
        bias     = stadium.get("toss_decision_bias", "bat first")
        opp_bats = (bias == "bat first")
        decision = "bat" if opp_bats else "bowl"
        user_bats = not opp_bats
        print(f"\n  You called {user_call} — it's {result}.  {opp_label} won the toss!")
        print(f"  Venue suggests: {bias}  →  {opp_label} chose to {decision} first.")
        if user_bats:
            print(f"  You will bat first.")
        else:
            print(f"  You will field (bowl) first.")
        return user_bats


def run_match_silent(
    team1: str,
    team2: str,
    match_num: int = 0,
    stadium_id: Optional[int] = None,
):
    """Simulate a full match with no output.
    Returns (MatchResult, inn1, inn1_batting_team, inn2, inn2_batting_team) —
    the two InningsState objects (with which team batted in each) are included
    so callers can accumulate season-long per-player stats instead of only
    the team-level summary in MatchResult."""
    sid = stadium_id if stadium_id is not None else TEAM_STADIUM.get(team1, 1)
    stadium = get_stadium(sid)

    xi1 = build_xi(get_team(team1))
    xi2 = build_xi(get_team(team2))
    bowl1 = build_bowling_order(xi1)
    bowl2 = build_bowling_order(xi2)

    if random.random() < 0.5:
        bat_xi, bat_bowl, bat_team = xi1, bowl2, team1
        field_xi, field_bowl, field_team = xi2, bowl1, team2
    else:
        bat_xi, bat_bowl, bat_team = xi2, bowl1, team2
        field_xi, field_bowl, field_team = xi1, bowl2, team1

    inn1 = simulate_innings(bat_xi, field_xi, bat_bowl, target=None, verbose=False, sc=None, stadium=stadium)
    inn2 = simulate_innings(field_xi, bat_xi, field_bowl, target=inn1.runs + 1, verbose=False, sc=None, stadium=stadium)

    winner, margin = _resolve_match(bat_team, field_team, inn1, inn2)

    if bat_team == team1:
        result = MatchResult(
            match_num, team1, team2, winner,
            inn1.runs, inn1.wickets, _overs_float(inn1),
            inn2.runs, inn2.wickets, _overs_float(inn2),
            margin,
        )
    else:
        result = MatchResult(
            match_num, team1, team2, winner,
            inn2.runs, inn2.wickets, _overs_float(inn2),
            inn1.runs, inn1.wickets, _overs_float(inn1),
            margin,
        )
    return result, inn1, bat_team, inn2, field_team


def run_match_interactive(
    user_team: str,
    opp_team: str,
    match_num: int,
    stadium_id: Optional[int] = None,
    speed_key: str = "2",
    on_ball: Optional[Callable] = None,
    user_bats_first: Optional[bool] = None,
) -> MatchResult:
    """
    Run a match where the user watches their team.
    Returns MatchResult for standings.
    on_ball(commentary, score, over_str) is called every delivery (used by online server).
    """
    from output.scorecard import print_scorecard, print_match_result

    sid = stadium_id if stadium_id is not None else TEAM_STADIUM.get(user_team, 1)
    stadium = get_stadium(sid)

    user_xi   = build_xi(get_team(user_team))
    opp_xi    = build_xi(get_team(opp_team))
    user_bowl = build_bowling_order(user_xi)
    opp_bowl  = build_bowling_order(opp_xi)

    # Toss — use pre-resolved result if caller handled it interactively
    if user_bats_first is None:
        bats_first = random.choice([user_team, opp_team])
        if on_ball is None:
            print(f"\n  TOSS: {bats_first} won and elected to bat first.")
    else:
        bats_first = user_team if user_bats_first else opp_team

    if bats_first == user_team:
        bat_xi, bat_bowl, bat_team   = user_xi, opp_bowl, user_team
        field_xi, field_bowl, f_team = opp_xi, user_bowl, opp_team
    else:
        bat_xi, bat_bowl, bat_team   = opp_xi, user_bowl, opp_team
        field_xi, field_bowl, f_team = user_xi, opp_bowl, user_team

    interactive = on_ball is None

    if interactive:
        from engine.user_input import user_pick_bowler, user_pick_batsman
        user_bats_inn1 = (bats_first == user_team)
        inn1_bat_fn  = user_pick_batsman if user_bats_inn1  else None
        inn1_bowl_fn = user_pick_bowler  if not user_bats_inn1 else None
        inn2_bat_fn  = user_pick_batsman if not user_bats_inn1 else None
        inn2_bowl_fn = user_pick_bowler  if user_bats_inn1  else None
    else:
        inn1_bat_fn = inn1_bowl_fn = inn2_bat_fn = inn2_bowl_fn = None

    sc = SpeedControl(speed_key) if interactive else None

    inn1 = simulate_innings(
        bat_xi, field_xi, bat_bowl, target=None,
        verbose=interactive, sc=sc, stadium=stadium, on_ball=on_ball,
        pick_bowler_fn=inn1_bowl_fn, pick_batsman_fn=inn1_bat_fn,
    )
    if interactive:
        print_scorecard(inn1, bat_team)
        input(f"\n  {f_team} need {inn1.runs + 1} to win. Press Enter...")

    sc2 = SpeedControl(speed_key) if interactive else None
    inn2 = simulate_innings(
        field_xi, bat_xi, field_bowl, target=inn1.runs + 1,
        verbose=interactive, sc=sc2, stadium=stadium, on_ball=on_ball,
        pick_bowler_fn=inn2_bowl_fn, pick_batsman_fn=inn2_bat_fn,
    )
    if interactive:
        print_scorecard(inn2, f_team)

    winner, margin = _resolve_match(bat_team, f_team, inn1, inn2)

    if interactive:
        print_match_result(bat_team, inn1, f_team, inn2)

    if bat_team == user_team:
        return MatchResult(
            match_num, user_team, opp_team, winner,
            inn1.runs, inn1.wickets, _overs_float(inn1),
            inn2.runs, inn2.wickets, _overs_float(inn2),
            margin,
        )
    return MatchResult(
        match_num, user_team, opp_team, winner,
        inn2.runs, inn2.wickets, _overs_float(inn2),
        inn1.runs, inn1.wickets, _overs_float(inn1),
        margin,
    )
