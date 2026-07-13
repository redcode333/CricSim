"""
simulator.py
Runs a complete T20 innings ball-by-ball using the probability engine.

The bowling order must be provided as a list of bowler player dicts.
Each bowler can bowl a maximum of 4 overs (configurable).
"""

from engine.match_state import InningsState
from engine.probability import ball_outcome
from engine.commentary import ball_commentary, over_summary
from engine.controls import SpeedControl, smart_sleep
from typing import Optional, Callable



MAX_BOWLER_OVERS = 4

# Kept for backwards compatibility (used by main.py speed picker)
SPEED_DELAYS = {
    "1x":      2.0,
    "2x":      1.0,
    "4x":      0.4,
    "instant": 0.0,
}


def _pick_bowler(
    bowling_order: list[dict],
    bowl_stats: dict,
    current_over: int,
    last_bowler_id: Optional[str],
) -> dict:
    """
    Pick the next bowler respecting:
    - Max 4 overs per bowler
    - Cannot bowl two consecutive overs
    """
    for bowler in bowling_order:
        bid = bowler["id"]
        if bid == last_bowler_id:
            continue
        overs_bowled = bowl_stats[bid].balls // 6 if bid in bowl_stats else 0
        if overs_bowled < MAX_BOWLER_OVERS:
            return bowler

    # Fallback: relax consecutive rule
    for bowler in bowling_order:
        bid = bowler["id"]
        overs_bowled = bowl_stats[bid].balls // 6 if bid in bowl_stats else 0
        if overs_bowled < MAX_BOWLER_OVERS:
            return bowler

    # All bowlers exhausted quota — reuse (edge case)
    return bowling_order[current_over % len(bowling_order)]


def simulate_innings(
    batting_xi: list[dict],
    bowling_xi: list[dict],
    bowling_order: list[dict],
    target: Optional[int] = None,
    verbose: bool = True,
    sc: Optional[SpeedControl] = None,
    stadium: Optional[dict] = None,
    on_ball: Optional[Callable[[str, str, str], None]] = None,
    pick_bowler_fn=None,
    pick_batsman_fn=None,
) -> InningsState:
    """
    Simulate a full T20 innings.

    Parameters
    ----------
    batting_xi    : 11 batsmen in batting order
    bowling_xi    : full squad of the fielding team (for reference)
    bowling_order : ordered list of bowlers to use (can repeat up to quota)
    target        : runs needed to win (2nd innings only)
    verbose       : if True, print ball-by-ball commentary
    sc            : SpeedControl instance for live speed/pause/quit control.
                    Pass None for instant silent simulation.
    stadium       : stadium dict from cricket_stadiums.json (optional)
    """
    state = InningsState(batting_xi, bowling_xi, target=target, pick_batsman_fn=pick_batsman_fn)
    second_innings = target is not None
    live = verbose and sc is not None

    last_bowler_id: Optional[str] = None
    current_bowler: Optional[dict] = None
    over_runs    = 0
    over_wickets = 0
    last_over_setup = -1   # tracks which over we've already set up a bowler for

    if verbose:
        label = "2nd Innings" if second_innings else "1st Innings"
        print(f"\n{'='*62}")
        print(f"  {label} | Batting: {batting_xi[0]['team']}")
        if target:
            print(f"  Target: {target}")
        print(f"{'='*62}")
        if live:
            print(f"\n{sc.status_bar()}\n")

    while not state.complete:
        # Honour quit request
        if live and sc.quit:
            break

        over = state.current_over

        # New over — pick bowler and print header (guard prevents re-triggering on wide/no-ball)
        if state.legal_balls % 6 == 0 and over != last_over_setup:
            if pick_bowler_fn:
                current_bowler = pick_bowler_fn(
                    bowling_order, state.bowl_stats, over, last_bowler_id
                )
            else:
                current_bowler = _pick_bowler(
                    bowling_order, state.bowl_stats, over, last_bowler_id
                )
            last_bowler_id = current_bowler["id"]
            last_over_setup = over
            over_runs    = 0
            over_wickets = 0

            if verbose:
                print(f"\n--- Over {over + 1} | {current_bowler['name']} to bowl ---")
                if live:
                    print(f"    {sc.status_bar()}")

        # Compute outcome
        outcome, _ = ball_outcome(
            batsman         = state.striker,
            bowler          = current_bowler,
            over            = over,
            runs_needed     = state.runs_needed,
            balls_remaining = state.balls_remaining,
            second_innings  = second_innings,
            stadium         = stadium,
        )

        striker_runs_before = state.bat_stats[state.striker["id"]].runs
        _striker_name = state.striker["name"]   # capture before apply (changes on wicket)
        _bowler_name  = current_bowler["name"]

        # Print commentary
        line     = ball_commentary(outcome, state.striker, current_bowler, striker_runs_before)
        over_ball = f"{over}.{state.ball_in_over - 1}"
        if verbose:
            print(f"  {over_ball}  {line}")

        legal_before = state.legal_balls

        # Apply outcome to match state
        state.apply_outcome(outcome, current_bowler)

        # Record to ball log (used by web API)
        state.ball_log.append({
            "over_str":    over_ball,
            "batsman":     _striker_name,
            "bowler":      _bowler_name,
            "outcome":     outcome,
            "commentary":  line.strip(),
            "runs":        state.runs,
            "wickets":     state.wickets,
            "crr":         state.run_rate,
            "runs_needed": state.runs_needed if second_innings else None,
            "rrr":         state.required_run_rate if second_innings else None,
        })

        # Track over stats
        if outcome not in ("Wd", "Nb"):
            if outcome == "W":
                over_wickets += 1
            elif outcome != "0":
                over_runs += int(outcome)

        if on_ball:
            on_ball(f"  {over_ball}  {line}", state.score_str(), state.over_str)

        # Print live score
        if verbose:
            score_line = f"         Score: {state.score_str()} | CRR: {state.run_rate}"
            if second_innings:
                score_line += (
                    f" | Need: {state.runs_needed} off "
                    f"{state.balls_remaining} balls (RRR: {state.required_run_rate})"
                )
            print(score_line, flush=True)

        # Speed-controlled delay (handles pause/quit/speed-change mid-match)
        if live:
            smart_sleep(sc)

        # End-of-over summary — only when a legal delivery just completed the over
        legal_ball_was_bowled = state.legal_balls > legal_before
        if legal_ball_was_bowled and state.legal_balls % 6 == 0 and not state.complete:
            if verbose:
                summary = over_summary(over, over_runs, over_wickets, current_bowler)
                print(f"\n  >> {summary}")

    if verbose:
        print(f"\n{'='*62}")
        if live and sc.quit:
            print(f"  INNINGS STOPPED — {state.score_str()} ({state.over_str} overs)")
        else:
            print(f"  INNINGS COMPLETE — {state.score_str()} ({state.over_str} overs)")
            print(f"  Reason: {state.result_note}")
        print(f"{'='*62}\n")

    return state
