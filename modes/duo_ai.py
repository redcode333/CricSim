"""
duo_ai.py
Duo vs AI: draft 11 players each, then play a 1-off, 3-match, or 5-match series.
Auto-saves after every match (requires login).
"""
from __future__ import annotations
import os

from engine.draft import get_draft_pool, ai_pick, print_draft_pool, print_xi
from engine.ai_manager import build_bowling_order, do_toss
from engine.simulator import simulate_innings
from engine.controls import SpeedControl
from engine.stadium import get_stadium, list_stadiums, print_stadium_menu, print_stadium_card
from engine.user_input import user_pick_bowler, user_pick_batsman
from output.scorecard import print_scorecard, print_match_result


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _banner(sub="DRAFT vs AI"):
    print("=" * 62)
    print(f"        DUO MODE  --  {sub}")
    print("=" * 62)


# ---------------------------------------------------------------------------
# Setup pickers
# ---------------------------------------------------------------------------

def _pick_series_format() -> dict:
    print("\n  SELECT FORMAT:")
    print("    1.  1-off match       (single T20)")
    print("    2.  3-match series    (first to 2 wins)")
    print("    3.  5-match series    (first to 3 wins)")
    while True:
        k = input("  Choose [1-3]: ").strip()
        if k == "1":
            return {"total": 1, "to_win": 1, "label": "1-off T20"}
        if k == "2":
            return {"total": 3, "to_win": 2, "label": "T20 Series (Best of 3)"}
        if k == "3":
            return {"total": 5, "to_win": 3, "label": "T20 Series (Best of 5)"}
        print("  Enter 1, 2, or 3.")


def _pick_stadium() -> dict:
    print_stadium_menu()
    ids = [str(s["id"]) for s in list_stadiums()]
    while True:
        c = input("\n  Enter stadium number: ").strip()
        if c in ids:
            return get_stadium(int(c))
        print(f"  Invalid. Choose from: {', '.join(ids)}")


def _pick_speed() -> str:
    print("\n  Match speed:")
    print("    1 = 2.0s/ball   2 = 1.0s/ball   3 = 0.4s/ball   4 = instant")
    while True:
        k = input("  Choose [1-4]: ").strip()
        if k in ("1", "2", "3", "4"):
            return k
        print("  Enter 1-4.")


