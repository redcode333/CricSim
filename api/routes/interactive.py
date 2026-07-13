"""
interactive.py — over-by-over interactive match endpoints.
"""
import random
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from engine.loader import get_team
from engine.ai_manager import build_xi, build_bowling_order, resolve_xi, InvalidXI
from engine.stadium import get_stadium
from engine.interactive import (
    init_session, simulate_over, start_second_innings,
    build_match_result, suggest_bowler, suggest_batsman,
    choose_batsman, choose_openers, _build_innings_summary,
)
from api import sessions

router = APIRouter()


def _public_state(sid: str, sess: dict) -> dict:
    """Return the state that the frontend needs to render."""
    over      = sess["legal_balls"] // 6
    crr       = round(sess["runs"] / (sess["legal_balls"] / 6), 2) if sess["legal_balls"] else 0
    rrr       = None
    if sess["target"]:
        balls_left = max(1, 120 - sess["legal_balls"])
        rrr = round((sess["target"] - sess["runs"]) / (balls_left / 6), 2)

    # Active batsmen stats
    active_bats = []
    for pid in [sess["striker_id"], sess["non_striker_id"]]:
        if pid and pid in sess["bat_stats"]:
            s = sess["bat_stats"][pid]
            active_bats.append({
                "name":     s["name"],
                "runs":     s["runs"],
                "balls":    s["balls"],
                "fours":    s["fours"],
                "sixes":    s["sixes"],
                "sr":       round((s["runs"] / s["balls"]) * 100, 1) if s["balls"] else 0,
                "is_striker": pid == sess["striker_id"],
            })

    # Current bowler stats
    last_bid = sess.get("last_bowler_id")
    current_bowler = None
    if last_bid and last_bid in sess["bowl_stats"]:
        s = sess["bowl_stats"][last_bid]
        current_bowler = {
            "name":    s["name"],
            "overs":   f"{s['balls'] // 6}.{s['balls'] % 6}",
            "runs":    s["runs"],
            "wickets": s["wickets"],
        }

    phase_name = "Powerplay" if over < 6 else ("Middle Overs" if over < 16 else "Death Overs")

    return {
        "session_id": sid,
        "inning":     sess["inning"],
        "bat_team":   sess["bat_team"],
        "fld_team":   sess["fld_team"],
        "user_team":  sess["user_team"],
        "stadium":    sess["stadium"],
        "runs":       sess["runs"],
        "wickets":    sess["wickets"],
        "over":       over,
        "over_str":   f"{over}.{sess['legal_balls'] % 6}",
        "crr":        crr,
        "target":     sess.get("target"),
        "rrr":        rrr,
        "runs_needed": (sess["target"] - sess["runs"]) if sess.get("target") else None,
        "phase":      phase_name,
        "phase_key":  "powerplay" if over < 6 else ("middle" if over < 16 else "death"),
        "active_batsmen": active_bats,
        "current_bowler": current_bowler,
        "last_over_balls": sess.get("last_over_balls", []),
        "ball_log":   sess.get("ball_log", []),
        "fow":        sess.get("fow", []),
        "pending":    sess["pending"],
        "available_bowlers": sess.get("available_bowlers", []),
        "available_batsmen": sess.get("available_batsmen", []),
        "available_openers": sess.get("available_openers", []),
        # user control flags
        "user_picks_bowler":  sess["fld_team"] == sess["user_team"],
        "user_picks_batsman": sess["bat_team"] == sess["user_team"],
        "user_picks_openers": sess["bat_team"] == sess["user_team"],
        "complete":   sess["complete"],
        "inn1_data":  sess.get("inn1_data"),
    }


# ─────────────────────────────────────────────────────────────────────────────

class StartReq(BaseModel):
    team1: str
    team2: str
    stadium_id: int
    bat_first: Optional[str] = None
    user_team: str  # which team the user manages
    user_xi_ids: Optional[list[str]] = None  # user's own choice of playing XI (exactly 11)


@router.post("/start")
def start_interactive(body: StartReq):
    t1 = body.team1.upper()
    t2 = body.team2.upper()
    ut = body.user_team.upper()

    if ut not in (t1, t2):
        raise HTTPException(400, "user_team must be one of the two playing teams")

    try:
        stadium  = get_stadium(body.stadium_id)
        xi1      = resolve_xi(t1, ut, body.user_xi_ids)
        xi2      = resolve_xi(t2, ut, body.user_xi_ids)
        bowl1    = build_bowling_order(xi1)
        bowl2    = build_bowling_order(xi2)
    except InvalidXI as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))

    bat_first = body.bat_first.upper() if body.bat_first else random.choice([t1, t2])

    if bat_first == t1:
        bat_xi, fld_xi, fld_bowl = xi1, xi2, bowl2
        bat_team, fld_team = t1, t2
    else:
        bat_xi, fld_xi, fld_bowl = xi2, xi1, bowl1
        bat_team, fld_team = t2, t1

    sess = init_session(bat_xi, fld_xi, fld_bowl, ut, bat_team, fld_team, stadium)
    sid  = sessions.new_session(sess)
    return _public_state(sid, sess)


class OpenersChoiceReq(BaseModel):
    striker_id: str
    non_striker_id: str


@router.post("/{sid}/openers")
def pick_openers(sid: str, body: OpenersChoiceReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    if sess["pending"] != "pick_openers":
        raise HTTPException(400, f"Not waiting for openers pick (pending={sess['pending']})")
    try:
        sess = choose_openers(sess, body.striker_id, body.non_striker_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sessions.update(sid, sess)
    return _public_state(sid, sess)


class BowlerChoiceReq(BaseModel):
    bowler_id: str


@router.post("/{sid}/over")
def play_over(sid: str, body: BowlerChoiceReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    if sess["pending"] != "pick_bowler":
        raise HTTPException(400, f"Not waiting for a bowler pick (pending={sess['pending']})")
    try:
        sess = simulate_over(sess, body.bowler_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sessions.update(sid, sess)
    return _public_state(sid, sess)


class BatsmanChoiceReq(BaseModel):
    batsman_id: str


@router.post("/{sid}/batsman")
def pick_batsman(sid: str, body: BatsmanChoiceReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    if sess["pending"] != "pick_batsman":
        raise HTTPException(400, f"Not waiting for batsman pick (pending={sess['pending']})")
    try:
        sess = choose_batsman(sess, body.batsman_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    sessions.update(sid, sess)
    return _public_state(sid, sess)


@router.post("/{sid}/next-innings")
def next_innings(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    if sess["pending"] != "innings_break":
        raise HTTPException(400, "Not at innings break")
    sess = start_second_innings(sess)
    sessions.update(sid, sess)
    return _public_state(sid, sess)


@router.get("/{sid}/result")
def get_result(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    if sess["pending"] != "complete":
        raise HTTPException(400, "Match not complete yet")
    return build_match_result(sess)


@router.get("/{sid}/suggest")
def get_suggestion(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    pending = sess.get("pending")
    if pending == "pick_bowler":
        return {"type": "bowler", **suggest_bowler(sess)}
    if pending == "pick_batsman":
        return {"type": "batsman", **suggest_batsman(sess)}
    return {"type": None, "reason": "No decision pending."}


@router.get("/{sid}")
def get_state(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    return _public_state(sid, sess)
