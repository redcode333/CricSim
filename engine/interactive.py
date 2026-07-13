"""
interactive.py — incremental over-by-over simulation for the interactive match.
Each over is simulated on demand so the user can pick bowler / batsman between overs.
"""
import random
from engine.probability import ball_outcome
from engine.commentary import ball_commentary

MAX_BOWLER_OVERS = 4


def _phase(over: int) -> str:
    if over < 6:   return "powerplay"
    if over < 16:  return "middle"
    return "death"


def _ser_bowler(p: dict, bowl_stats: dict) -> dict:
    bid = p["id"]
    bs  = bowl_stats.get(bid, {})
    overs_bowled = bs.get("balls", 0) // 6
    return {
        "id":           bid,
        "name":         p["name"],
        "team":         p.get("team", ""),
        "role":         p.get("role", ""),
        "bowling_type": p.get("bowling", {}).get("type", ""),
        "wicket_threat": round(p.get("bowling", {}).get("wicket_threat", 0), 2),
        "economy_skill": round(p.get("bowling", {}).get("economy_skill", 0), 2),
        "death_skill":   round(p.get("bowling", {}).get("death_skill", 0.5), 2),
        "overs_bowled":  overs_bowled,
        "runs_given":    bs.get("runs", 0),
        "wickets":       bs.get("wickets", 0),
    }


def _ser_batsman(p: dict, bat_stats: dict) -> dict:
    bid = p["id"]
    bs  = bat_stats.get(bid, {})
    return {
        "id":         bid,
        "name":       p["name"],
        "team":       p.get("team", ""),
        "role":       p.get("role", ""),
        "bat_power":      round(p.get("skills", {}).get("bat_power", 0), 2),
        "bat_control":    round(p.get("skills", {}).get("bat_control", 0), 2),
        "bat_aggression": round(p.get("skills", {}).get("bat_aggression", 0.5), 2),
        "pressure_handling": round(p.get("mental", {}).get("pressure_handling", 0.5), 2),
        "runs":    bs.get("runs", 0),
        "balls":   bs.get("balls", 0),
    }


def _eligible_bowlers(bowling_order: list, bowl_stats: dict, last_bowler_id) -> list:
    eligible = [
        b for b in bowling_order
        if b["id"] != last_bowler_id
        and bowl_stats.get(b["id"], {}).get("balls", 0) // 6 < MAX_BOWLER_OVERS
    ]
    if not eligible:  # relax consecutive rule
        eligible = [
            b for b in bowling_order
            if bowl_stats.get(b["id"], {}).get("balls", 0) // 6 < MAX_BOWLER_OVERS
        ]
    if not eligible:
        # Every bowler has hit the 4-over quota (thin bowling attack) — let the
        # least-used bowler continue rather than stalling the match.
        by_overs = sorted(bowling_order, key=lambda b: bowl_stats.get(b["id"], {}).get("balls", 0))
        eligible = [b for b in by_overs if b["id"] != last_bowler_id] or by_overs
    return eligible


def init_session(
    batting_xi: list, bowling_xi: list, bowling_order: list,
    user_team: str, bat_team: str, fld_team: str, stadium: dict,
) -> dict:
    bowl_stats: dict = {}
    sess = {
        "user_team":    user_team,
        "bat_team":     bat_team,
        "fld_team":     fld_team,
        "batting_xi":   batting_xi,
        "bowling_xi":   bowling_xi,
        "bowling_order": bowling_order,
        "stadium":      {"id": stadium["id"], "name": stadium["name"], "city": stadium["city"]},
        "inning":       1,
        "runs":         0,
        "wickets":      0,
        "legal_balls":  0,
        "extras":       {"wides": 0, "no_balls": 0},
        "target":       None,
        "complete":     False,
        "result_note":  "",
        "striker_id":   None,
        "non_striker_id": None,
        "next_bat_idx": 0,
        "bat_stats":    {},
        "last_bowler_id": None,
        "bowl_stats":   bowl_stats,
        "fow":          [],
        "ball_log":     [],
        "last_over_balls": [],
        "inn1_data":    None,
        "pending":      "pick_bowler",
        "available_bowlers": [],
        "available_batsmen": [],
        "available_openers": [],
    }
    _start_innings_batting(sess)
    return sess