def _user_pick(pool: list[dict], user_xi: list[dict], round_num: int) -> dict:
    while True:
        _clear()
        _banner()
        print(f"\n  DRAFT — Round {round_num}/11  |  YOUR PICK  ({len(user_xi)}/11 drafted)")
        print_xi(user_xi, "Your XI so far")
        print(f"\n  Available players (top 30 — enter number to pick):")
        print_draft_pool(pool, top_n=30)
        raw = input("\n  Your pick #: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < min(30, len(pool)):
                return pool[idx]
        print("  Invalid.")


# ---------------------------------------------------------------------------
# Series score display
# ---------------------------------------------------------------------------

def _series_bar(user_w: int, ai_w: int, fmt: dict) -> str:
    return (
        f"  Series: YOU {user_w}  --  AI {ai_w}"
        f"  (first to {fmt['to_win']} wins)"
    )


# ---------------------------------------------------------------------------
# Single match runner — returns "user" | "ai" | "tie"
# ---------------------------------------------------------------------------

def _play_one_match(
    user_xi: list[dict],
    ai_xi:   list[dict],
    stadium: dict,
    speed_key: str,
    match_label: str,
) -> str:
    _clear()
    _banner(match_label)

    user_bowl = build_bowling_order(user_xi)
    ai_bowl   = build_bowling_order(ai_xi)

    user_bats = do_toss("Your XI", "AI's XI", stadium)
    if user_bats:
        bat_xi,   bat_bowl,   bat_label   = user_xi, ai_bowl,   "Your XI"
        field_xi, field_bowl, field_label = ai_xi,   user_bowl, "AI's XI"
    else:
        bat_xi,   bat_bowl,   bat_label   = ai_xi,   user_bowl, "AI's XI"
        field_xi, field_bowl, field_label = user_xi, ai_bowl,   "Your XI"

    # Wire user-control callbacks per innings
    if user_bats:
        inn1_bat_fn  = user_pick_batsman   # user bats inn1
        inn1_bowl_fn = None                # AI bowls inn1
        inn2_bat_fn  = None                # AI bats inn2
        inn2_bowl_fn = user_pick_bowler    # user bowls inn2
    else:
        inn1_bat_fn  = None                # AI bats inn1
        inn1_bowl_fn = user_pick_bowler    # user bowls inn1
        inn2_bat_fn  = user_pick_batsman   # user bats inn2
        inn2_bowl_fn = None                # AI bowls inn2

    input("\n  Press Enter to start innings 1...")

    _clear()
    _banner(match_label)
    sc1  = SpeedControl(speed_key)
    inn1 = simulate_innings(
        bat_xi, field_xi, bat_bowl, target=None,
        verbose=True, sc=sc1, stadium=stadium,
        pick_bowler_fn=inn1_bowl_fn, pick_batsman_fn=inn1_bat_fn,
    )
    print_scorecard(inn1, bat_label)
    target = inn1.runs + 1
    input(f"\n  {field_label} need {target}. Press Enter for innings 2...")

    _clear()
    _banner(match_label)
    sc2  = SpeedControl(speed_key)
    inn2 = simulate_innings(
        field_xi, bat_xi, field_bowl, target=target,
        verbose=True, sc=sc2, stadium=stadium,
        pick_bowler_fn=inn2_bowl_fn, pick_batsman_fn=inn2_bat_fn,
    )
    print_scorecard(inn2, field_label)

    if user_bats:
        print_match_result("Your XI", inn1, "AI's XI", inn2)
        if inn2.result_note == "target reached":
            winner = "ai"
        elif inn1.runs > inn2.runs:
            winner = "user"
        else:
            winner = "tie"
    else:
        print_match_result("AI's XI", inn1, "Your XI", inn2)
        if inn2.result_note == "target reached":
            winner = "user"
        elif inn1.runs > inn2.runs:
            winner = "ai"
        else:
            winner = "tie"

    return winner


# ---------------------------------------------------------------------------
# Series loop (shared by new game and resume)
# ---------------------------------------------------------------------------

def _run_series(
    username,
    user_xi: list[dict],
    ai_xi:   list[dict],
    fmt:     dict,
    stadium: dict,
    speed_key: str,
    user_wins: int,
    ai_wins:   int,
    start_match: int,
):
    from engine.save_manager import write_save, delete_save

    for match_num in range(start_match, fmt["total"] + 1):
        if user_wins >= fmt["to_win"] or ai_wins >= fmt["to_win"]:
            break

        label  = "1-off T20" if fmt["total"] == 1 else f"{fmt['label']}  |  Match {match_num}/{fmt['total']}"
        winner = _play_one_match(user_xi, ai_xi, stadium, speed_key, label)

        if winner == "user":
            user_wins += 1
            print("\n  YOU WIN THIS MATCH!")
        elif winner == "ai":
            ai_wins += 1
            print("\n  AI wins this match.")
        else:
            print("\n  Match tied — no series point awarded.")

        print(f"\n  {_series_bar(user_wins, ai_wins, fmt)}")

        series_done = user_wins >= fmt["to_win"] or ai_wins >= fmt["to_win"]

        if username and not series_done:
            summary = (
                f"{fmt['label']} | YOU {user_wins}–AI {ai_wins} | "
                f"Match {match_num + 1}/{fmt['total']} next"
            )
            write_save(username, "duo_ai", {
                "user_xi":        user_xi,
                "ai_xi":          ai_xi,
                "format":         fmt,
                "stadium_id":     stadium["id"],
                "speed":          speed_key,
                "user_wins":      user_wins,
                "ai_wins":        ai_wins,
                "next_match_num": match_num + 1,
                "_summary":       summary,
            })
            print("  [Game auto-saved]")

        if series_done:
            if user_wins >= fmt["to_win"]:
                print(f"\n  YOU WIN THE SERIES {user_wins}-{ai_wins}! Congratulations!")
            else:
                print(f"\n  AI wins the series {ai_wins}-{user_wins}. Better luck next time.")
            if username:
                delete_save(username, "duo_ai")
            break

        remaining = fmt["total"] - match_num
        u_need    = fmt["to_win"] - user_wins
        a_need    = fmt["to_win"] - ai_wins
        if u_need == a_need:
            print(f"  {remaining} match{'es' if remaining > 1 else ''} remaining — series level.")
        elif u_need < a_need:
            print(f"  You need {u_need} more win{'s' if u_need > 1 else ''} from {remaining} match{'es' if remaining > 1 else ''}.")
        else:
            print(f"  AI needs {a_need} more win{'s' if a_need > 1 else ''} from {remaining} match{'es' if remaining > 1 else ''}.")
        input("\n  Press Enter for next match...")
    else:
        # All matches played, nobody clinched (ties kept series level)
        if user_wins > ai_wins:
            print(f"\n  YOU WIN THE SERIES {user_wins}-{ai_wins}!")
        elif ai_wins > user_wins:
            print(f"\n  AI wins the series {ai_wins}-{user_wins}.")
        else:
            print(f"\n  Series drawn {user_wins}-{ai_wins}!")
        if username:
            delete_save(username, "duo_ai")

    input("\n  Press Enter to return to main menu...")


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def run_duo_ai(username=None):
    _clear()
    _banner()

    # ----- Check for a saved series -----
    if username:
        from engine.save_manager import read_save, delete_save
        save = read_save(username, "duo_ai")
        if save:
            print(f"\n  SAVED SERIES: {save.get('_summary', '...')}")
            print(f"  Saved: {save.get('_saved_at', '?')}")
            print("\n    1. Continue series")
            print("    2. New game  (overwrites save)")
            print("    3. Back")
            while True:
                k = input("\n  Choose [1-3]: ").strip()
                if k == "1":
                    # Restore and resume
                    user_xi   = save["user_xi"]
                    ai_xi     = save["ai_xi"]
                    fmt       = save["format"]
                    stadium   = get_stadium(save["stadium_id"])
                    speed_key = save["speed"]
                    user_wins = save["user_wins"]
                    ai_wins   = save["ai_wins"]
                    nxt       = save["next_match_num"]

                    _clear()
                    _banner()
                    print_xi(user_xi, "YOUR XI")
                    print_xi(ai_xi, "AI's XI")
                    print_stadium_card(stadium)
                    print(f"\n  {_series_bar(user_wins, ai_wins, fmt)}")
                    print(f"  Resuming at Match {nxt}/{fmt['total']}...")
                    input("  Press Enter to continue...")

                    _run_series(username, user_xi, ai_xi, fmt, stadium, speed_key,
                                user_wins, ai_wins, nxt)
                    return
                if k == "2":
                    delete_save(username, "duo_ai")
                    break
                if k == "3":
                    return
                print("  Enter 1, 2, or 3.")

    # ----- New game: draft -----
    print("\n  You will draft 11 players from the full IPL 2026 pool.")
    print("  Same XI plays all matches in the series.")
    print("  Draft order: You pick 1st in odd rounds, AI picks 1st in even rounds.")
    input("\n  Press Enter to start the draft...")

    pool    = get_draft_pool()
    user_xi: list[dict] = []
    ai_xi:   list[dict] = []

    for round_num in range(1, 12):
        order = ["user", "ai"] if round_num % 2 == 1 else ["ai", "user"]
        for turn in order:
            if turn == "user":
                picked = _user_pick(pool, user_xi, round_num)
                user_xi.append(picked)
                pool.remove(picked)
                print(f"  You drafted: {picked['name']} ({picked['team']}, {picked['role']})")
                input("  Press Enter to continue...")
            else:
                picked = ai_pick(pool, ai_xi)
                ai_xi.append(picked)
                pool.remove(picked)
                print(f"\n  AI drafted:  {picked['name']} ({picked['team']}, {picked['role']})")

    # Draft summary + series setup
    _clear()
    _banner()
    print_xi(user_xi, "YOUR XI")
    print_xi(ai_xi, "AI's XI")

    fmt       = _pick_series_format()
    stadium   = _pick_stadium()
    print_stadium_card(stadium)
    speed_key = _pick_speed()

    print(f"\n  Format: {fmt['label']}")
    input("  Press Enter to begin the series...")

    _run_series(username, user_xi, ai_xi, fmt, stadium, speed_key, 0, 0, 1)
