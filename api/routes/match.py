"""
match.py  —  stateless match simulation endpoints.
"""
import random
import dataclasses
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from engine.loader import get_team
from engine.ai_manager import build_xi, build_bowling_order
from engine.simulator import simulate_innings
from engine.stadium import get_stadium
from engine.match_state import InningsState
from engine.toss import flip_toss

router = APIRouter()


# ---------------------------------------------------------------------------
# Serialisation helper
# ---------------------------------------------------------------------------

def _ser_innings(state: InningsState, team: str) -> dict:
    return {
        "team": team,
        "runs": state.runs,
        "wickets": state.wickets,
        "overs": state.over_str,
        "crr": state.run_rate,
        "result_note": state.result_note,
        "balls": state.ball_log,
        "bat_stats": [
            {
                "id": s.player["id"], "name": s.name, "runs": s.runs, "balls": s.balls,
                "fours": s.fours, "sixes": s.sixes, "sr": s.strike_rate,
                "dismissed": s.dismissed, "how_out": s.dismissal,
            }
            for s in state.bat_stats.values()
        ],
        "bowl_stats": [
            {
                "id": s.player["id"], "name": s.name, "overs": s.overs_str, "runs": s.runs,
                "wickets": s.wickets, "wides": s.wides, "no_balls": s.no_balls,
                "economy": s.economy, "maidens": s.maidens, "dots": s.dots,
            }
            for s in state.bowl_stats.values()
        ],
        "fow": [
            {"n": f.wicket_num, "score": f.score, "batsman": f.batsman_name,
             "over": f"{f.over}.{f.ball}"}
            for f in state.fow
        ],
    }


def _resolve(bat_team, field_team, inn1, inn2) -> dict:
    if inn2.result_note == "target reached":
        ww = 10 - inn2.wickets
        return {"winner": field_team, "margin": f"{ww} wicket{'s' if ww != 1 else ''}"}
    elif inn2.runs < inn1.runs:
        diff = inn1.runs - inn2.runs
        return {"winner": bat_team, "margin": f"{diff} run{'s' if diff != 1 else ''}"}
    return {"winner": None, "margin": "Tied"}


def simulate_full_match(team1: str, team2: str, stadium_id: int, bat_first: Optional[str] = None) -> dict:
    """Simulate both innings and return serialised match data."""
    stadium = get_stadium(stadium_id)
    xi1 = build_xi(get_team(team1))
    xi2 = build_xi(get_team(team2))
    bowl1 = build_bowling_order(xi1)
    bowl2 = build_bowling_order(xi2)

    if bat_first is None:
        bat_first = random.choice([team1, team2])

    if bat_first == team1:
        bat_xi, bat_bowl, bat_team   = xi1, bowl2, team1
        fld_xi, fld_bowl, fld_team   = xi2, bowl1, team2
    else:
        bat_xi, bat_bowl, bat_team   = xi2, bowl1, team2
        fld_xi, fld_bowl, fld_team   = xi1, bowl2, team1

    inn1 = simulate_innings(bat_xi, fld_xi, bat_bowl, target=None,    verbose=False, sc=None, stadium=stadium)
    inn2 = simulate_innings(fld_xi, bat_xi, fld_bowl, target=inn1.runs+1, verbose=False, sc=None, stadium=stadium)

    result = _resolve(bat_team, fld_team, inn1, inn2)
    return {
        "bat_first":  bat_team,
        "fld_first":  fld_team,
        "stadium":    {"id": stadium["id"], "name": stadium["name"], "city": stadium["city"]},
        "inn1":       _ser_innings(inn1, bat_team),
        "inn2":       _ser_innings(inn2, fld_team),
        "result":     result,
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

class QuickMatchReq(BaseModel):
    team1: str
    team2: str
    stadium_id: int
    bat_first: Optional[str] = None


@router.post("/quick")
def quick_match(body: QuickMatchReq):
    try:
        return simulate_full_match(body.team1.upper(), body.team2.upper(),
                                   body.stadium_id, body.bat_first)
    except Exception as e:
        raise HTTPException(400, str(e))


class TossReq(BaseModel):
    caller_team: str
    opponent_team: str
    stadium_id: int
    call: str  # "heads" | "tails"


@router.post("/toss")
def toss(body: TossReq):
    try:
        stadium = get_stadium(body.stadium_id)
        return flip_toss(body.caller_team, body.opponent_team, body.call, stadium)
    except Exception as e:
        raise HTTPException(400, str(e))