def _start_innings_batting(sess: dict) -> None:
    """
    Set up who's batting for the innings that's about to start. If the
    user's own team is batting, pause for them to choose their openers;
    otherwise default to the top of the XI as usual.
    """
    batting_xi = sess["batting_xi"]
    if sess["bat_team"] == sess["user_team"]:
        sess["pending"] = "pick_openers"
        sess["available_openers"] = [_ser_batsman(p, {}) for p in batting_xi]
        sess["available_bowlers"] = []
        return

    opener1, opener2 = batting_xi[0], batting_xi[1]
    sess["bat_stats"] = {
        opener1["id"]: {"name": opener1["name"], "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissed": False},
        opener2["id"]: {"name": opener2["name"], "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissed": False},
    }
    sess["striker_id"]     = opener1["id"]
    sess["non_striker_id"] = opener2["id"]
    sess["next_bat_idx"]   = 2
    available = _eligible_bowlers(sess["bowling_order"], sess["bowl_stats"], None)
    sess["available_bowlers"] = [_ser_bowler(b, sess["bowl_stats"]) for b in available]
    sess["available_openers"] = []
    sess["pending"] = "pick_bowler"


def choose_openers(sess: dict, striker_id: str, non_striker_id: str) -> dict:
    """User's team is batting: bring in the two chosen openers."""
    batting_xi = sess["batting_xi"]
    striker     = next((p for p in batting_xi if p["id"] == striker_id), None)
    non_striker = next((p for p in batting_xi if p["id"] == non_striker_id), None)
    if not striker or not non_striker or striker_id == non_striker_id:
        raise ValueError("Pick two different players from the batting XI as openers.")

    # Reorder the XI so the chosen pair occupy the first two slots, then
    # keep the rest of the order unchanged for later batsman promotions.
    rest = [p for p in batting_xi if p["id"] not in (striker_id, non_striker_id)]
    sess["batting_xi"] = [striker, non_striker] + rest

    sess["bat_stats"] = {
        striker["id"]:     {"name": striker["name"],     "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissed": False},
        non_striker["id"]: {"name": non_striker["name"], "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissed": False},
    }
    sess["striker_id"]     = striker["id"]
    sess["non_striker_id"] = non_striker["id"]
    sess["next_bat_idx"]   = 2

    available = _eligible_bowlers(sess["bowling_order"], sess["bowl_stats"], sess["last_bowler_id"])
    sess["available_bowlers"] = [_ser_bowler(b, sess["bowl_stats"]) for b in available]
    sess["available_openers"] = []
    sess["pending"] = "pick_bowler"
    return sess


