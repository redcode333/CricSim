"""
single_player.py
Full IPL 2026 tournament mode for a single player.
- Pick your team from the 10 IPL franchises
- 70-match group stage: you play 14, rest auto-simulated
- Points table + NRR
- Top-4 playoff: Q1, Eliminator, Q2, Final
- Auto-saves after every user match (requires login)
"""
from __future__ import annotations
import os
import random
import dataclasses

from engine.tournament import (
    TEAMS, TEAM_STADIUM,
    generate_schedule, init_standings, update_standings,
    print_standings, get_top_4, build_playoff_bracket,
    MatchResult, TeamStanding,
)
from engine.ai_manager import (
    build_xi, build_bowling_order,
    run_match_silent, run_match_interactive, do_toss,
)
from engine.stadium import get_stadium, list_stadiums, print_stadium_menu, print_stadium_card


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _banner():
    print("=" * 62)
    print("        IPL 2026 TOURNAMENT  --  SINGLE PLAYER MODE")
    print("=" * 62)


def _pick_team() -> str:
    print("\n  SELECT YOUR TEAM:")
    for i, t in enumerate(TEAMS, 1):
        print(f"    {i:2}. {t}")
    while True:
        raw = input("\n  Enter number or team code: ").strip().upper()
        if raw in TEAMS:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(TEAMS):
            return TEAMS[int(raw) - 1]
        print("  Invalid. Try again.")


def _pick_speed() -> str:
    print("\n  Match speed (you can change live with 1/2/3/4 keys):")
    print("    1 = 2.0s/ball   2 = 1.0s/ball   3 = 0.4s/ball   4 = instant")
    while True:
        k = input("  Choose [1-4]: ").strip()
        if k in ("1", "2", "3", "4"):
            return k
        print("  Enter 1-4.")


_IPL_VENUE_IDS = {1, 2, 3, 4, 5, 6, 11, 12, 13, 14}


def _pick_stadium(home_team: str) -> dict:
    home_sid = TEAM_STADIUM.get(home_team, 1)
    ipl_venues = [s for s in list_stadiums() if s["id"] in _IPL_VENUE_IDS]
    print("\n  SELECT VENUE:")
    print(f"  {'#':<4} {'STADIUM':<45} {'CITY':<14} {'AVG':>4}")
    print(f"  {'─'*72}")
    for s in ipl_venues:
        home_tag = "  <- home" if s["id"] == home_sid else ""
        print(f"  {s['id']:<4} {s['name']:<45} {s['city']:<14} {s['avg_first_innings_t20']:>4}{home_tag}")
    valid = {str(s["id"]) for s in ipl_venues}
    while True:
        raw = input(f"\n  Enter venue number (default {home_sid}): ").strip()
        if raw == "":
            return get_stadium(home_sid)
        if raw in valid:
            return get_stadium(int(raw))
        print(f"  Invalid. Enter a number from the list, or press Enter for home ground.")


def _show_round_header(round_num: int, matches: list[dict], user_team: str):
    user_match = next((m for m in matches if user_team in (m["team1"], m["team2"])), None)
    opp = user_match["team2"] if user_match and user_match["team1"] == user_team else (
        user_match["team1"] if user_match else "?"
    )
    print(f"\n{'='*62}")
    print(f"  ROUND {round_num:>2}  |  Your match: {user_team} vs {opp}")
    print(f"{'='*62}")


def _play_ai_matches(matches: list[dict], user_team: str, standings: dict) -> list[MatchResult]:
    results = []
    for m in matches:
        if user_team in (m["team1"], m["team2"]):
            continue
        result = run_match_silent(m["team1"], m["team2"], m["match_num"])
        m["played"] = True
        m["result"] = result
        update_standings(standings, result)
        print(f"  {result.one_liner()}")
        results.append(result)
    return results


def _play_user_match(m: dict, user_team: str, speed_key: str, standings: dict) -> MatchResult:
    opp = m["team2"] if m["team1"] == user_team else m["team1"]

    _clear()
    _banner()
    print(f"\n  Match {m['match_num']}: {user_team} vs {opp}\n")
    stadium = _pick_stadium(home_team=m["team1"])

    _clear()
    _banner()
    print(f"\n  Match {m['match_num']}: {user_team} vs {opp}")
    print_stadium_card(stadium)

    user_bats_first = do_toss(user_team, opp, stadium)
    input("\n  Press Enter to start the match...")
    _clear()
    _banner()

    result = run_match_interactive(
        user_team=user_team,
        opp_team=opp,
        match_num=m["match_num"],
        stadium_id=stadium["id"],
        speed_key=speed_key,
        user_bats_first=user_bats_first,
    )
    m["played"] = True
    m["result"] = result
    update_standings(standings, result)
    return result


