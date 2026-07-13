"""
tournament.py  —  full IPL 2026 tournament session endpoints.
"""
import dataclasses
import random
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from engine.tournament import (
    TEAMS, TEAM_STADIUM, generate_schedule, init_standings, update_standings,
    sorted_standings, get_top_4, build_playoff_bracket,
    MatchResult, TeamStanding,
)
from engine.loader import get_team
from engine.ai_manager import (
    run_match_silent, build_xi, build_bowling_order, resolve_xi, suggest_xi, InvalidXI,
)
from engine.stadium import get_stadium
from engine.interactive import init_session, build_match_result
from engine.save_manager import read_save, write_save, delete_save
from api.routes.match import simulate_full_match, _ser_innings
from api import sessions

router = APIRouter()


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _ser_standing(s: TeamStanding) -> dict:
    return {
        "team": s.team, "played": s.played, "won": s.won, "lost": s.lost,
        "tied": s.tied, "points": s.points, "nrr": s.nrr,
    }


def _ser_standings(standings: dict) -> list:
    return [_ser_standing(s) for s in sorted_standings(standings)]


def _ser_result(r: MatchResult) -> dict:
    return dataclasses.asdict(r)


def _ser_schedule_round(rnd: list) -> list:
    out = []
    for m in rnd:
        sm = dict(m)
        if sm.get("result") and not isinstance(sm["result"], dict):
            sm["result"] = _ser_result(sm["result"])
        out.append(sm)
    return out


def _deser_schedule(data: list) -> list:
    result = []
    for rnd in data:
        drnd = []
        for m in rnd:
            dm = dict(m)
            if dm.get("result") and isinstance(dm["result"], dict):
                dm["result"] = MatchResult(**dm["result"])
            drnd.append(dm)
        result.append(drnd)
    return result


def _deser_standings(data: list) -> dict:
    return {
        d["team"]: TeamStanding(
            team=d["team"], played=d["played"], won=d["won"], lost=d["lost"],
            tied=d["tied"], points=d["points"],
            runs_scored=d.get("runs_scored", 0), overs_faced=d.get("overs_faced", 0.0),
            runs_conceded=d.get("runs_conceded", 0), overs_bowled=d.get("overs_bowled", 0.0),
        )
        for d in data
    }


def _next_opponent(sess: dict) -> Optional[str]:
    rnd_idx  = sess["round_idx"]
    schedule = sess["schedule"]
    if rnd_idx >= len(schedule):
        return None
    player_team = sess["player_team"]
    m = next((m for m in schedule[rnd_idx] if player_team in (m["team1"], m["team2"])), None)
    if not m:
        return None
    return m["team2"] if m["team1"] == player_team else m["team1"]


def _state_response(sid: str, sess: dict) -> dict:
    return {
        "session_id":    sid,
        "player_team":   sess["player_team"],
        "round_idx":     sess["round_idx"],
        "total_rounds":  len(sess["schedule"]),
        "standings":     _ser_standings(sess["standings"]),
        "playoff_state": sess.get("playoff_state"),
        "complete":      sess.get("complete", False),
        "next_opponent": _next_opponent(sess),
    }


# ---------------------------------------------------------------------------
# Autosave helper
# ---------------------------------------------------------------------------

def _autosave(sess: dict):
    username = sess.get("username")
    if not username:
        return
    pt  = sess["player_team"]
    my  = sess["standings"][pt]
    rnd = sess["round_idx"]
    tot = len(sess["schedule"])
    ps  = sess.get("playoff_state")

    summary = (f"{pt} | PLAYOFFS | {ps.get('stage_label','')}" if ps
               else f"{pt} | Round {rnd}/{tot} | W{my.won} L{my.lost} | {my.points}pts")

    write_save(username, "tournament", {
        "player_team":    pt,
        "speed":          "2",
        "round_idx":      rnd,
        "schedule":       [_ser_schedule_round(r) for r in sess["schedule"]],
        "standings":      [dataclasses.asdict(s) for s in sorted_standings(sess["standings"])],
        "playoff_state":  ps,
        "season_stats":   sess.get("season_stats", {}),
        "_summary":       summary,
    })