def simulate_over(sess: dict, bowler_id: str) -> dict:
    """
    Simulate an over; returns updated session (mutates in place).
    If a wicket falls mid-over, simulation stops immediately so the next
    batsman can be chosen — resuming this same over (same bowler, same
    ball count) happens transparently when choose_batsman() calls back in.
    """
    resuming = sess.get("_mid_over") is not None
    if resuming:
        mid           = sess.pop("_mid_over")
        bowler        = mid["bowler"]
        over_num      = mid["over_num"]
        legal_in_over = mid["legal_in_over"]
        over_balls    = mid["over_balls"]
    else:
        bowling_order = sess["bowling_order"]
        bowler = next((b for b in bowling_order if b["id"] == bowler_id), None)
        if not bowler:
            raise ValueError(f"Bowler {bowler_id} not found in bowling order")
        over_num      = sess["legal_balls"] // 6
        legal_in_over = 0
        over_balls    = []

    batting_xi   = sess["batting_xi"]
    bat_stats    = sess["bat_stats"]
    bowl_stats   = sess["bowl_stats"]
    second_innings = sess["target"] is not None

    striker     = next(p for p in batting_xi if p["id"] == sess["striker_id"])
    non_striker = next(p for p in batting_xi if p["id"] == sess["non_striker_id"])

    if bowler["id"] not in bowl_stats:
        bowl_stats[bowler["id"]] = {"name": bowler["name"], "balls": 0, "runs": 0,
                                    "wickets": 0, "wides": 0, "no_balls": 0,
                                    "maidens": 0, "dots": 0, "_over_runs": 0}

    wicket_fell  = False
    need_batsman = False

    while legal_in_over < 6 and not sess["complete"]:
        runs_needed    = (sess["target"] - sess["runs"]) if second_innings else 0
        balls_remaining = max(1, (20 - over_num) * 6 - legal_in_over)

        outcome, _ = ball_outcome(
            batsman=striker, bowler=bowler, over=over_num,
            runs_needed=runs_needed, balls_remaining=balls_remaining,
            second_innings=second_innings, stadium=None,
        )

        striker_runs_before = bat_stats.get(striker["id"], {}).get("runs", 0)
        dismissed_name      = striker["name"]
        line                = ball_commentary(outcome, striker, bowler, striker_runs_before)
        over_str            = f"{over_num}.{legal_in_over}"

        is_extra   = outcome in ("Wd", "Nb")
        is_wicket  = outcome == "W"
        is_legal   = not is_extra

        bowl = bowl_stats[bowler["id"]]

        if is_legal:
            bowl["balls"]       += 1
            sess["legal_balls"] += 1
            legal_in_over       += 1
            if striker["id"] not in bat_stats:
                bat_stats[striker["id"]] = {"name": striker["name"], "runs": 0, "balls": 0,
                                            "fours": 0, "sixes": 0, "dismissed": False}
            bat_stats[striker["id"]]["balls"] += 1

        if is_extra:
            sess["runs"] += 1
            bowl["runs"] += 1
            bowl["_over_runs"] += 1
            if outcome == "Wd":
                bowl["wides"]         += 1
                sess["extras"]["wides"] += 1
            else:
                bowl["no_balls"]          += 1
                sess["extras"]["no_balls"] += 1

        elif is_wicket:
            sess["wickets"] += 1
            bowl["wickets"] += 1
            wicket_fell = True
            if striker["id"] not in bat_stats:
                bat_stats[striker["id"]] = {"name": striker["name"], "runs": 0, "balls": 0,
                                            "fours": 0, "sixes": 0, "dismissed": False}
            bat_stats[striker["id"]]["dismissed"] = True
            sess["fow"].append({
                "n": sess["wickets"], "score": sess["runs"],
                "batsman": dismissed_name, "over": over_str,
            })
            # Pause here for the next batsman to be chosen, rather than
            # silently promoting whoever is next in the default XI order.
            if sess["next_bat_idx"] < len(batting_xi):
                need_batsman = True
            else:
                sess["complete"]    = True
                sess["result_note"] = "all out"

        else:
            runs_scored = int(outcome)
            sess["runs"] += runs_scored
            bowl["runs"] += runs_scored
            bowl["_over_runs"] += runs_scored
            if striker["id"] not in bat_stats:
                bat_stats[striker["id"]] = {"name": striker["name"], "runs": 0, "balls": 0,
                                            "fours": 0, "sixes": 0, "dismissed": False}
            bat_stats[striker["id"]]["runs"] += runs_scored
            if runs_scored == 0: bowl["dots"] += 1
            if runs_scored == 4:  bat_stats[striker["id"]]["fours"] += 1
            if runs_scored == 6:  bat_stats[striker["id"]]["sixes"] += 1
            if runs_scored % 2 == 1:
                striker, non_striker = non_striker, striker
                sess["striker_id"], sess["non_striker_id"] = sess["non_striker_id"], sess["striker_id"]

        # Over boundary: rotate strike (moot if we're about to pause for a batsman pick)
        if is_legal and sess["legal_balls"] % 6 == 0 and not sess["complete"]:
            if bowl["_over_runs"] == 0:
                bowl["maidens"] += 1
            bowl["_over_runs"] = 0
        if not need_batsman and is_legal and sess["legal_balls"] % 6 == 0 and not sess["complete"]:
            striker, non_striker = non_striker, striker
            sess["striker_id"], sess["non_striker_id"] = sess["non_striker_id"], sess["striker_id"]

        # Check completion
        if not sess["complete"]:
            if second_innings and sess["runs"] >= sess["target"]:
                sess["complete"]    = True
                sess["result_note"] = "target reached"
            elif sess["legal_balls"] >= 120:
                sess["complete"]    = True
                sess["result_note"] = "overs complete"

        crr         = round(sess["runs"] / (sess["legal_balls"] / 6), 2) if sess["legal_balls"] else 0
        runs_needed = (sess["target"] - sess["runs"]) if second_innings else None

        over_balls.append({
            "over_str":    over_str,
            "batsman":     dismissed_name if is_wicket else striker["name"],
            "bowler":      bowler["name"],
            "outcome":     outcome,
            "commentary":  line.strip(),
            "runs":        sess["runs"],
            "wickets":     sess["wickets"],
            "crr":         crr,
            "runs_needed": runs_needed,
            "rrr":         round(runs_needed / max(0.1, (120 - sess["legal_balls"]) / 6), 2) if runs_needed else None,
        })
        sess["ball_log"].append(over_balls[-1])

        if need_batsman:
            break  # stop mid-over; resume once a batsman is chosen

    sess["bat_stats"]  = bat_stats
    sess["bowl_stats"] = bowl_stats
    sess["last_over_balls"] = over_balls

    if need_batsman and not sess["complete"]:
        # Pause mid-over: stash bowler/ball-count state so simulate_over() can
        # resume this exact over once choose_batsman() picks the next batsman.
        sess["_mid_over"] = {
            "bowler": bowler, "over_num": over_num,
            "legal_in_over": legal_in_over, "over_balls": over_balls,
        }
        remaining = batting_xi[sess["next_bat_idx"]:]
        sess["available_batsmen"] = [_ser_batsman(p, bat_stats) for p in remaining]
        sess["available_bowlers"] = []
        sess["pending"] = "pick_batsman"
        return sess

    sess["last_bowler_id"] = bowler["id"]

    # Determine next pending decision (over genuinely finished, or innings ended)
    if sess["complete"]:
        sess["pending"] = "innings_break" if sess["inning"] == 1 else "complete"
        sess["available_bowlers"] = []
        sess["available_batsmen"] = []
    else:
        available = _eligible_bowlers(sess["bowling_order"], bowl_stats, sess["last_bowler_id"])
        sess["available_bowlers"] = [_ser_bowler(b, bowl_stats) for b in available]
        sess["available_batsmen"] = []
        sess["pending"] = "pick_bowler"

    return sess