def _playoff_match(name: str, team1: str, team2: str, user_team: str, speed_key: str, match_num: int) -> str:
    is_user = user_team in (team1, team2)
    if is_user:
        sid = TEAM_STADIUM.get(team1, 1)
        result = run_match_interactive(
            user_team=user_team,
            opp_team=team2 if team1 == user_team else team1,
            match_num=match_num,
            stadium_id=sid,
            speed_key=speed_key,
        )
    else:
        result = run_match_silent(team1, team2, match_num)
        print(f"  {name}: {result.one_liner()}")

    return result.winner or random.choice([team1, team2])


# ---------------------------------------------------------------------------
# Serialisation helpers (schedule and standings ↔ plain dicts for JSON)
# ---------------------------------------------------------------------------

def _dump_schedule(schedule: list) -> list:
    result = []
    for rnd in schedule:
        srnd = []
        for m in rnd:
            sm = dict(m)
            if sm.get("result") is not None and not isinstance(sm["result"], dict):
                sm["result"] = dataclasses.asdict(sm["result"])
            srnd.append(sm)
        result.append(srnd)
    return result


def _load_schedule(data: list) -> list:
    result = []
    for rnd in data:
        drnd = []
        for m in rnd:
            dm = dict(m)
            if dm.get("result") and isinstance(dm["result"], dict):
                dm["result"] = MatchResult(**dm["result"])
            drnd.append(dm)
        result.append(drnd)
    return result


def _dump_standings(standings: dict) -> dict:
    return {t: dataclasses.asdict(s) for t, s in standings.items()}


