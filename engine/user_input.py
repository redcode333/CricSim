"""
user_input.py
AI-suggested, user-confirmed bowler and batsman selection.

Suggestion logic mirrors the MCP tool attributes:
  Bowling: economy_skill, wicket_threat, death_skill per phase
  Batting:  bat_control, bat_power, bat_aggression, consistency per situation
"""
from __future__ import annotations
from typing import Optional


# ---------------------------------------------------------------------------
# Bowler suggestion
# ---------------------------------------------------------------------------

def _overs_bowled(bowl_stats: dict, bid: str) -> int:
    return bowl_stats[bid].balls // 6 if bid in bowl_stats else 0


def _phase(over: int) -> str:
    if over < 6:
        return "powerplay"
    if over < 16:
        return "middle"
    return "death"


def _bowler_score(b: dict, phase: str) -> float:
    bw = b["bowling"]
    if phase == "powerplay":
        return bw["economy_skill"] * 0.50 + bw["wicket_threat"] * 0.50
    if phase == "middle":
        return bw["wicket_threat"] * 0.60 + bw["economy_skill"] * 0.40
    return bw["death_skill"] * 0.60 + bw["wicket_threat"] * 0.20 + bw["economy_skill"] * 0.20


def suggest_bowler(
    candidates: list[dict],
    bowl_stats: dict,
    over: int,
    last_id: Optional[str],
) -> tuple[dict, str]:
    """Return (best_bowler, reason_str) for the current over."""
    phase = _phase(over)
    eligible = [
        b for b in candidates
        if b["id"] != last_id and _overs_bowled(bowl_stats, b["id"]) < 4
    ]
    if not eligible:
        eligible = [b for b in candidates if _overs_bowled(bowl_stats, b["id"]) < 4]
    if not eligible:
        eligible = candidates

    ranked = sorted(eligible, key=lambda b: -_bowler_score(b, phase))
    best = ranked[0]
    quota_left = 4 - _overs_bowled(bowl_stats, best["id"])
    label = {
        "powerplay": "Powerplay specialist (economy + threat)",
        "middle":    "Middle-overs wicket-taker",
        "death":     "Death specialist",
    }[phase]
    reason = f"{label} — {quota_left} over{'s' if quota_left != 1 else ''} left in quota"
    return best, reason


def user_pick_bowler(
    candidates: list[dict],
    bowl_stats: dict,
    over: int,
    last_id: Optional[str],
) -> dict:
    """Interactive bowler-selection menu. Returns chosen bowler dict."""
    phase = _phase(over)
    suggested, reason = suggest_bowler(candidates, bowl_stats, over, last_id)

    def eligible(b):
        return b["id"] != last_id and _overs_bowled(bowl_stats, b["id"]) < 4

    display = sorted(candidates, key=lambda b: (0 if eligible(b) else 1, -_bowler_score(b, phase)))

    # If only one eligible bowler, skip the menu
    avail = [b for b in display if eligible(b)]
    if len(avail) <= 1 and avail:
        return avail[0]

    print(f"\n  ┌── OVER {over + 1} | SELECT BOWLER  [{phase.upper()}] " + "─" * 30)
    print(f"  │  AI suggest → {suggested['name']}  ({reason})")
    print(f"  ├" + "─" * 60)
    print(f"  │  {'#':<3} {'NAME':<22} {'OV':>4} {'ECO':>5} {'WKT':>5} {'DTH':>5}  STATUS")
    print(f"  ├" + "─" * 60)
    for i, b in enumerate(display, 1):
        ob  = _overs_bowled(bowl_stats, b["id"])
        bw  = b["bowling"]
        if b["id"] == last_id:
            status = "consecutive — skip"
        elif ob >= 4:
            status = "quota full"
        elif b["id"] == suggested["id"]:
            status = "<-- AI pick"
        else:
            status = ""
        print(
            f"  │  {i:<3} {b['name']:<22} {ob}/4 "
            f"{bw['economy_skill']:>5.2f} {bw['wicket_threat']:>5.2f} {bw['death_skill']:>5.2f}  {status}"
        )
    print(f"  └" + "─" * 60)

    while True:
        raw = input(f"  Pick [1-{len(display)}] or Enter for AI pick: ").strip()
        if raw == "":
            print(f"  → {suggested['name']} to bowl over {over + 1}.")
            return suggested
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(display):
                chosen = display[idx]
                if chosen["id"] == last_id:
                    print("  Can't bowl consecutive overs — pick someone else.")
                elif _overs_bowled(bowl_stats, chosen["id"]) >= 4:
                    print("  Quota full (4 overs) — pick someone else.")
                else:
                    print(f"  → {chosen['name']} to bowl over {over + 1}.")
                    return chosen
        print(f"  Enter a number 1–{len(display)} or press Enter.")


