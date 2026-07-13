"""
scorecard.py
Prints a formatted scorecard from a completed InningsState.
"""

from engine.match_state import InningsState


def print_scorecard(state: InningsState, team_name: str):
    print(f"\n{'='*62}")
    print(f"  SCORECARD -- {team_name}  |  {state.score_str()} ({state.over_str} ov)")
    print(f"{'='*62}")

    # Batting
    print(f"\n  {'BATSMAN':<24} {'R':>4} {'B':>4} {'4s':>4} {'6s':>4} {'SR':>7}  STATUS")
    print(f"  {'-'*60}")
    for stat in state.bat_stats.values():
        status = stat.dismissal if stat.dismissed else ("batting" if not state.complete else "not out")
        print(
            f"  {stat.name:<24} {stat.runs:>4} {stat.balls:>4} "
            f"{stat.fours:>4} {stat.sixes:>4} {stat.strike_rate:>7.1f}  {status}"
        )

    extras = state.extras
    total_extras = sum(extras.values())
    print(f"\n  Extras: {total_extras}  (Wides: {extras['wides']}, No-balls: {extras['no_balls']})")
    print(f"\n  TOTAL: {state.runs}/{state.wickets}  ({state.over_str} overs)  CRR: {state.run_rate}")

    # Fall of wickets
    if state.fow:
        print(f"\n  FALL OF WICKETS")
        fow_parts = [f"{f.wicket_num}-{f.score} ({f.batsman_name}, {f.over}.{f.ball} ov)" for f in state.fow]
        print("  " + " | ".join(fow_parts))

    # Bowling
    print(f"\n  {'BOWLER':<24} {'O':>5} {'R':>5} {'W':>4} {'Wd':>4} {'NB':>4} {'Econ':>6}")
    print(f"  {'-'*56}")
    for stat in state.bowl_stats.values():
        print(
            f"  {stat.name:<24} {stat.overs_str:>5} {stat.runs:>5} "
            f"{stat.wickets:>4} {stat.wides:>4} {stat.no_balls:>4} {stat.economy:>6.2f}"
        )

    # Partnerships
    if state.partnerships:
        print(f"\n  PARTNERSHIPS")
        for i, p in enumerate(state.partnerships, 1):
            print(f"  {i}. {p.bat1_name} & {p.bat2_name}: {p.runs} runs ({p.balls} balls)")

    print(f"\n{'='*62}\n")


def print_match_result(
    team1: str, innings1: InningsState,
    team2: str, innings2: InningsState,
):
    print(f"\n{'*'*62}")
    print(f"  MATCH RESULT")
    print(f"{'*'*62}")
    print(f"  {team1}: {innings1.score_str()} ({innings1.over_str} ov)")
    print(f"  {team2}: {innings2.score_str()} ({innings2.over_str} ov)")
    print()

    if innings2.result_note == "target reached":
        wickets_left = 10 - innings2.wickets
        print(f"  {team2} won by {wickets_left} wicket{'s' if wickets_left != 1 else ''}!")
    elif innings2.runs < innings1.runs:
        margin = innings1.runs - innings2.runs
        print(f"  {team1} won by {margin} run{'s' if margin != 1 else ''}!")
    else:
        print("  Match tied!")

    print(f"{'*'*62}\n")