def choose_batsman(sess: dict, batsman_id: str) -> dict:
    """Send in the chosen batsman as the new striker, then resume play."""
    batting_xi = sess["batting_xi"]
    next_idx   = sess["next_bat_idx"]
    remaining  = batting_xi[next_idx:]

    target = next((i for i, p in enumerate(remaining) if p["id"] == batsman_id), None)
    if target is None:
        raise ValueError(f"Batsman {batsman_id} not found in remaining lineup")

    # Swap chosen batsman into the next slot, then bring them to the crease
    if target != 0:
        remaining[0], remaining[target] = remaining[target], remaining[0]
        sess["batting_xi"] = batting_xi[:next_idx] + remaining

    new_bat = sess["batting_xi"][next_idx]
    sess["next_bat_idx"] += 1
    sess["bat_stats"].setdefault(new_bat["id"], {
        "name": new_bat["name"], "runs": 0, "balls": 0,
        "fours": 0, "sixes": 0, "dismissed": False,
    })
    sess["striker_id"] = new_bat["id"]

    if sess.get("_mid_over"):
        # Resume the over that was interrupted by the wicket, same bowler.
        return simulate_over(sess, sess["_mid_over"]["bowler"]["id"])

    # No over was in progress (shouldn't normally happen) — just queue a bowler pick.
    bowl_stats = sess["bowl_stats"]
    available  = _eligible_bowlers(sess["bowling_order"], bowl_stats, sess["last_bowler_id"])
    sess["available_bowlers"] = [_ser_bowler(b, bowl_stats) for b in available]
    sess["available_batsmen"] = []
    sess["pending"] = "pick_bowler"
    return sess


