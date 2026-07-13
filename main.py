"""
main.py
Entry point for the AI Cricket Match Simulator — IPL 2026.

Modes:
  1. Single Player Tournament  — pick a team, play the full IPL season
  2. Duo Mode: vs AI (Draft)   — draft 11 players, play one match vs AI
  3. Duo Mode: Online          — create/join a room with a friend over the network
  4. Quick Match               — classic pick-teams-and-play (original mode)

Accounts:
  - Login / Register to unlock save & resume across all modes.
  - Guest mode plays normally but progress is never saved.
"""

import os
import sys
import io

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print("=" * 62)
    print("        AI CRICKET MATCH SIMULATOR  --  IPL 2026")
    print("=" * 62)


# ---------------------------------------------------------------------------
# Login / Register screen
# ---------------------------------------------------------------------------

def _getpass(prompt="  Password: ") -> str:
    try:
        import getpass
        return getpass.getpass(prompt)
    except Exception:
        return input(prompt)


def _do_login() -> str | None:
    from engine.auth import login, display_name
    print()
    for _ in range(3):
        u = input("  Username: ").strip()
        p = _getpass("  Password: ")
        ok, result = login(u, p)
        if ok:
            print(f"\n  Welcome back, {display_name(result)}!")
            input("  Press Enter to continue...")
            return result
        print(f"  {result}  (try again)\n")
    print("  Too many failed attempts.")
    input("  Press Enter to continue as Guest...")
    return None


def _do_register() -> str | None:
    from engine.auth import register
    print()
    while True:
        u  = input("  Choose a username (min 3 chars): ").strip()
        p  = _getpass("  Choose a password: ")
        p2 = _getpass("  Confirm password:  ")
        if p != p2:
            print("  Passwords don't match. Try again.\n")
            continue
        ok, result = register(u, p)
        if ok:
            print(f"\n  Account created! Welcome, {u}!")
            input("  Press Enter to continue...")
            return result
        print(f"  {result}\n")


def _login_screen() -> str | None:
    """Returns username key (str) if logged in, None for guest."""
    clear()
    banner()
    print("\n  WELCOME")
    print("    1. Login to existing account")
    print("    2. Create new account")
    print("    3. Continue as Guest  (saves disabled)")
    while True:
        k = input("\n  Choose [1-3]: ").strip()
        if k == "1":
            return _do_login()
        if k == "2":
            return _do_register()
        if k == "3":
            return None
        print("  Enter 1, 2, or 3.")


# ---------------------------------------------------------------------------
# Quick Match (original single-match mode)
# ---------------------------------------------------------------------------

def quick_match():
    from engine.loader import list_teams
    from engine.simulator import simulate_innings
    from engine.controls import SpeedControl
    from engine.stadium import print_stadium_menu, print_stadium_card, get_stadium, list_stadiums
    from output.scorecard import print_scorecard, print_match_result
    from engine.ai_manager import build_xi, build_bowling_order

    def pick_team(prompt, exclude=""):
        teams = [t for t in list_teams() if t != exclude]
        print(f"\n  Available teams: {', '.join(teams)}")
        while True:
            c = input(f"  {prompt}: ").strip().upper()
            if c in teams:
                return c
            print(f"  Invalid. Choose from: {', '.join(teams)}")

    def pick_speed():
        print("\n  Speed: 1=2.0s  2=1.0s  3=0.4s  4=Instant")
        while True:
            k = input("  Choose [1-4]: ").strip()
            if k in ("1", "2", "3", "4"):
                return k

    def pick_stadium():
        print_stadium_menu()
        ids = [str(s["id"]) for s in list_stadiums()]
        while True:
            c = input("\n  Enter stadium number: ").strip()
            if c in ids:
                return get_stadium(int(c))

    clear()
    banner()
    print("\n  QUICK MATCH")
    team1 = pick_team("Team 1 (batting first)")
    team2 = pick_team("Team 2", exclude=team1)

    from engine.loader import get_team
    xi1 = build_xi(get_team(team1))
    xi2 = build_xi(get_team(team2))
    bowl1 = build_bowling_order(xi1)
    bowl2 = build_bowling_order(xi2)

    stadium  = pick_stadium()
    print_stadium_card(stadium)
    speed    = pick_speed()

    print("\n  LIVE CONTROLS: 1/2/3/4 = speed | P = pause | Q = quit")
    input(f"\n  Press Enter to start: {team1} vs {team2} ...")
    clear()
    banner()

    sc1 = SpeedControl(speed)
    inn1 = simulate_innings(xi1, xi2, bowl2, target=None, verbose=True, sc=sc1, stadium=stadium)
    print_scorecard(inn1, team1)

    if not sc1.quit:
        target = inn1.runs + 1
        input(f"\n  {team2} need {target} to win. Press Enter ...")
        clear()
        banner()
        sc2 = SpeedControl(speed)
        inn2 = simulate_innings(xi2, xi1, bowl1, target=target, verbose=True, sc=sc2, stadium=stadium)
        print_scorecard(inn2, team2)
        print_match_result(team1, inn1, team2, inn2)

    input("\n  Press Enter to return to main menu...")


# ---------------------------------------------------------------------------
# Duo mode sub-menu
# ---------------------------------------------------------------------------

def duo_menu(username=None):
    clear()
    banner()
    print("\n  DUO MODE")
    print("    1. vs AI (Draft)    -- draft 11 players, play one match")
    print("    2. Online Multiplayer -- create/join a room with a friend")
    print("    3. Back")
    while True:
        c = input("\n  Choose [1-3]: ").strip()
        if c == "1":
            from modes.duo_ai import run_duo_ai
            run_duo_ai(username=username)
            return
        if c == "2":
            from modes.duo_online import run_duo_online
            run_duo_online()
            return
        if c == "3":
            return
        print("  Enter 1, 2, or 3.")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main():
    username = _login_screen()

    while True:
        clear()
        banner()

        # Build save hints for logged-in users
        t_hint = ""
        d_hint = ""
        if username:
            from engine.save_manager import save_hint
            from engine.auth import display_name
            t_s = save_hint(username, "tournament")
            d_s = save_hint(username, "duo_ai")
            if t_s:
                t_hint = f"\n       [SAVE: {t_s}]"
            if d_s:
                d_hint = f"\n       [SAVE: {d_s}]"
            acct_line = f"  Logged in as: {display_name(username)}"
        else:
            acct_line = "  Playing as Guest  (login to enable saves)"

        print(f"\n  MAIN MENU")
        print(f"  {'-'*40}")
        print(f"  {acct_line}")
        print(f"  {'-'*40}")
        print(f"    1. Single Player Tournament  (full IPL 2026 season){t_hint}")
        print(f"    2. Duo Mode                  (draft vs AI  |  online vs friend){d_hint}")
        print(f"    3. Quick Match               (pick teams, play now)")
        print(f"    4. Quit")
        choice = input("\n  Choose [1-4]: ").strip()

        if choice == "1":
            from modes.single_player import run_tournament
            run_tournament(username=username)
        elif choice == "2":
            duo_menu(username=username)
        elif choice == "3":
            quick_match()
        elif choice == "4":
            print("\n  Goodbye!\n")
            break
        else:
            print("  Enter 1, 2, 3, or 4.")


if __name__ == "__main__":
    main()