# ---------------------------------------------------------------------------
# Season stats (Orange Cap / Purple Cap / etc.)
# ---------------------------------------------------------------------------

def _overs_to_balls(overs_str: str) -> int:
    ov, _, ball = overs_str.partition(".")
    return int(ov or 0) * 6 + int(ball or 0)


def _blank_player_entry(pid: str, name: str, team: str) -> dict:
    return {
        "id": pid, "name": name, "team": team,
        "matches": 0, "innings_batted": 0, "not_outs": 0,
        "runs": 0, "balls_faced": 0, "fours": 0, "sixes": 0,
        "hundreds": 0, "fifties": 0, "highest_score": 0,
        "best_fours": 0, "best_sixes": 0,
        "innings_bowled": 0, "balls_bowled": 0, "runs_conceded": 0,
        "wickets": 0, "maidens": 0, "dots": 0, "best_dots": 0,
    }


def _accumulate_season_stats(season_stats: dict, innings_list: list[dict]) -> None:
    """Merge one match's innings summaries (already in the unified _ser_innings /
    _build_innings_summary shape — both include id/dots/maidens per player) into
    the running season_stats dict. Called once per match, from every code path
    that resolves a result (AI-vs-AI silent matches, the user's own matches,
    and playoff matches of both kinds)."""
    seen_this_match = set()

    def entry(pid: str, name: str, team: str) -> dict:
        e = season_stats.get(pid)
        if not e:
            e = _blank_player_entry(pid, name, team)
            season_stats[pid] = e
        e["team"] = team
        return e

    # Each innings' bat_stats belong to the team that batted (inn["team"]), but
    # its bowl_stats belong to the OPPOSING (fielding) team — with exactly two
    # innings per match, that's simply whichever team batted in the other one.
    bat_teams = [inn.get("team", "") for inn in innings_list]

    for i, inn in enumerate(innings_list):
        bat_team  = bat_teams[i]
        bowl_team = bat_teams[1 - i] if len(bat_teams) == 2 else ""

        for b in inn.get("bat_stats", []):
            pid = b.get("id")
            if not pid:
                continue
            e = entry(pid, b["name"], bat_team)
            seen_this_match.add(pid)
            e["innings_batted"] += 1
            e["runs"]        += b["runs"]
            e["balls_faced"] += b["balls"]
            e["fours"]       += b["fours"]
            e["sixes"]       += b["sixes"]
            if not b["dismissed"]:
                e["not_outs"] += 1
            if b["runs"] >= 100:
                e["hundreds"] += 1
            elif b["runs"] >= 50:
                e["fifties"] += 1
            e["highest_score"] = max(e["highest_score"], b["runs"])
            e["best_fours"]    = max(e["best_fours"], b["fours"])
            e["best_sixes"]    = max(e["best_sixes"], b["sixes"])

        for w in inn.get("bowl_stats", []):
            pid = w.get("id")
            if not pid:
                continue
            e = entry(pid, w["name"], bowl_team)
            seen_this_match.add(pid)
            balls = _overs_to_balls(w["overs"])
            dots  = w.get("dots", 0)
            e["innings_bowled"] += 1
            e["balls_bowled"]   += balls
            e["runs_conceded"]  += w["runs"]
            e["wickets"]        += w["wickets"]
            e["maidens"]        += w.get("maidens", 0)
            e["dots"]           += dots
            e["best_dots"]      = max(e["best_dots"], dots)

    for pid in seen_this_match:
        season_stats[pid]["matches"] += 1


