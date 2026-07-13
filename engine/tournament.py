"""
tournament.py
IPL 2026 tournament: 70-match group stage (10 teams x 14 games each),
top-4 playoffs: Qualifier 1, Eliminator, Qualifier 2, Final.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

TEAMS = ["CSK", "DC", "GT", "KKR", "LSG", "MI", "PBKS", "RCB", "RR", "SRH"]

# team -> home stadium id (matches cricket_stadiums.json)
TEAM_STADIUM: dict[str, int] = {
    "CSK":  1,   # Chepauk, Chennai
    "MI":   2,   # Wankhede, Mumbai
    "KKR":  3,   # Eden Gardens, Kolkata
    "RCB":  4,   # Chinnaswamy, Bengaluru
    "DC":   5,   # Arun Jaitley, Delhi
    "SRH":  6,   # Rajiv Gandhi, Hyderabad
    "GT":  11,   # Narendra Modi Stadium, Ahmedabad
    "LSG": 12,   # Ekana Cricket Stadium, Lucknow
    "PBKS": 13,  # Maharaja Yadavindra Singh Stadium, Mullanpur
    "RR":  14,   # Sawai Mansingh Stadium, Jaipur
}


@dataclass
class MatchResult:
    match_num: int
    team1: str
    team2: str
    winner: Optional[str] = None
    team1_runs: int = 0
    team1_wickets: int = 0
    team1_overs: float = 20.0
    team2_runs: int = 0
    team2_wickets: int = 0
    team2_overs: float = 20.0
    margin_str: str = ""

    def one_liner(self) -> str:
        if self.winner:
            return (
                f"Match {self.match_num:>2}: {self.team1} {self.team1_runs}/{self.team1_wickets} "
                f"vs {self.team2} {self.team2_runs}/{self.team2_wickets} "
                f"-- {self.winner} won by {self.margin_str}"
            )
        return (
            f"Match {self.match_num:>2}: {self.team1} {self.team1_runs}/{self.team1_wickets} "
            f"vs {self.team2} {self.team2_runs}/{self.team2_wickets} -- Tied"
        )


@dataclass
class TeamStanding:
    team: str
    played: int = 0
    won: int = 0
    lost: int = 0
    tied: int = 0
    points: int = 0
    runs_scored: int = 0
    overs_faced: float = 0.0
    runs_conceded: int = 0
    overs_bowled: float = 0.0

    @property
    def nrr(self) -> float:
        if self.overs_faced == 0 or self.overs_bowled == 0:
            return 0.0
        return round(
            (self.runs_scored / self.overs_faced)
            - (self.runs_conceded / self.overs_bowled),
            3,
        )


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

def generate_schedule(teams: list[str]) -> list[list[dict]]:
    """
    Return 14 rounds of 5 matches each (70 total).
    Rounds 1-9: full round-robin (polygon rotation, 45 unique pairs).
    Rounds 10-14: repeat rounds 1-5 with home/away swapped (25 rematches).
    """
    n = len(teams)  # 10
    pool = list(teams)
    rounds: list[list[dict]] = []
    match_counter = 1

    def one_round(arr: list[str], round_num: int, swap: bool) -> list[dict]:
        nonlocal match_counter
        half = len(arr) // 2
        ms = []
        for i in range(half):
            a, b = arr[i], arr[n - 1 - i]
            if swap:
                a, b = b, a
            ms.append({
                "match_num": match_counter,
                "round": round_num,
                "team1": a,
                "team2": b,
                "played": False,
                "result": None,
            })
            match_counter += 1
        return ms

    current = list(pool)
    saved: list[list[dict]] = []
    for r in range(n - 1):          # 9 rounds
        rnd = one_round(current, r + 1, swap=False)
        rounds.append(rnd)
        saved.append(rnd)
        # polygon rotate: fix index-0, move last to index-1
        current = [current[0]] + [current[-1]] + current[1:-1]

    for r in range(5):              # 5 rematch rounds
        orig = saved[r]
        rnd = [
            {
                "match_num": match_counter + i,
                "round": 9 + r + 1,
                "team1": m["team2"],
                "team2": m["team1"],
                "played": False,
                "result": None,
            }
            for i, m in enumerate(orig)
        ]
        match_counter += len(rnd)
        rounds.append(rnd)

    return rounds


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def init_standings(teams: list[str]) -> dict[str, TeamStanding]:
    return {t: TeamStanding(team=t) for t in teams}


def update_standings(standings: dict[str, TeamStanding], result: MatchResult):
    t1 = standings[result.team1]
    t2 = standings[result.team2]
    t1.played += 1
    t2.played += 1

    o1 = min(result.team1_overs, 20.0)
    o2 = min(result.team2_overs, 20.0)
    t1.runs_scored   += result.team1_runs;  t1.overs_faced  += o1
    t1.runs_conceded += result.team2_runs;  t1.overs_bowled += o2
    t2.runs_scored   += result.team2_runs;  t2.overs_faced  += o2
    t2.runs_conceded += result.team1_runs;  t2.overs_bowled += o1

    if result.winner == result.team1:
        t1.won += 1; t1.points += 2; t2.lost += 1
    elif result.winner == result.team2:
        t2.won += 1; t2.points += 2; t1.lost += 1
    else:
        t1.tied += 1; t1.points += 1
        t2.tied += 1; t2.points += 1


def sorted_standings(standings: dict[str, TeamStanding]) -> list[TeamStanding]:
    return sorted(standings.values(), key=lambda s: (-s.points, -s.nrr, -s.won))


def get_top_4(standings: dict[str, TeamStanding]) -> list[str]:
    return [s.team for s in sorted_standings(standings)[:4]]


def print_standings(standings: dict[str, TeamStanding], highlight: str = ""):
    table = sorted_standings(standings)
    print(f"\n  {'#':<3} {'TEAM':<6} {'P':>3} {'W':>3} {'L':>3} {'T':>3} {'PTS':>4} {'NRR':>8}")
    print(f"  {'-'*44}")
    for i, s in enumerate(table, 1):
        q = "  <-- Qualifier" if i <= 4 else ""
        me = " *" if s.team == highlight else "  "
        print(
            f"  {i:<3}{me}{s.team:<6} {s.played:>3} {s.won:>3} {s.lost:>3} "
            f"{s.tied:>3} {s.points:>4} {s.nrr:>+8.3f}{q}"
        )
    print()


# ---------------------------------------------------------------------------
# Playoffs
# ---------------------------------------------------------------------------

def build_playoff_bracket(top4: list[str]) -> list[dict]:
    """Return 4 playoff match stubs. Q2/Final teams filled in after earlier results."""
    return [
        {"name": "Qualifier 1", "team1": top4[0], "team2": top4[1], "winner": None},
        {"name": "Eliminator",  "team1": top4[2], "team2": top4[3], "winner": None},
        {"name": "Qualifier 2", "team1": None,    "team2": None,    "winner": None},
        {"name": "Final",       "team1": None,    "team2": None,    "winner": None},
    ]
