"""
match_state.py
Tracks everything that changes ball-by-ball during an innings:
  - Score, wickets, overs, balls
  - Who is batting (striker / non-striker) and who is bowling
  - Per-batsman stats (runs, balls, 4s, 6s)
  - Per-bowler stats (overs, runs, wickets, wides, no-balls)
  - Partnerships and fall of wickets
  - Required run rate (second innings)
"""

from dataclasses import dataclass, field
from typing import Optional


# -------------------------------------------------------------------
# Per-player stat trackers
# -------------------------------------------------------------------

@dataclass
class BatsmanInnings:
    player: dict
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    dismissed: bool = False
    dismissal: str = ""          # e.g. "caught", "bowled", "lbw"

    @property
    def strike_rate(self) -> float:
        return round((self.runs / self.balls) * 100, 1) if self.balls else 0.0

    @property
    def name(self) -> str:
        return self.player["name"]


@dataclass
class BowlerInnings:
    player: dict
    balls: int = 0
    runs: int = 0
    wickets: int = 0
    wides: int = 0
    no_balls: int = 0
    maidens: int = 0
    dots: int = 0
    _current_over_runs: int = 0  # tracks runs in current over for maiden calc

    @property
    def overs_str(self) -> str:
        return f"{self.balls // 6}.{self.balls % 6}"

    @property
    def economy(self) -> float:
        overs = self.balls / 6
        return round(self.runs / overs, 2) if overs else 0.0

    @property
    def name(self) -> str:
        return self.player["name"]

    def over_complete(self):
        """Call at end of each over to check for maiden."""
        if self._current_over_runs == 0:
            self.maidens += 1
        self._current_over_runs = 0


@dataclass
class Partnership:
    bat1_name: str
    bat2_name: str
    runs: int = 0
    balls: int = 0


@dataclass
class FallOfWicket:
    wicket_num: int
    score: int
    over: int
    ball: int
    batsman_name: str
    runs_scored: int
    dismissal: str


# -------------------------------------------------------------------
# Main innings state
# -------------------------------------------------------------------