def _start_interactive_match(
    team_a: str, team_b: str, stadium_id: int, bat_first_team: str, user_team: str,
    user_xi_ids: Optional[list[str]] = None,
) -> str:
    """Build XIs and start an interactive ball-by-ball session; returns its session id."""
    stadium = get_stadium(stadium_id)
    xi_a   = resolve_xi(team_a, user_team, user_xi_ids)
    xi_b   = resolve_xi(team_b, user_team, user_xi_ids)
    bowl_a = build_bowling_order(xi_a)
    bowl_b = build_bowling_order(xi_b)

    if bat_first_team == team_a:
        bat_xi, bat_team = xi_a, team_a
        fld_xi, fld_bowl, fld_team = xi_b, bowl_b, team_b
    else:
        bat_xi, bat_team = xi_b, team_b
        fld_xi, fld_bowl, fld_team = xi_a, bowl_a, team_a

    isess = init_session(bat_xi, fld_xi, fld_bowl, user_team, bat_team, fld_team, stadium)
    return sessions.new_session(isess)


def _match_result_from_interactive(isess: dict, team1: str, team2: str, match_num: int) -> tuple[dict, MatchResult]:
    """Build (public match_data, MatchResult) from a finished interactive session."""
    match_data = build_match_result(isess)
    bat_t = match_data["bat_first"]
    inn1d = match_data["inn1"]
    inn2d = match_data["inn2"]
    mr = MatchResult(
        match_num=match_num,
        team1=team1, team2=team2,
        winner=match_data["result"]["winner"], margin_str=match_data["result"]["margin"],
        team1_runs=inn1d["runs"] if bat_t == team1 else inn2d["runs"],
        team1_wickets=inn1d["wickets"] if bat_t == team1 else inn2d["wickets"],
        team1_overs=float(inn1d["overs"]) if bat_t == team1 else float(inn2d["overs"]),
        team2_runs=inn2d["runs"] if bat_t == team1 else inn1d["runs"],
        team2_wickets=inn2d["wickets"] if bat_t == team1 else inn1d["wickets"],
        team2_overs=float(inn2d["overs"]) if bat_t == team1 else float(inn1d["overs"]),
    )
    return match_data, mr


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class NewTournamentReq(BaseModel):
    player_team: str
    username: Optional[str] = None


class LoadTournamentReq(BaseModel):
    username: str


class PlayRoundReq(BaseModel):
    round_idx: int
    stadium_id: int
    bat_first_team: Optional[str] = None
    user_xi_ids: Optional[list[str]] = None


class PlayPlayoffReq(BaseModel):
    match_idx: int      # 0=Q1, 1=Elim, 2=Q2, 3=Final
    stadium_id: Optional[int] = None
    bat_first_team: Optional[str] = None
    user_xi_ids: Optional[list[str]] = None


@router.post("/new")
def new_tournament(body: NewTournamentReq):
    team = body.player_team.upper()
    if team not in TEAMS:
        raise HTTPException(400, f"Unknown team: {team}")

    sid = sessions.new_session({
        "username":      body.username,
        "player_team":   team,
        "schedule":      generate_schedule(TEAMS),
        "standings":     init_standings(TEAMS),
        "round_idx":     0,
        "playoff_state": None,
        "complete":      False,
        "season_stats":  {},
    })
    sess = sessions.get(sid)
    return _state_response(sid, sess)


@router.post("/load")
def load_tournament(body: LoadTournamentReq):
    save = read_save(body.username, "tournament")
    if not save:
        raise HTTPException(404, "No saved tournament for this user.")

    schedule  = _deser_schedule(save["schedule"])
    standings_raw = save["standings"]
    # standings saved as list of dicts
    if isinstance(standings_raw, list):
        standings = _deser_standings(standings_raw)
    else:
        standings = {
            t: TeamStanding(**d)
            for t, d in standings_raw.items()
        }

    sid = sessions.new_session({
        "username":      body.username,
        "player_team":   save["player_team"],
        "schedule":      schedule,
        "standings":     standings,
        "round_idx":     save["round_idx"],
        "playoff_state": save.get("playoff_state"),
        "complete":      False,
        "season_stats":  save.get("season_stats", {}),
    })
    return _state_response(sid, sessions.get(sid))


