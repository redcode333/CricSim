"""
loader.py
Reads ipl_2026_game_ratings.json and exposes helpers to fetch players by id,
team, or role. Everything downstream reads data through this module.
"""

import json
import os
from typing import Optional

_DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "ipl_2026_game_ratings (1).json",
)

# -------------------------------------------------------------------
# Internal cache — loaded once on first import
# -------------------------------------------------------------------
_db: dict = {}          # full parsed JSON
_by_id: dict = {}       # player_id -> player dict
_by_team: dict = {}     # team code  -> list of player dicts


def _load():
    global _db, _by_id, _by_team
    if _db:
        return  # already loaded

    path = os.path.abspath(_DATA_FILE)
    with open(path, "r", encoding="utf-8") as f:
        _db = json.load(f)

    for player in _db["players"]:
        _by_id[player["id"]] = player

        team = player["team"]
        if team not in _by_team:
            _by_team[team] = []
        _by_team[team].append(player)


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def get_player(player_id: str) -> dict:
    """Return a single player dict by id. Raises KeyError if not found."""
    _load()
    return _by_id[player_id]


def get_team(team_code: str) -> list[dict]:
    """Return all players belonging to a team (e.g. 'CSK', 'MI')."""
    _load()
    code = team_code.upper()
    if code not in _by_team:
        raise KeyError(f"Team '{code}' not found. Available: {list_teams()}")
    return _by_team[code]


def get_team_by_role(team_code: str, role: str) -> list[dict]:
    """
    Filter a team's players by role.
    Roles in the data: 'batter', 'bowler', 'all rounder', 'wicket_keeper'
    """
    return [p for p in get_team(team_code) if p["role"] == role]


def list_teams() -> list[str]:
    """Return all team codes present in the database."""
    _load()
    return sorted(_by_team.keys())


def list_players(team_code: Optional[str] = None) -> list[dict]:
    """Return all players, optionally filtered by team."""
    _load()
    if team_code:
        return get_team(team_code)
    return list(_by_id.values())


def search_player(name: str) -> list[dict]:
    """Case-insensitive partial name search across all players."""
    _load()
    name_lower = name.lower()
    return [p for p in _by_id.values() if name_lower in p["name"].lower()]


# -------------------------------------------------------------------
# Convenience: flat attribute accessors used by the engine
# -------------------------------------------------------------------

def bat_skills(player: dict) -> dict:
    """Return batting skill dict for easy access."""
    return player["skills"]


def bowl_skills(player: dict) -> dict:
    """Return bowling skill dict."""
    return player["bowling"]


def mental(player: dict) -> dict:
    return player["mental"]


def form(player: dict) -> float:
    return player["form"]["recent_form"]


def bowling_type(player: dict) -> str:
    """Return 'pace' or 'spin'."""
    return player["bowling"]["type"]