# ---------------------------------------------------------------------------
# Batsman suggestion
# ---------------------------------------------------------------------------

def _bat_score(b: dict, mode: str) -> float:
    s = b["skills"]
    m = b["mental"]
    if mode == "anchor":
        return s["bat_control"] * 0.45 + m["consistency"] * 0.30 + m["pressure_handling"] * 0.25
    if mode == "attack":
        return s["bat_power"] * 0.40 + s["bat_aggression"] * 0.35 + s["bat_control"] * 0.25
    return (
        s["bat_control"] * 0.35 + s["bat_power"] * 0.25 + s["bat_aggression"] * 0.15
        + m["consistency"] * 0.15 + m["pressure_handling"] * 0.10
    )


def suggest_batsman(remaining: list[dict], state) -> tuple[dict, str]:
    """Return (best_batsman, reason_str) for current match situation."""
    over       = state.current_over
    wickets    = state.wickets
    balls_left = state.balls_remaining

    if state.second_innings and state.runs_needed > 0 and state.run_rate > 0:
        rrr = state.required_run_rate
        crr = state.run_rate
        if rrr > crr + 3 or balls_left < 24:
            mode = "attack"
        elif wickets >= 5:
            mode = "anchor"
        else:
            mode = "balanced"
    else:
        if over >= 16 or (wickets <= 3 and over >= 10):
            mode = "attack"
        elif wickets >= 5:
            mode = "anchor"
        else:
            mode = "balanced"

    ranked = sorted(remaining, key=lambda b: -_bat_score(b, mode))
    best   = ranked[0]
    reasons = {
        "anchor":   "Stability needed — best bat_control + consistency",
        "attack":   "Need runs fast — power hitter recommended",
        "balanced": "Balanced situation — best all-round option",
    }
    return best, reasons[mode]


def user_pick_batsman(remaining: list[dict], state) -> dict:
    """Interactive next-batsman menu. Returns chosen player dict."""
    if len(remaining) == 1:
        return remaining[0]

    suggested, reason = suggest_batsman(remaining, state)

    print(f"\n  ┌── WICKET! {state.score_str()} ({state.over_str} ov) — NEXT BATSMAN " + "─" * 20)
    print(f"  │  AI suggest → {suggested['name']}  ({reason})")
    print(f"  ├" + "─" * 60)
    print(f"  │  {'#':<3} {'NAME':<22} {'ROLE':<14} {'CTL':>5} {'PWR':>5} {'AGG':>5} {'CON':>5}")
    print(f"  ├" + "─" * 60)
    for i, b in enumerate(remaining, 1):
        s    = b["skills"]
        m    = b["mental"]
        note = "  <-- AI pick" if b["id"] == suggested["id"] else ""
        print(
            f"  │  {i:<3} {b['name']:<22} {b['role']:<14} "
            f"{s['bat_control']:>5.2f} {s['bat_power']:>5.2f} "
            f"{s['bat_aggression']:>5.2f} {m['consistency']:>5.2f}{note}"
        )
    print(f"  └" + "─" * 60)

    while True:
        raw = input(f"  Pick [1-{len(remaining)}] or Enter for AI pick: ").strip()
        if raw == "":
            print(f"  → {suggested['name']} comes in.")
            return suggested
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(remaining):
                chosen = remaining[idx]
                print(f"  → {chosen['name']} comes in.")
                return chosen
        print(f"  Enter a number 1–{len(remaining)} or press Enter.")
