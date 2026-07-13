"""
server.py
FastAPI WebSocket server for online duo mode.

Run:  python -m server.server [--port 8765]

Protocol (JSON messages):
  Server -> Client:
    room_created   {code, player, series_label}
    player_joined  {opponent}
    room_joined    {code, opponent, series_label}
    draft_state    {pool, your_xi, opp_xi, your_turn, round, series_label}
    pick_ack       {picked, by, round}
    draft_done     {your_xi, opp_xi, series_label}
    match_start    {match_num, total, series_label}
    innings_start  {innings, batting}
    ball           {commentary, score, over, innings}
    innings_end    {innings, score, target?}
    match_end      {result}
    series_state   {your_wins, opp_wins, to_win, remaining, series_over}
    series_end     {your_wins, opp_wins, series_winner}  -- "you"|"opp"|"draw"
    error          {message}

  Client -> Server:
    create  {player, series_total, series_to_win, series_label}
    join    {player, code}
    pick    {player_id}
"""
from __future__ import annotations

import asyncio
import json
import random
import string
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from engine.draft import get_draft_pool, overall_rating
from engine.ai_manager import build_bowling_order
from engine.simulator import simulate_innings
from engine.stadium import get_stadium

app = FastAPI()
rooms: dict[str, "Room"] = {}

_IPL_VENUES = [1, 2, 3, 4, 5, 6, 11, 12, 13, 14]


def _gen_code() -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code