class InningsState:
    def __init__(
        self,
        batting_xi: list[dict],
        bowling_xi: list[dict],
        target: Optional[int] = None,
        max_overs: int = 20,
        pick_batsman_fn=None,
    ):
        self.batting_xi   = batting_xi
        self.bowling_xi   = bowling_xi
        self.target       = target          # set in 2nd innings
        self.max_overs    = max_overs
        self.second_innings = target is not None

        # Ball counters
        self.legal_balls  = 0              # only legal deliveries count toward overs
        self.total_balls  = 0              # all deliveries including extras

        # Score
        self.runs         = 0
        self.wickets      = 0
        self.extras       = {"wides": 0, "no_balls": 0}

        # Batsmen
        self._next_bat_idx = 2             # 0=striker, 1=non-striker already in
        self.bat_stats: dict[str, BatsmanInnings] = {}

        # Bowler
        self.bowl_stats: dict[str, BowlerInnings] = {}
        self.current_bowler: Optional[dict] = None

        # Partnerships / FoW
        self.partnerships: list[Partnership] = []
        self.fow: list[FallOfWicket] = []
        self._current_partnership: Optional[Partnership] = None

        self._init_openers()

        # Innings status
        self.complete = False
        self.result_note = ""             # e.g. "all out", "target reached", "overs done"

        # Ball-by-ball log for API / frontend replay
        self.ball_log: list = []

        # Optional user-control callbacks
        self.pick_batsman_fn = pick_batsman_fn

    # -------------------------------------------------------------------
    # Setup
    # -------------------------------------------------------------------

    def _init_openers(self):
        opener1 = self.batting_xi[0]
        opener2 = self.batting_xi[1]
        self.striker     = opener1
        self.non_striker = opener2
        self.bat_stats[opener1["id"]] = BatsmanInnings(opener1)
        self.bat_stats[opener2["id"]] = BatsmanInnings(opener2)
        self._current_partnership = Partnership(opener1["name"], opener2["name"])

    # -------------------------------------------------------------------
    # Ball processing
    # -------------------------------------------------------------------

    def apply_outcome(self, outcome: str, bowler: dict):
        """
        Apply a ball outcome to the match state.
        outcome: '0','1','2','3','4','6','W','Wd','Nb'
        """
        self.current_bowler = bowler
        bowl = self._get_bowl_stat(bowler)
        striker_stat = self.bat_stats[self.striker["id"]]

        is_extra   = outcome in ("Wd", "Nb")
        is_wicket  = outcome == "W"
        is_legal   = not is_extra

        # --- Bowler ball count ---
        if is_legal:
            bowl.balls += 1
            self.legal_balls += 1
            striker_stat.balls += 1
        else:
            # Wides / no-balls still count as a delivery bowled (total_balls)
            if outcome == "Wd":
                bowl.wides += 1
                self.extras["wides"] += 1
            else:
                bowl.no_balls += 1
                self.extras["no_balls"] += 1

        self.total_balls += 1

        # --- Runs ---
        if is_extra:
            runs_scored = 1          # penalty run for wide / no-ball
            self.runs += runs_scored
            bowl.runs += runs_scored
            bowl._current_over_runs += runs_scored
            if self._current_partnership:
                self._current_partnership.runs += runs_scored
                self._current_partnership.balls += 0   # extras don't count as partnership balls

        elif is_wicket:
            runs_scored = 0
            striker_stat.dismissed = True
            striker_stat.dismissal = "out"
            self.wickets += 1

            self.fow.append(FallOfWicket(
                wicket_num=self.wickets,
                score=self.runs,
                over=self.current_over,
                ball=self.ball_in_over,
                batsman_name=self.striker["name"],
                runs_scored=striker_stat.runs,
                dismissal="out",
            ))

            bowl.wickets += 1
            bowl.runs += 0

            # Close current partnership
            if self._current_partnership:
                self.partnerships.append(self._current_partnership)

            # Bring in next batsman
            if self._next_bat_idx < len(self.batting_xi):
                remaining = self.batting_xi[self._next_bat_idx:]
                if self.pick_batsman_fn and len(remaining) > 1:
                    chosen = self.pick_batsman_fn(remaining, self)
                    chosen_pos = self._next_bat_idx + remaining.index(chosen)
                    if chosen_pos != self._next_bat_idx:
                        self.batting_xi[self._next_bat_idx], self.batting_xi[chosen_pos] = (
                            self.batting_xi[chosen_pos], self.batting_xi[self._next_bat_idx]
                        )
                new_bat = self.batting_xi[self._next_bat_idx]
                self._next_bat_idx += 1
                self.bat_stats[new_bat["id"]] = BatsmanInnings(new_bat)
                self.striker = new_bat
                self._current_partnership = Partnership(
                    self.striker["name"], self.non_striker["name"]
                )
            else:
                self.complete = True
                self.result_note = "all out"
                if self._current_partnership:
                    self.partnerships.append(self._current_partnership)

        else:
            runs_scored = int(outcome)
            self.runs += runs_scored
            bowl.runs += runs_scored
            bowl._current_over_runs += runs_scored
            striker_stat.runs += runs_scored
            if runs_scored == 0:
                bowl.dots += 1
            elif runs_scored == 4:
                striker_stat.fours += 1
            elif runs_scored == 6:
                striker_stat.sixes += 1
            if self._current_partnership:
                self._current_partnership.runs += runs_scored
                self._current_partnership.balls += 1

        # --- Strike rotation ---
        if is_legal and not is_wicket:
            if runs_scored % 2 == 1:
                self._rotate_strike()
        # On wide/no-ball, no rotation (batter gets a free delivery)

        # --- Over boundary ---
        if is_legal and self.legal_balls % 6 == 0 and self.legal_balls > 0:
            bowl.over_complete()
            # Swap strike at end of over
            self._rotate_strike()

        # --- Check innings end conditions ---
        if not self.complete:
            if self.wickets >= 10:
                self.complete = True
                self.result_note = "all out"
                if self._current_partnership:
                    self.partnerships.append(self._current_partnership)
                    self._current_partnership = None
            elif self.current_over >= self.max_overs:
                self.complete = True
                self.result_note = "overs complete"
                if self._current_partnership:
                    self.partnerships.append(self._current_partnership)
                    self._current_partnership = None

        # --- Second innings: target check ---
        if self.second_innings and not self.complete:
            if self.runs >= self.target:
                self.complete = True
                self.result_note = "target reached"
                if self._current_partnership:
                    self.partnerships.append(self._current_partnership)
                    self._current_partnership = None

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _rotate_strike(self):
        self.striker, self.non_striker = self.non_striker, self.striker

    def _get_bowl_stat(self, bowler: dict) -> BowlerInnings:
        bid = bowler["id"]
        if bid not in self.bowl_stats:
            self.bowl_stats[bid] = BowlerInnings(bowler)
        return self.bowl_stats[bid]

    # -------------------------------------------------------------------
    # Context properties (used by probability engine each ball)
    # -------------------------------------------------------------------

    @property
    def current_over(self) -> int:
        """0-indexed current over number."""
        return self.legal_balls // 6

    @property
    def ball_in_over(self) -> int:
        """Ball number within the current over (1-6)."""
        return (self.legal_balls % 6) + 1

    @property
    def balls_remaining(self) -> int:
        return max(0, self.max_overs * 6 - self.legal_balls)

    @property
    def runs_needed(self) -> int:
        if self.target is None:
            return 0
        return max(0, self.target - self.runs)

    @property
    def run_rate(self) -> float:
        overs = self.legal_balls / 6
        return round(self.runs / overs, 2) if overs else 0.0

    @property
    def required_run_rate(self) -> float:
        overs_left = self.balls_remaining / 6
        if overs_left <= 0:
            return 0.0
        return round(self.runs_needed / overs_left, 2)

    @property
    def over_str(self) -> str:
        return f"{self.current_over}.{self.legal_balls % 6}"

    def score_str(self) -> str:
        return f"{self.runs}/{self.wickets}"