def start_second_innings(sess: dict) -> dict:
    """Flip teams for the 2nd innings."""
    inn1_bat  = sess["bat_team"]
    inn1_fld  = sess["fld_team"]
    target    = sess["runs"] + 1

    # Swap batting / bowling
    new_batting  = sess["bowling_xi"]
    new_bowling  = sess["batting_xi"]
    from engine.ai_manager import build_bowling_order
    new_bowl_order = build_bowling_order(new_bowling)

    # Save inn1 summary
    inn1_data = _build_innings_summary(sess, inn1_bat)

    sess.update({
        "inning":        2,
        "bat_team":      inn1_fld,
        "fld_team":      inn1_bat,
        "batting_xi":    new_batting,
        "bowling_xi":    new_bowling,
        "bowling_order": new_bowl_order,
        "runs":          0,
        "wickets":       0,
        "legal_balls":   0,
        "extras":        {"wides": 0, "no_balls": 0},
        "target":        target,
        "complete":      False,
        "result_note":   "",
        "striker_id":    None,
        "non_striker_id": None,
        "next_bat_idx":  0,
        "bat_stats":     {},
        "last_bowler_id": None,
        "bowl_stats":    {},
        "fow":           [],
        "ball_log":      [],
        "last_over_balls": [],
        "inn1_data":     inn1_data,
        "pending":       "pick_bowler",
        "available_bowlers": [],
        "available_batsmen": [],
        "available_openers": [],
    })
    _start_innings_batting(sess)
    return sess


def _build_innings_summary(sess: dict, team: str) -> dict:
    return {
        "team":       team,
        "runs":       sess["runs"],
        "wickets":    sess["wickets"],
        "overs":      f"{sess['legal_balls'] // 6}.{sess['legal_balls'] % 6}",
        "crr":        round(sess["runs"] / (sess["legal_balls"] / 6), 2) if sess["legal_balls"] else 0,
        "result_note": sess["result_note"],
        "balls":      sess["ball_log"],
        "bat_stats":  [
            {
                "id": pid, "name": s["name"], "runs": s["runs"], "balls": s["balls"],
                "fours": s["fours"], "sixes": s["sixes"],
                "sr": round((s["runs"] / s["balls"]) * 100, 1) if s["balls"] else 0,
                "dismissed": s["dismissed"], "how_out": "out" if s["dismissed"] else "not out",
            }
            for pid, s in sess["bat_stats"].items()
        ],
        "bowl_stats": [
            {
                "id": pid, "name": s["name"],
                "overs": f"{s['balls'] // 6}.{s['balls'] % 6}",
                "runs": s["runs"], "wickets": s["wickets"],
                "wides": s["wides"], "no_balls": s["no_balls"],
                "economy": round(s["runs"] / (s["balls"] / 6), 2) if s["balls"] else 0,
                "maidens": s.get("maidens", 0),
                "dots": s.get("dots", 0),
            }
            for pid, s in sess["bowl_stats"].items()
        ],
        "fow": sess["fow"],
    }


def build_match_result(sess: dict) -> dict:
    """Build final match data dict compatible with scorecard page."""
    inn1 = sess["inn1_data"]
    inn2 = _build_innings_summary(sess, sess["bat_team"])

    if inn2["result_note"] == "target reached":
        ww = 10 - inn2["wickets"]
        result = {"winner": sess["bat_team"], "margin": f"{ww} wicket{'s' if ww != 1 else ''}"}
    elif inn2["runs"] < inn1["runs"]:
        diff = inn1["runs"] - inn2["runs"]
        result = {"winner": inn1["team"], "margin": f"{diff} run{'s' if diff != 1 else ''}"}
    else:
        result = {"winner": None, "margin": "Tied"}

    return {
        "bat_first": inn1["team"],
        "fld_first": sess["bat_team"],
        "stadium":   sess["stadium"],
        "inn1":      inn1,
        "inn2":      inn2,
        "result":    result,
        "interactive": True,
    }


# ── MCP-style suggestion engine ──────────────────────────────────────────────