@router.get("/{sid}")
def get_tournament(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    return _state_response(sid, sess)


@router.get("/{sid}/suggest-xi")
def suggest_xi_route(sid: str, opponent: str, stadium_id: int):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    player_team = sess["player_team"]
    opp = opponent.upper()
    if opp not in TEAMS:
        raise HTTPException(400, f"Unknown team: {opp}")
    try:
        stadium = get_stadium(stadium_id)
    except KeyError:
        raise HTTPException(404, f"Stadium id {stadium_id} not found.")

    suggested_ids, reasons, matchup_note = suggest_xi(
        get_team(player_team), stadium, get_team(opp),
    )
    return {"suggested_ids": suggested_ids, "reasons": reasons, "matchup_note": matchup_note}


def _ser_batter_stat(e: dict) -> dict:
    dismissals = e["innings_batted"] - e["not_outs"]
    avg = round(e["runs"] / dismissals, 2) if dismissals > 0 else e["runs"]
    sr  = round(e["runs"] / e["balls_faced"] * 100, 2) if e["balls_faced"] else 0
    return {
        "id": e["id"], "name": e["name"], "team": e["team"],
        "matches": e["matches"], "innings": e["innings_batted"], "not_outs": e["not_outs"],
        "runs": e["runs"], "highest_score": e["highest_score"], "avg": avg,
        "balls_faced": e["balls_faced"], "sr": sr,
        "hundreds": e["hundreds"], "fifties": e["fifties"],
        "fours": e["fours"], "sixes": e["sixes"],
        "best_fours": e["best_fours"], "best_sixes": e["best_sixes"],
    }


def _ser_bowler_stat(e: dict) -> dict:
    overs = f"{e['balls_bowled'] // 6}.{e['balls_bowled'] % 6}"
    avg  = round(e["runs_conceded"] / e["wickets"], 2) if e["wickets"] > 0 else None
    econ = round(e["runs_conceded"] / (e["balls_bowled"] / 6), 2) if e["balls_bowled"] else 0
    return {
        "id": e["id"], "name": e["name"], "team": e["team"],
        "matches": e["matches"], "innings": e["innings_bowled"], "overs": overs,
        "runs_conceded": e["runs_conceded"], "wickets": e["wickets"],
        "avg": avg, "econ": econ,
        "maidens": e["maidens"], "dots": e["dots"], "best_dots": e["best_dots"],
    }


@router.get("/{sid}/stats")
def get_season_stats(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    season_stats = sess.get("season_stats", {})

    batters = [_ser_batter_stat(e) for e in season_stats.values() if e["innings_batted"] > 0]
    bowlers = [_ser_bowler_stat(e) for e in season_stats.values() if e["innings_bowled"] > 0]

    batters.sort(key=lambda p: p["runs"], reverse=True)
    bowlers.sort(key=lambda p: p["wickets"], reverse=True)

    return {"batters": batters, "bowlers": bowlers}


@router.post("/{sid}/play-round")
def play_round(sid: str, body: PlayRoundReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")

    schedule  = sess["schedule"]
    standings = sess["standings"]
    rnd_idx   = body.round_idx

    if rnd_idx >= len(schedule):
        raise HTTPException(400, "Round index out of range.")

    round_matches = schedule[rnd_idx]
    player_team   = sess["player_team"]
    season_stats  = sess.setdefault("season_stats", {})

    # --- Simulate AI vs AI ---
    ai_results = []
    for m in round_matches:
        if player_team in (m["team1"], m["team2"]):
            continue
        result, inn1, inn1_team, inn2, inn2_team = run_match_silent(m["team1"], m["team2"], m["match_num"])
        m["played"] = True
        m["result"] = result
        update_standings(standings, result)
        _accumulate_season_stats(season_stats, [
            _ser_innings(inn1, inn1_team), _ser_innings(inn2, inn2_team),
        ])
        ai_results.append({
            "match_num": m["match_num"],
            "team1": m["team1"], "team2": m["team2"],
            "winner": result.winner, "margin": result.margin_str,
            "t1_score": f"{result.team1_runs}/{result.team1_wickets}",
            "t2_score": f"{result.team2_runs}/{result.team2_wickets}",
        })

    # --- User's own match: start an interactive ball-by-ball session ---
    user_match_meta = next(
        (m for m in round_matches if player_team in (m["team1"], m["team2"])), None
    )

    if user_match_meta:
        opp = user_match_meta["team2"] if user_match_meta["team1"] == player_team else user_match_meta["team1"]
        bat_first_team = body.bat_first_team or random.choice([player_team, opp])
        interactive_sid = _start_interactive_match(
            player_team, opp, body.stadium_id, bat_first_team, player_team, body.user_xi_ids,
        )

        sessions.update(sid, {
            "pending_user_match": {
                "interactive_sid": interactive_sid,
                "match_num": user_match_meta["match_num"],
                "opp": opp,
                "round_idx": rnd_idx,
            },
        })

        return {
            "ai_results":      ai_results,
            "standings":       _ser_standings(standings),
            "interactive_sid": interactive_sid,
        }

    # No match for the player this round (bye) — advance immediately.
    sessions.update(sid, {"round_idx": rnd_idx + 1})
    _autosave(sessions.get(sid))

    return {
        "ai_results":     ai_results,
        "standings":      _ser_standings(standings),
        "interactive_sid": None,
        "next_round_idx": rnd_idx + 1,
        "group_complete": rnd_idx + 1 >= len(schedule),
    }


@router.post("/{sid}/finish-user-match")
def finish_user_match(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    pending = sess.get("pending_user_match")
    if not pending:
        raise HTTPException(400, "No pending user match.")

    isess = sessions.get(pending["interactive_sid"])
    if not isess:
        raise HTTPException(404, "Interactive session not found.")
    if isess["pending"] != "complete":
        raise HTTPException(400, "Match not finished yet.")

    standings   = sess["standings"]
    player_team = sess["player_team"]
    opp         = pending["opp"]
    rnd_idx     = pending["round_idx"]

    match_data, mr = _match_result_from_interactive(isess, player_team, opp, pending["match_num"])
    update_standings(standings, mr)
    _accumulate_season_stats(sess.setdefault("season_stats", {}), [match_data["inn1"], match_data["inn2"]])

    schedule = sess["schedule"]
    m = next((m for m in schedule[rnd_idx] if player_team in (m["team1"], m["team2"])), None)
    if m:
        m["played"] = True
        m["result"] = mr

    new_round_idx  = rnd_idx + 1
    group_complete = new_round_idx >= len(schedule)
    sessions.update(sid, {"round_idx": new_round_idx, "pending_user_match": None})
    _autosave(sessions.get(sid))

    return {
        "match_data":     match_data,
        "standings":      _ser_standings(standings),
        "next_round_idx": new_round_idx,
        "group_complete": group_complete,
    }


@router.get("/{sid}/top4")
def get_top4(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    top4 = get_top_4(sess["standings"])
    bracket = build_playoff_bracket(top4)
    sessions.update(sid, {"playoff_bracket": bracket, "playoff_match_num": 71})
    return {"top4": top4, "bracket": bracket, "player_qualified": sess["player_team"] in top4}


@router.post("/{sid}/play-playoff")
def play_playoff(sid: str, body: PlayPlayoffReq):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")

    bracket    = sess.get("playoff_bracket")
    match_num  = sess.get("playoff_match_num", 71)
    player_team = sess["player_team"]

    if not bracket:
        raise HTTPException(400, "Playoffs not started. Call /top4 first.")

    idx  = body.match_idx
    slot = bracket[idx]
    t1, t2 = slot["team1"], slot["team2"]

    sid_used = body.stadium_id or TEAM_STADIUM.get(t1, 1)

    # Player's own playoff match: interactive ball-by-ball session.
    if player_team in (t1, t2):
        bat_first_team = body.bat_first_team or random.choice([t1, t2])
        interactive_sid = _start_interactive_match(
            t1, t2, sid_used, bat_first_team, player_team, body.user_xi_ids,
        )
        sessions.update(sid, {
            "pending_playoff": {"interactive_sid": interactive_sid, "match_idx": idx, "t1": t1, "t2": t2},
        })
        return {"interactive_sid": interactive_sid, "bracket": bracket}

    # AI-vs-AI playoff match — instant as before.
    match_data = simulate_full_match(t1, t2, sid_used, body.bat_first_team)
    winner     = match_data["result"]["winner"] or random.choice([t1, t2])
    loser      = t2 if winner == t1 else t1
    bracket[idx]["winner"] = winner
    _accumulate_season_stats(sess.setdefault("season_stats", {}), [match_data["inn1"], match_data["inn2"]])

    # Wire dependent slots
    if idx == 0:
        bracket[2]["team1"] = loser
    elif idx == 1:
        bracket[2]["team2"] = winner
    elif idx == 2:
        bracket[3]["team1"] = bracket[0]["winner"]
        bracket[3]["team2"] = winner

    sessions.update(sid, {
        "playoff_bracket":    bracket,
        "playoff_match_num":  match_num + 1,
        "complete":           idx == 3,
    })

    if idx < 3:
        _autosave(sessions.get(sid))
    else:
        # Tournament over — clear save
        username = sess.get("username")
        if username:
            delete_save(username, "tournament")

    return {
        "interactive_sid": None,
        "match_data": match_data,
        "winner":     winner,
        "bracket":    bracket,
        "complete":   idx == 3,
        "champion":   winner if idx == 3 else None,
    }


@router.post("/{sid}/finish-playoff")
def finish_playoff(sid: str):
    sess = sessions.get(sid)
    if not sess:
        raise HTTPException(404, "Session not found.")
    pending = sess.get("pending_playoff")
    if not pending:
        raise HTTPException(400, "No pending playoff match.")

    isess = sessions.get(pending["interactive_sid"])
    if not isess:
        raise HTTPException(404, "Interactive session not found.")
    if isess["pending"] != "complete":
        raise HTTPException(400, "Match not finished yet.")

    t1, t2 = pending["t1"], pending["t2"]
    idx    = pending["match_idx"]
    match_num = sess.get("playoff_match_num", 71)

    match_data, mr = _match_result_from_interactive(isess, t1, t2, match_num)
    winner = mr.winner or random.choice([t1, t2])
    loser  = t2 if winner == t1 else t1
    _accumulate_season_stats(sess.setdefault("season_stats", {}), [match_data["inn1"], match_data["inn2"]])

    bracket = sess["playoff_bracket"]
    bracket[idx]["winner"] = winner
    if idx == 0:
        bracket[2]["team1"] = loser
    elif idx == 1:
        bracket[2]["team2"] = winner
    elif idx == 2:
        bracket[3]["team1"] = bracket[0]["winner"]
        bracket[3]["team2"] = winner

    sessions.update(sid, {
        "playoff_bracket":   bracket,
        "playoff_match_num": match_num + 1,
        "complete":          idx == 3,
        "pending_playoff":   None,
    })

    if idx < 3:
        _autosave(sessions.get(sid))
    else:
        username = sess.get("username")
        if username:
            delete_save(username, "tournament")

    return {
        "match_data": match_data,
        "winner":     winner,
        "bracket":    bracket,
        "complete":   idx == 3,
        "champion":   winner if idx == 3 else None,
    }
