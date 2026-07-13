"""
duo_online.py
Terminal client for online duo mode.

Usage (from cricket_sim directory):
  python -m modes.duo_online

Room creator picks the series format (1-off / 3-match / 5-match).
The joiner inherits the creator's choice.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    print("  ERROR: 'websockets' package not installed. Run: pip install websockets")
    sys.exit(1)


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _banner(subtitle="ONLINE DUO MODE"):
    print("=" * 62)
    print(f"        AI CRICKET SIM  --  {subtitle}")
    print("=" * 62)


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def _pick_series_format() -> dict:
    print("\n  SELECT SERIES FORMAT:")
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


# ---------------------------------------------------------------------------
# Draft display helpers
# ---------------------------------------------------------------------------

def _show_draft_state(msg: dict):
    _clear()
    _banner("DRAFT PHASE")
    round_n   = msg.get("round", "?")
    your_turn = msg.get("your_turn", False)
    fmt_label = msg.get("series_label", "")

    print(f"\n  {fmt_label}  |  Round {round_n}/11  |  {'YOUR PICK' if your_turn else 'Waiting for opponent...'}")

    your_xi = msg.get("your_xi", [])
    opp_xi  = msg.get("opp_xi", [])
    print(f"\n  Your XI ({len(your_xi)}/11):")
    for p in your_xi:
        print(f"    {p['name']:<24} [{p['team']}] {p['role']}")

    print(f"\n  Opponent XI ({len(opp_xi)}/11):")
    for p in opp_xi:
        print(f"    {p['name']:<24} [{p['team']}] {p['role']}")

    pool = msg.get("pool", [])
    print(f"\n  Available players (top {len(pool)} shown):")
    print(f"  {'#':<4} {'NAME':<24} {'TEAM':<6} {'ROLE':<14} {'RATING':>7}")
    print(f"  {'-'*60}")
    for i, p in enumerate(pool, 1):
        print(f"  {i:<4} {p['name']:<24} {p['team']:<6} {p['role']:<14} {p.get('rating', 0):>7.3f}")


def _pick_from_pool(pool: list[dict]) -> str:
    while True:
        raw = input(f"\n  Enter pick number (1-{min(30, len(pool))}): ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(pool):
                return pool[idx]["id"]
        print("  Invalid. Try again.")


# ---------------------------------------------------------------------------
# Async client loop
# ---------------------------------------------------------------------------

async def _client(
    host: str,
    port: int,
    player_name: str,
    action: str,
    code: str = "",
    series_fmt: dict | None = None,
):
    uri = f"ws://{host}:{port}/ws"

    async with websockets.connect(uri) as ws:
        if action == "create":
            await ws.send(json.dumps({
                "type": "create",
                "player": player_name,
                "series_total": series_fmt["total"],
                "series_to_win": series_fmt["to_win"],
                "series_label": series_fmt["label"],
            }))
        else:
            await ws.send(json.dumps({"type": "join", "player": player_name, "code": code}))

        current_pool: list[dict] = []
        my_wins = 0
        opp_wins = 0

        async for raw in ws:
            msg = json.loads(raw)
            mtype = msg.get("type")

            if mtype == "room_created":
                _clear()
                _banner("ONLINE DUO MODE")
                fmt_label = msg.get("series_label", "")
                print(f"\n  Room created! Format: {fmt_label}")
                print(f"\n  Share this code with your opponent:")
                print(f"\n      >>> {msg['code']} <<<\n")
                print("  Waiting for opponent to join...")

            elif mtype == "room_joined":
                _clear()
                _banner("ONLINE DUO MODE")
                fmt_label = msg.get("series_label", "")
                print(f"\n  Joined room {msg['code']}. Format: {fmt_label}")
                print(f"  Opponent: {msg['opponent']}")
                print("  Waiting for draft to begin...")

            elif mtype == "player_joined":
                print(f"\n  Opponent joined: {msg['opponent']}")
                print("  Draft starting...")
                await asyncio.sleep(1)

            elif mtype == "draft_state":
                current_pool = msg.get("pool", [])
                _show_draft_state(msg)
                if msg.get("your_turn"):
                    player_id = _pick_from_pool(current_pool)
                    await ws.send(json.dumps({"type": "pick", "player_id": player_id}))

            elif mtype == "pick_ack":
                p = msg["picked"]
                who = "You" if msg["by"] == "you" else "Opponent"
                print(f"\n  {who} drafted: {p['name']} ({p['team']}, {p['role']})")

            elif mtype == "draft_done":
                _clear()
                _banner("DRAFT COMPLETE")
                fmt_label = msg.get("series_label", "")
                print(f"\n  Format: {fmt_label}")
                print("\n  YOUR XI:")
                for p in msg.get("your_xi", []):
                    print(f"    {p['name']:<24} [{p['team']}] {p['role']}")
                print("\n  OPPONENT'S XI:")
                for p in msg.get("opp_xi", []):
                    print(f"    {p['name']:<24} [{p['team']}] {p['role']}")
                print("\n  Series starting in 3 seconds...")
                await asyncio.sleep(3)

            elif mtype == "match_start":
                _clear()
                match_n = msg.get("match_num", 1)
                total   = msg.get("total", 1)
                fmt_label = msg.get("series_label", "")
                header = fmt_label if total == 1 else f"{fmt_label}  |  Match {match_n}/{total}"
                _banner(header)
                print(f"\n  Series score: You {my_wins}  --  Opp {opp_wins}")

            elif mtype == "innings_start":
                inn     = msg["innings"]
                batting = msg["batting"]
                print(f"\n{'='*62}")
                print(f"  Innings {inn} | {batting} batting")
                print(f"{'='*62}")

            elif mtype == "ball":
                print(f"  {msg['commentary']}")
                print(f"         Score: {msg['score']}  ({msg['over']} ov)")

            elif mtype == "innings_end":
                print(f"\n  End of innings {msg['innings']}: {msg['score']}")
                if msg["innings"] == 1:
                    print(f"  Target: {msg['target']}")
                print()

            elif mtype == "match_end":
                print(f"\n  {msg['result']}")

            elif mtype == "series_state":
                my_wins  = msg.get("your_wins", 0)
                opp_wins = msg.get("opp_wins", 0)
                to_win   = msg.get("to_win", 1)
                remaining = msg.get("remaining", 0)
                print(f"\n  Series: You {my_wins}  --  Opponent {opp_wins}  (first to {to_win})")
                if remaining > 0 and msg.get("series_over") is not True:
                    print(f"  {remaining} match{'es' if remaining > 1 else ''} remaining...")
                    await asyncio.sleep(3)

            elif mtype == "series_end":
                _clear()
                _banner("SERIES RESULT")
                my_wins  = msg.get("your_wins", 0)
                opp_wins = msg.get("opp_wins", 0)
                series_winner = msg.get("series_winner", "")  # "you" | "opp" | "draw"
                print()
                if series_winner == "you":
                    print(f"  YOU WIN THE SERIES {my_wins}-{opp_wins}! Congratulations!")
                elif series_winner == "opp":
                    print(f"  Opponent wins the series {opp_wins}-{my_wins}. Better luck next time.")
                else:
                    print(f"  Series drawn {my_wins}-{opp_wins}!")
                input("\n  Press Enter to exit...")
                break

            elif mtype == "error":
                print(f"\n  SERVER ERROR: {msg['message']}")
                break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_duo_online():
    _clear()
    _banner("ONLINE DUO MODE")

    print("\n  SERVER SETTINGS")
    host     = input("  Server host [localhost]: ").strip() or "localhost"
    port_raw = input("  Server port [8765]: ").strip()
    port     = int(port_raw) if port_raw.isdigit() else 8765

    player_name = input("\n  Your name: ").strip() or "Player"

    print("\n  1. Create a room (you pick the format + get a code to share)")
    print("  2. Join a room   (enter the code your friend gave you)")
    while True:
        choice = input("  Choose [1/2]: ").strip()
        if choice in ("1", "2"):
            break

    series_fmt = None
    code = ""
    if choice == "1":
        series_fmt = _pick_series_format()
    else:
        code = input("  Enter room code: ").strip().upper()

    try:
        asyncio.run(_client(
            host, port, player_name,
            "create" if choice == "1" else "join",
            code, series_fmt,
        ))
    except ConnectionRefusedError:
        print(f"\n  Could not connect to {host}:{port}.")
        print("  Make sure the server is running: python -m server.server")
        input("\n  Press Enter to return to main menu...")
    except Exception as e:
        print(f"\n  Connection error: {e}")
        input("\n  Press Enter to return to main menu...")