def _load_standings(data: dict) -> dict:
    return {t: TeamStanding(**d) for t, d in data.items()}


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def _autosave(username, player_team, speed_key, schedule, standings, round_idx, playoff_state=None):
    from engine.save_manager import write_save
    my = standings[player_team]
    if playoff_state:
        summary = f"{player_team} | PLAYOFFS | {playoff_state.get('stage_label', 'in progress')}"
    else:
        summary = (
            f"{player_team} | Round {round_idx}/{len(schedule)} | "
            f"W{my.won} L{my.lost} | {my.points}pts"
        )
    state = {
        "player_team": player_team,
        "speed": speed_key,
        "round_idx": round_idx,
        "schedule": _dump_schedule(schedule),
        "standings": _dump_standings(standings),
        "_summary": summary,
    }
    if playoff_state:
        state["playoff_state"] = playoff_state
    write_save(username, "tournament", state)
    print("  [Game auto-saved]")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_tournament(username=None):
    _clear()
    _banner()

    # ----- Check for a saved game -----
    resume = None
    if username:
        from engine.save_manager import read_save, delete_save
        save = read_save(username, "tournament")
        if save:
            print(f"\n  SAVED GAME: {save.get('_summary', '...')}")
            print(f"  Saved: {save.get('_saved_at', '?')}")
            print("\n    1. Continue")
            print("    2. New game  (overwrites save)")
            print("    3. Back")
            while True:
                k = input("\n  Choose [1-3]: ").strip()
                if k == "1":
                    resume = save
                    break
                if k == "2":
                    delete_save(username, "tournament")
                    break
                if k == "3":
                    return
                print("  Enter 1, 2, or 3.")

    # ----- Restore or start fresh -----
    if resume:
        player_team  = resume["player_team"]
        speed_key    = resume["speed"]
        schedule     = _load_schedule(resume["schedule"])
        standings    = _load_standings(resume["standings"])
        start_round  = resume["round_idx"]        # 0-indexed; == len(schedule) means group done
        playoff_state = resume.get("playoff_state")
        print(f"\n  Resuming as {player_team}...")
        input("  Press Enter to continue...")
    else:
        player_team   = _pick_team()
        speed_key     = _pick_speed()
        print(f"\n  You are managing: {player_team}")
        print(f"  Tournament: {len(TEAMS)} teams, 70 group-stage matches, top-4 playoffs.\n")
        input("  Press Enter to begin the IPL 2026...")
        standings     = init_standings(TEAMS)
        schedule      = generate_schedule(TEAMS)
        start_round   = 0
        playoff_state = None

    # ------------------------------------------------------------------
    # Group Stage (skipped entirely when resuming directly into playoffs)
    # ------------------------------------------------------------------
    if playoff_state is None:
        for rnd_idx in range(start_round, len(schedule)):
            round_matches = schedule[rnd_idx]
            round_num     = rnd_idx + 1
            _clear()
            _banner()
            _show_round_header(round_num, round_matches, player_team)

            _play_ai_matches(round_matches, player_team, standings)

            user_match = next(
                (m for m in round_matches if player_team in (m["team1"], m["team2"])), None
            )
            if user_match:
                result = _play_user_match(user_match, player_team, speed_key, standings)
                opp = user_match["team2"] if user_match["team1"] == player_team else user_match["team1"]
                if result.winner == player_team:
                    print(f"\n  RESULT: {player_team} won vs {opp} by {result.margin_str}!")
                elif result.winner:
                    print(f"\n  RESULT: {opp} won by {result.margin_str}. Better luck next match.")
                else:
                    print(f"\n  RESULT: Match tied!")

            if username:
                _autosave(username, player_team, speed_key, schedule, standings, rnd_idx + 1)

            print_standings(standings, highlight=player_team)
            input("  Press Enter for next round...")

        # Group Stage Summary
        _clear()
        _banner()
        print("\n  GROUP STAGE COMPLETE")
        print_standings(standings, highlight=player_team)

        top4 = get_top_4(standings)
        print(f"  Qualifiers: {', '.join(top4)}")

        if player_team not in top4:
            print(f"\n  {player_team} did not qualify for the playoffs. Season over.")
            if username:
                from engine.save_manager import delete_save
                delete_save(username, "tournament")
            input("\n  Press Enter to return to main menu...")
            return

        print(f"\n  {player_team} qualified! Position: {top4.index(player_team) + 1}")
        input("\n  Press Enter to start the playoffs...")

        bracket          = build_playoff_bracket(top4)
        start_playoff_idx = 0
        match_num        = 71
    else:
        # Resuming into playoffs
        top4              = playoff_state["top4"]
        bracket           = playoff_state["bracket"]
        start_playoff_idx = playoff_state["next_playoff_idx"]
        match_num         = playoff_state["match_num"]

    # ------------------------------------------------------------------
    # Playoffs
    # ------------------------------------------------------------------
    _clear()
    _banner()
    print("\n  PLAYOFFS")

    for idx in range(start_playoff_idx, 4):
        name = bracket[idx]["name"]
        t1   = bracket[idx]["team1"]
        t2   = bracket[idx]["team2"]

        print(f"\n  --- {name}: {t1} vs {t2} ---")
        winner           = _playoff_match(name, t1, t2, player_team, speed_key, match_num)
        bracket[idx]["winner"] = winner
        loser            = t2 if winner == t1 else t1
        match_num       += 1

        # Wire up dependent bracket slots
        if idx == 0:
            bracket[2]["team1"] = loser      # Q2: Q1 loser
        elif idx == 1:
            bracket[2]["team2"] = winner     # Q2: Eliminator winner
        elif idx == 2:
            bracket[3]["team1"] = bracket[0]["winner"]
            bracket[3]["team2"] = winner

        # Auto-save after each playoff match except the Final
        if username and idx < 3:
            _autosave(
                username, player_team, speed_key, schedule, standings,
                round_idx=len(schedule),
                playoff_state={
                    "top4": top4,
                    "bracket": bracket,
                    "next_playoff_idx": idx + 1,
                    "match_num": match_num,
                    "stage_label": bracket[idx + 1]["name"] if idx + 1 < 4 else "Final",
                },
            )

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------
    champion = bracket[3]["winner"]
    _clear()
    _banner()
    print(f"\n  {'*'*50}")
    print(f"  IPL 2026 CHAMPION: {champion}")
    print(f"  {'*'*50}\n")
    if champion == player_team:
        print("  Congratulations! You won the IPL 2026!")
    else:
        print(f"  {player_team} finished the playoffs but {champion} lifted the trophy.")

    if username:
        from engine.save_manager import delete_save
        delete_save(username, "tournament")

    input("\n  Press Enter to return to main menu...")