def suggest_bowler(sess: dict) -> dict:
    """Rank available bowlers for the current game phase and return top suggestion."""
    available = sess.get("available_bowlers", [])
    if not available:
        return {"suggestion": None, "reason": "No eligible bowlers."}

    over      = sess["legal_balls"] // 6
    phase     = _phase(over)
    runs      = sess["runs"]
    wickets   = sess["wickets"]
    balls_left = 120 - sess["legal_balls"]

    def score(b):
        wt = b.get("wicket_threat", 0.5)
        ec = b.get("economy_skill", 0.5)
        ds = b.get("death_skill", 0.5)
        econ_penalty = 0
        if b.get("runs_given", 0) > 0 and b.get("overs_bowled", 0) > 0:
            econ_penalty = min(0.2, (b["runs_given"] / b["overs_bowled"] - 8) / 40)

        if phase == "powerplay":
            return 0.55 * wt + 0.30 * ec + 0.15 * ds - econ_penalty
        elif phase == "middle":
            return 0.30 * wt + 0.50 * ec + 0.20 * ds - econ_penalty
        else:  # death
            return 0.20 * wt + 0.25 * ec + 0.55 * ds - econ_penalty

    ranked = sorted(available, key=score, reverse=True)
    top    = ranked[0]
    s      = score(top)

    phase_reasons = {
        "powerplay": "Powerplay — bowlers with wicket threat can break partnerships early.",
        "middle":    "Middle overs — economy bowlers dry up the run rate.",
        "death":     "Death overs — death specialists contain big hits and yorkers.",
    }

    overs_str = f"{top.get('overs_bowled', 0)} overs bowled"
    reason = (
        f"Phase: {phase.title()} (over {over + 1}). {phase_reasons[phase]} "
        f"{top['name']} rates {round(s * 100)}% for this phase "
        f"(Wkt: {int(top.get('wicket_threat',0)*100)}, "
        f"Eco: {int(top.get('economy_skill',0)*100)}, "
        f"Death: {int(top.get('death_skill',0)*100)} — {overs_str})."
    )

    return {
        "suggestion":    top["id"],
        "player_name":   top["name"],
        "reason":        reason,
        "phase":         phase,
        "ranked":        [{"id": b["id"], "name": b["name"], "score": round(score(b) * 100)} for b in ranked],
    }


def suggest_batsman(sess: dict) -> dict:
    """Rank remaining batsmen and return top suggestion for current situation."""
    batting_xi  = sess["batting_xi"]
    bat_stats   = sess["bat_stats"]
    next_idx    = sess["next_bat_idx"]
    remaining   = batting_xi[next_idx:]

    if not remaining:
        return {"suggestion": None, "reason": "No batsmen remaining."}

    over        = sess["legal_balls"] // 6
    wickets     = sess["wickets"]
    target      = sess["target"]
    runs        = sess["runs"]
    balls_left  = 120 - sess["legal_balls"]
    second_inn  = target is not None

    def score(p):
        sk  = p.get("skills", {})
        mt  = p.get("mental", {})
        bp  = sk.get("bat_power", 0.5)
        bc  = sk.get("bat_control", 0.5)
        ba  = sk.get("bat_aggression", 0.5)
        ph  = mt.get("pressure_handling", 0.5)

        if second_inn and balls_left <= 30:
            # Last 5 overs of chase — need big hitters
            return 0.50 * bp + 0.20 * bc + 0.15 * ba + 0.15 * ph
        elif second_inn:
            rr_needed = (target - runs) / max(1, balls_left / 6)
            if rr_needed > 10:
                return 0.50 * bp + 0.20 * bc + 0.15 * ba + 0.15 * ph
            return 0.25 * bp + 0.45 * bc + 0.15 * ba + 0.15 * ph
        elif over < 10 and wickets < 3:
            return 0.30 * bp + 0.45 * bc + 0.10 * ba + 0.15 * ph
        else:
            return 0.45 * bp + 0.25 * bc + 0.15 * ba + 0.15 * ph

    ranked = sorted(remaining, key=score, reverse=True)
    top    = ranked[0]

    if second_inn:
        rrr = round((target - runs) / max(0.1, balls_left / 6), 1)
        reason = (
            f"Over {over + 1}, chasing {target}, need {target - runs} off {balls_left} balls "
            f"(RRR {rrr}). {top['name']} suits this situation "
            f"(Power: {int(top.get('skills',{}).get('bat_power',0)*100)}, "
            f"Pressure: {int(top.get('mental',{}).get('pressure_handling',0)*100)})."
        )
    else:
        reason = (
            f"Over {over + 1}, score {runs}/{wickets}. "
            f"{'Consolidate with a reliable bat.' if over < 10 else 'Need acceleration — pick an attacking bat.'} "
            f"{top['name']} is the best fit "
            f"(Power: {int(top.get('skills',{}).get('bat_power',0)*100)}, "
            f"Control: {int(top.get('skills',{}).get('bat_control',0)*100)})."
        )

    return {
        "suggestion":  top["id"],
        "player_name": top["name"],
        "reason":      reason,
        "ranked": [{"id": p["id"], "name": p["name"], "score": round(score(p) * 100)} for p in ranked],
    }
