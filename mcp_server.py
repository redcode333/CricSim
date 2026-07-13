import json
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

DATA_PATH = Path(__file__).parent / "ipl_2026_game_ratings (1).json"

with open(DATA_PATH, encoding="utf-8") as f:
    _raw = json.load(f)

PLAYERS: list[dict] = _raw["players"]
PLAYERS_BY_ID = {p["id"]: p for p in PLAYERS}
PLAYERS_BY_NAME = {p["name"].lower(): p for p in PLAYERS}

mcp = FastMCP("cricket-sim")


@mcp.tool()
def get_player(name_or_id: str) -> dict:
    """Return full stats for a player by name or ID (e.g. 'Virat Kohli' or 'RCB_001')."""
    key = name_or_id.strip()
    if key in PLAYERS_BY_ID:
        return PLAYERS_BY_ID[key]
    lower = key.lower()
    if lower in PLAYERS_BY_NAME:
        return PLAYERS_BY_NAME[lower]
    # fuzzy: partial name match
    matches = [p for p in PLAYERS if lower in p["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return {"error": "multiple matches", "players": [p["name"] for p in matches]}
    return {"error": f"player not found: {name_or_id}"}


@mcp.tool()
def list_teams() -> list[str]:
    """Return all team codes present in the dataset."""
    return sorted({p["team"] for p in PLAYERS})


@mcp.tool()
def get_team_players(team: str) -> list[dict]:
    """Return all players for a team (use team code e.g. 'CSK', 'MI', 'RCB')."""
    code = team.upper()
    squad = [p for p in PLAYERS if p["team"] == code]
    if not squad:
        return [{"error": f"no players found for team '{team}'"}]
    return squad


@mcp.tool()
def search_players(
    team: str = "",
    role: str = "",
    nationality: str = "",
    batting_style: str = "",
    bowling_type: str = "",
) -> list[dict]:
    """
    Filter players by any combination of fields.
    - team: e.g. 'MI', 'CSK'
    - role: 'batter', 'bowler', 'all_rounder', 'wicket_keeper'
    - nationality: 'IND', 'AUS', 'ENG', etc.
    - batting_style: 'right-hand' or 'left-hand'
    - bowling_type: 'pace' or 'spin'
    Returns matching player summaries (name, team, role, id).
    """
    results = PLAYERS
    if team:
        results = [p for p in results if p["team"].upper() == team.upper()]
    if role:
        results = [p for p in results if p["role"].lower() == role.lower()]
    if nationality:
        results = [p for p in results if p["nationality"].upper() == nationality.upper()]
    if batting_style:
        results = [p for p in results if batting_style.lower() in p.get("batting_style", "").lower()]
    if bowling_type:
        results = [p for p in results if p.get("bowling", {}).get("type", "").lower() == bowling_type.lower()]
    return [
        {"id": p["id"], "name": p["name"], "team": p["team"], "role": p["role"], "nationality": p["nationality"]}
        for p in results
    ]


@mcp.tool()
def top_players(attribute: str, n: int = 10, team: str = "") -> list[dict]:
    """
    Return the top N players ranked by a nested attribute.
    attribute examples: 'skills.bat_power', 'bowling.wicket_threat', 'mental.pressure_handling',
                        'form.recent_form', 'fielding.catching', 'running.speed'
    Optionally filter by team code.
    """
    pool = PLAYERS if not team else [p for p in PLAYERS if p["team"].upper() == team.upper()]

    parts = attribute.split(".")
    def get_val(player):
        val = player
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return -1
        return val if isinstance(val, (int, float)) else -1

    ranked = sorted(pool, key=get_val, reverse=True)[:n]
    return [
        {
            "rank": i + 1,
            "id": p["id"],
            "name": p["name"],
            "team": p["team"],
            "role": p["role"],
            attribute: get_val(p),
        }
        for i, p in enumerate(ranked)
    ]


@mcp.tool()
def compare_players(name_or_id_1: str, name_or_id_2: str) -> dict:
    """Side-by-side stat comparison of two players."""
    def lookup(key):
        k = key.strip()
        if k in PLAYERS_BY_ID:
            return PLAYERS_BY_ID[k]
        lower = k.lower()
        if lower in PLAYERS_BY_NAME:
            return PLAYERS_BY_NAME[lower]
        matches = [p for p in PLAYERS if lower in p["name"].lower()]
        return matches[0] if len(matches) == 1 else None

    p1, p2 = lookup(name_or_id_1), lookup(name_or_id_2)
    if not p1:
        return {"error": f"not found: {name_or_id_1}"}
    if not p2:
        return {"error": f"not found: {name_or_id_2}"}
    return {"player_1": p1, "player_2": p2}


if __name__ == "__main__":
    mcp.run(transport="stdio")
