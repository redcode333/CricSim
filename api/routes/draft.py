"""
draft.py  —  draft session + series endpoints.
"""
import random
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from engine.draft import get_draft_pool, ai_pick
from engine.ai_manager import build_bowling_order
from engine.stadium import get_stadium
from engine.interactive import init_session, build_match_result
from engine.save_manager import write_save, delete_save, read_save
from api import sessions

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ser_player(p: dict) -> dict:
    return {
        "id": p["id"], "name": p["name"], "team": p["team"],
        "role": p["role"],
        "bat_power": round(p["skills"]["bat_power"], 2),
        "bat_control": round(p["skills"]["bat_control"], 2),
        "wicket_threat": round(p["bowling"]["wicket_threat"], 2),
        "economy_skill": round(p["bowling"]["economy_skill"], 2),
        "bowling_type": p["bowling"].get("type", ""),
    }


def _draft_state(sid: str, sess: dict) -> dict:
    return {
        "session_id":  sid,
        "round":       sess["round"],
        "awaiting":    sess["awaiting"],
        "user_xi":     [_ser_player(p) for p in sess["user_xi"]],
        "ai_xi":       [_ser_player(p) for p in sess["ai_xi"]],
        "pool":        [_ser_player(p) for p in sess["pool"][:40]],
        "complete":    sess["complete"],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class NewDraftReq(BaseModel):
    username: Optional[str] = None


class LoadDraftReq(BaseModel):
    username: str


class PickReq(BaseModel):
    player_id: str


class SeriesMatchReq(BaseModel):
    stadium_id: int
    series_total: int = 1
    series_to_win: int = 1
    series_label: str = "1-off T20"


@router.post("/new")
def new_draft(body: NewDraftReq):
    pool = get_draft_pool()
    sid  = sessions.new_session({
        "username": body.username,
        "pool":     pool,
        "user_xi":  [],
        "ai_xi":    [],
        "round":    1,
        "awaiting": "user",   # odd round 1 → user picks first
        "complete": False,
        # Series state (set after draft)
        "format":     None,
        "stadium_id": None,
        "user_wins":  0,
        "ai_wins":    0,
        "next_match": 1,
    })
    return _draft_state(sid, sessions.get(sid))


@router.get("/{sid}")
def get_draft(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    return _draft_state(sid, sess)


@router.post("/{sid}/pick")
def draft_pick(sid: str, body: PickReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    if sess["complete"]:
        raise HTTPException(400, "Draft is complete.")
    if sess["awaiting"] != "user":
        raise HTTPException(400, "Not your turn.")

    pool = sess["pool"]
    player = next((p for p in pool if p["id"] == body.player_id), None)
    if not player:
        raise HTTPException(400, "Player not in pool.")

    user_xi = sess["user_xi"]
    ai_xi   = sess["ai_xi"]

    pool.remove(player)
    user_xi.append(player)
    user_pick = _ser_player(player)

    # AI picks immediately after user
    ai_player = ai_pick(pool, ai_xi)
    pool.remove(ai_player)
    ai_xi.append(ai_player)
    ai_pick_data = _ser_player(ai_player)

    # Advance turn/round — strict single-pick alternation (user, ai, user, ai, ...)
    complete  = len(user_xi) == 11
    new_round = len(user_xi) + (0 if complete else 1)
    new_await = "user"

    sessions.update(sid, {
        "pool": pool, "user_xi": user_xi, "ai_xi": ai_xi,
        "round": new_round, "awaiting": new_await, "complete": complete,
    })

    return {
        "user_pick":  user_pick,
        "ai_picks":   [ai_pick_data],
        "round":      new_round,
        "awaiting":   new_await,
        "complete":   complete,
        "user_xi":    [_ser_player(p) for p in user_xi],
        "ai_xi":      [_ser_player(p) for p in ai_xi],
        "pool":       [_ser_player(p) for p in pool[:40]],
    }


class SeriesSetupReq(BaseModel):
    stadium_id: int
    total: int = 1
    to_win: int = 1
    label: str = "1-off T20"


@router.post("/{sid}/setup-series")
def setup_series(sid: str, body: SeriesSetupReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    if not sess["complete"]:
        raise HTTPException(400, "Draft not complete yet.")

    sessions.update(sid, {
        "format": {"total": body.total, "to_win": body.to_win, "label": body.label},
        "stadium_id": body.stadium_id,
        "user_wins": 0, "ai_wins": 0, "next_match": 1,
    })
    return {"ok": True}


class PlayMatchReq(BaseModel):
    bat_first_team: Optional[str] = None  # "YOU" | "AI"


@router.post("/{sid}/play-match")
def play_series_match(sid: str, body: PlayMatchReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    if not sess.get("format"):
        raise HTTPException(400, "Call /setup-series first.")

    fmt        = sess["format"]
    user_xi    = sess["user_xi"]
    ai_xi      = sess["ai_xi"]
    stadium_id = sess["stadium_id"]
    user_wins  = sess["user_wins"]
    ai_wins    = sess["ai_wins"]

    if user_wins >= fmt["to_win"] or ai_wins >= fmt["to_win"]:
        raise HTTPException(400, "Series already concluded.")

    bat_first_team = body.bat_first_team or random.choice(["YOU", "AI"])
    stadium   = get_stadium(stadium_id)
    user_bowl = build_bowling_order(user_xi)
    ai_bowl   = build_bowling_order(ai_xi)

    if bat_first_team == "YOU":
        bat_xi, bat_team = user_xi, "YOU"
        fld_xi, fld_bowl, fld_team = ai_xi, ai_bowl, "AI"
    else:
        bat_xi, bat_team = ai_xi, "AI"
        fld_xi, fld_bowl, fld_team = user_xi, user_bowl, "YOU"

    isess = init_session(bat_xi, fld_xi, fld_bowl, "YOU", bat_team, fld_team, stadium)
    interactive_sid = sessions.new_session(isess)
    sessions.update(sid, {"pending_match_sid": interactive_sid})

    return {"interactive_sid": interactive_sid}


@router.post("/{sid}/finish-match")
def finish_series_match(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    interactive_sid = sess.get("pending_match_sid")
    if not interactive_sid:
        raise HTTPException(400, "No pending match.")

    isess = sessions.get(interactive_sid)
    if not isess:
        raise HTTPException(404, "Interactive session not found.")
    if isess["pending"] != "complete":
        raise HTTPException(400, "Match not finished yet.")

    match_data = build_match_result(isess)
    fmt        = sess["format"]
    match_num  = sess["next_match"]
    user_wins  = sess["user_wins"]
    ai_wins    = sess["ai_wins"]

    bat_first = match_data["bat_first"]
    inn1      = match_data["inn1"]
    inn2      = match_data["inn2"]

    if inn2["result_note"] == "target reached":
        winner = "ai" if bat_first == "YOU" else "user"
    elif inn1["runs"] > inn2["runs"]:
        winner = "user" if bat_first == "YOU" else "ai"
    else:
        winner = "tie"

    if winner == "user":
        user_wins += 1
    elif winner == "ai":
        ai_wins += 1

    series_done = user_wins >= fmt["to_win"] or ai_wins >= fmt["to_win"]
    sessions.update(sid, {
        "user_wins": user_wins, "ai_wins": ai_wins,
        "next_match": match_num + 1,
        "pending_match_sid": None,
    })

    username   = sess.get("username")
    user_xi    = sess["user_xi"]
    ai_xi      = sess["ai_xi"]
    stadium_id = sess["stadium_id"]
    if username:
        if series_done:
            delete_save(username, "duo_ai")
        else:
            write_save(username, "duo_ai", {
                "user_xi":        user_xi,
                "ai_xi":          ai_xi,
                "format":         fmt,
                "stadium_id":     stadium_id,
                "user_wins":      user_wins,
                "ai_wins":        ai_wins,
                "next_match_num": match_num + 1,
                "_summary":       f"{fmt['label']} | YOU {user_wins}–AI {ai_wins} | Match {match_num+1}/{fmt['total']} next",
            })

    return {
        "match_data":   match_data,
        "match_winner": winner,
        "user_wins":    user_wins,
        "ai_wins":      ai_wins,
        "series_done":  series_done,
        "series_winner": ("user" if user_wins >= fmt["to_win"]
                          else "ai" if ai_wins >= fmt["to_win"] else None),
        "format":       fmt,
    }