class Room:
    def __init__(self, code: str, series_total: int, series_to_win: int, series_label: str):
        self.code          = code
        self.series_total  = series_total
        self.series_to_win = series_to_win
        self.series_label  = series_label

        self.players: list[str]     = []
        self.sockets: list[WebSocket] = []
        self.pool:    list[dict]    = []
        self.xi:      list[list[dict]] = [[], []]
        self.wins:    list[int]     = [0, 0]
        self.draft_turn:  int = 0
        self.draft_round: int = 1
        self.state: str = "waiting"

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send(self, idx: int, msg: dict):
        try:
            await self.sockets[idx].send_text(json.dumps(msg))
        except Exception:
            pass

    async def broadcast(self, msg: dict):
        for i in range(len(self.sockets)):
            await self.send(i, msg)

    # ------------------------------------------------------------------
    # Draft helpers
    # ------------------------------------------------------------------

    def _pool_summary(self, top: int = 30) -> list[dict]:
        return [
            {"id": p["id"], "name": p["name"], "team": p["team"],
             "role": p["role"], "rating": round(overall_rating(p), 3)}
            for p in self.pool[:top]
        ]

    def _xi_summary(self, xi: list[dict]) -> list[dict]:
        return [
            {"id": p["id"], "name": p["name"], "team": p["team"], "role": p["role"]}
            for p in xi
        ]

    async def send_draft_state(self):
        for idx in range(2):
            await self.send(idx, {
                "type":         "draft_state",
                "pool":         self._pool_summary(),
                "your_xi":      self._xi_summary(self.xi[idx]),
                "opp_xi":       self._xi_summary(self.xi[1 - idx]),
                "your_turn":    self.draft_turn == idx,
                "round":        self.draft_round,
                "series_label": self.series_label,
            })

    async def handle_pick(self, picker_idx: int, player_id: str):
        if self.draft_turn != picker_idx:
            await self.send(picker_idx, {"type": "error", "message": "Not your turn."})
            return

        player = next((p for p in self.pool if p["id"] == player_id), None)
        if player is None:
            await self.send(picker_idx, {"type": "error", "message": "Player not available."})
            return

        self.xi[picker_idx].append(player)
        self.pool.remove(player)

        for idx in range(2):
            await self.send(idx, {
                "type":   "pick_ack",
                "picked": {"name": player["name"], "team": player["team"], "role": player["role"]},
                "by":     "you" if idx == picker_idx else "opp",
                "round":  self.draft_round,
            })

        self.draft_turn = 1 - self.draft_turn
        picks_done = len(self.xi[0]) + len(self.xi[1])

        if picks_done >= 22:
            self.state = "playing"
            for idx in range(2):
                await self.send(idx, {
                    "type":         "draft_done",
                    "your_xi":      self._xi_summary(self.xi[idx]),
                    "opp_xi":       self._xi_summary(self.xi[1 - idx]),
                    "series_label": self.series_label,
                })
            await asyncio.sleep(2)
            await self.run_series()
        else:
            self.draft_round = picks_done // 2 + 1
            await self.send_draft_state()

    # ------------------------------------------------------------------
    # Match simulation
    # ------------------------------------------------------------------

    async def _stream_one_match(self, match_num: int) -> str | None:
        """Simulate and stream one match. Returns player name of winner, or None for tie."""
        stadium = get_stadium(random.choice(_IPL_VENUES))
        xi0, xi1 = self.xi[0], self.xi[1]
        bowl0 = build_bowling_order(xi0)
        bowl1 = build_bowling_order(xi1)

        if random.random() < 0.5:
            bat_xi, bat_bowl, bat_name   = xi0, bowl1, self.players[0]
            field_xi, field_bowl, f_name = xi1, bowl0, self.players[1]
        else:
            bat_xi, bat_bowl, bat_name   = xi1, bowl0, self.players[1]
            field_xi, field_bowl, f_name = xi0, bowl1, self.players[0]

        await self.broadcast({
            "type":         "match_start",
            "match_num":    match_num,
            "total":        self.series_total,
            "series_label": self.series_label,
        })
        await asyncio.sleep(1)

        # Collect balls silently
        balls_inn1: list[dict] = []
        balls_inn2: list[dict] = []

        def collect(store: list):
            def cb(commentary: str, score: str, over_str: str):
                store.append({"commentary": commentary, "score": score, "over": over_str})
            return cb

        inn1 = simulate_innings(bat_xi, field_xi, bat_bowl, target=None,
                                verbose=False, sc=None, stadium=stadium,
                                on_ball=collect(balls_inn1))
        inn2 = simulate_innings(field_xi, bat_xi, field_bowl, target=inn1.runs + 1,
                                verbose=False, sc=None, stadium=stadium,
                                on_ball=collect(balls_inn2))

        # Stream innings 1
        await self.broadcast({"type": "innings_start", "innings": 1, "batting": bat_name})
        for ball in balls_inn1:
            await self.broadcast({"type": "ball", "innings": 1, **ball})
            await asyncio.sleep(0.8)
        await self.broadcast({
            "type": "innings_end", "innings": 1,
            "score": f"{inn1.runs}/{inn1.wickets}", "target": inn1.runs + 1,
        })
        await asyncio.sleep(2)

        # Stream innings 2
        await self.broadcast({"type": "innings_start", "innings": 2, "batting": f_name})
        for ball in balls_inn2:
            await self.broadcast({"type": "ball", "innings": 2, **ball})
            await asyncio.sleep(0.8)
        await self.broadcast({
            "type": "innings_end", "innings": 2,
            "score": f"{inn2.runs}/{inn2.wickets}",
        })

        # Resolve
        if inn2.result_note == "target reached":
            match_winner = f_name
            ww = 10 - inn2.wickets
            result_str = f"{f_name} won by {ww} wicket{'s' if ww != 1 else ''}!"
        elif inn2.runs < inn1.runs:
            diff = inn1.runs - inn2.runs
            match_winner = bat_name
            result_str = f"{bat_name} won by {diff} run{'s' if diff != 1 else ''}!"
        else:
            match_winner = None
            result_str = "Match tied!"

        await self.broadcast({"type": "match_end", "result": result_str})
        return match_winner

    # ------------------------------------------------------------------
    # Series loop
    # ------------------------------------------------------------------

    async def run_series(self):
        self.wins = [0, 0]

        for match_num in range(1, self.series_total + 1):
            match_winner = await self._stream_one_match(match_num)

            # Update series wins
            if match_winner == self.players[0]:
                self.wins[0] += 1
            elif match_winner == self.players[1]:
                self.wins[1] += 1

            remaining = self.series_total - match_num
            clinched  = (
                self.wins[0] >= self.series_to_win
                or self.wins[1] >= self.series_to_win
            )

            # Per-player series_state (your_wins / opp_wins are perspective-flipped)
            for idx in range(2):
                await self.send(idx, {
                    "type":        "series_state",
                    "your_wins":   self.wins[idx],
                    "opp_wins":    self.wins[1 - idx],
                    "to_win":      self.series_to_win,
                    "remaining":   remaining,
                    "series_over": clinched,
                })

            if clinched:
                break

            await asyncio.sleep(4)  # pause between matches

        # Series result
        for idx in range(2):
            if self.wins[0] > self.wins[1]:
                winner_for_player = "you" if idx == 0 else "opp"
            elif self.wins[1] > self.wins[0]:
                winner_for_player = "you" if idx == 1 else "opp"
            else:
                winner_for_player = "draw"

            await self.send(idx, {
                "type":          "series_end",
                "your_wins":     self.wins[idx],
                "opp_wins":      self.wins[1 - idx],
                "series_winner": winner_for_player,
            })

        self.state = "done"


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    room: Room | None = None
    code: str = ""
    player_idx: int = -1

    try:
        raw = await ws.receive_text()
        msg = json.loads(raw)

        # ------------------------------------------------------------------
        # Create room
        # ------------------------------------------------------------------
        if msg.get("type") == "create":
            name        = msg.get("player", "Player1")
            s_total     = int(msg.get("series_total",  1))
            s_to_win    = int(msg.get("series_to_win", 1))
            s_label     = msg.get("series_label", "1-off T20")
            code        = _gen_code()
            room        = Room(code, s_total, s_to_win, s_label)
            room.players.append(name)
            room.sockets.append(ws)
            rooms[code] = room
            player_idx  = 0

            await ws.send_text(json.dumps({
                "type": "room_created", "code": code,
                "player": name, "series_label": s_label,
            }))

            # Wait for 2nd player
            while len(room.players) < 2:
                await asyncio.sleep(0.3)

            await ws.send_text(json.dumps({
                "type": "player_joined", "opponent": room.players[1],
            }))

        # ------------------------------------------------------------------
        # Join room
        # ------------------------------------------------------------------
        elif msg.get("type") == "join":
            name = msg.get("player", "Player2")
            code = msg.get("code", "").upper()
            if code not in rooms:
                await ws.send_text(json.dumps({"type": "error", "message": f"Room '{code}' not found."}))
                await ws.close()
                return
            room = rooms[code]
            if len(room.players) >= 2:
                await ws.send_text(json.dumps({"type": "error", "message": "Room is full."}))
                await ws.close()
                return
            room.players.append(name)
            room.sockets.append(ws)
            player_idx = 1

            await ws.send_text(json.dumps({
                "type": "room_joined", "code": code,
                "opponent": room.players[0],
                "series_label": room.series_label,
            }))

        else:
            await ws.send_text(json.dumps({"type": "error", "message": "Send create or join first."}))
            await ws.close()
            return

        # ------------------------------------------------------------------
        # Draft start (host triggers)
        # ------------------------------------------------------------------
        if player_idx == 0:
            room.pool = get_draft_pool()
            room.state = "drafting"
            await asyncio.sleep(0.5)
            await room.send_draft_state()

        # ------------------------------------------------------------------
        # Message loop
        # ------------------------------------------------------------------
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=600)
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)

            if msg.get("type") == "pick" and room.state == "drafting":
                await room.handle_pick(player_idx, msg.get("player_id", ""))

            if room.state == "done":
                break

    except WebSocketDisconnect:
        pass
    finally:
        if room and code in rooms and room.state == "done":
            del rooms[code]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    print(f"Cricket Sim server starting on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
