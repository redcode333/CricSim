from fastapi import APIRouter, HTTPException
from engine.loader import list_teams, get_team
from engine.stadium import list_stadiums, get_stadium
from engine.tournament import TEAM_STADIUM

router = APIRouter()

_STADIUM_HOME_TEAM = {sid: team for team, sid in TEAM_STADIUM.items()}


@router.get("/")
def teams():
    return list_teams()


@router.get("/stadiums")
def stadiums():
    return [
        {**s, "home_team": _STADIUM_HOME_TEAM.get(s["id"])}
        for s in list_stadiums()
    ]


@router.get("/{team}/players")
def players(team: str):
    try:
        squad = get_team(team.upper())
    except Exception:
        raise HTTPException(404, f"Team {team} not found")
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "role": p["role"],
            "team": p["team"],
            "nationality": p.get("nationality", ""),
            "skills": p.get("skills", {}),
            "bowling": p.get("bowling", {}),
            "mental": p.get("mental", {}),
            "form": p.get("form", {}),
            "fielding": p.get("fielding", {}),
            "running": p.get("running", {}),
            # flat aliases for match engine / draft list display
            "bat_power": round(p["skills"]["bat_power"], 2),
            "bat_control": round(p["skills"]["bat_control"], 2),
            "wicket_threat": round(p["bowling"]["wicket_threat"], 2),
            "economy_skill": round(p["bowling"]["economy_skill"], 2),
        }
        for p in squad
    ]
