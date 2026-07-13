"""
commentary.py
Generates ball-by-ball commentary text. Keeps a pool of varied
phrases per outcome so consecutive balls don't sound identical.
"""

import random

_DOT_LINES = [
    "Dot ball. {bowler} beats {batsman} outside off.",
    "Good length delivery, {batsman} defends solidly. No run.",
    "{bowler} gets one to skid through, {batsman} plays and misses. Dot.",
    "Tight line from {bowler}. {batsman} can't find a gap.",
    "Superb delivery! {bowler} induces a false shot. Dot ball.",
]

_SINGLE_LINES = [
    "{batsman} nudges it fine leg for a single.",
    "Pushed to mid-on, they scamper through for one.",
    "{batsman} works it off the pads, rotates strike.",
    "Gentle push to covers — single taken.",
    "Tucked away to square leg. Quick single.",
]

_DOUBLE_LINES = [
    "{batsman} drives to long-off — 2 runs.",
    "Good running between the wickets, 2 completed.",
    "{batsman} punches through cover, they come back for two.",
    "Placed perfectly into the gap — 2 runs.",
]

_TRIPLE_LINES = [
    "Three runs! Poor outfield work lets them get three.",
    "{batsman} drives hard, misfield at long-off — 3 runs!",
    "Three! Excellent running by {batsman}.",
]

_FOUR_LINES = [
    "FOUR! {batsman} drives {bowler} through the covers beautifully.",
    "FOUR! {batsman} pulls it hard to the mid-wicket boundary.",
    "FOUR! Cracking cut shot from {batsman}!",
    "FOUR! {bowler} overpitches and {batsman} punishes it!",
    "FOUR! Whipped off the pads, races to the boundary.",
    "FOUR! {batsman} finds the gap between cover and point perfectly.",
]

_SIX_LINES = [
    "SIX! {batsman} launches {bowler} into the stands!",
    "SIX! Maximum! {batsman} goes downtown!",
    "SIX! Huge hit from {batsman} — right out of the ground!",
    "SIX! {batsman} picks the length early and clears the rope!",
    "SIX! {bowler} bowls full and {batsman} absolutely murders it!",
    "SIX! Over long-on — effortless power from {batsman}!",
]

_WICKET_LINES = [
    "OUT! {batsman} is gone! {bowler} strikes!",
    "WICKET! {batsman} departs for {runs} runs. Huge blow!",
    "OUT! {bowler} is pumped up! {batsman} walks back.",
    "That's out! {batsman} couldn't handle that one from {bowler}.",
    "GONE! {batsman} top-edges and it's taken. {bowler} gets the breakthrough!",
]

_WIDE_LINES = [
    "Wide! {bowler} drifts it down leg. Extra run.",
    "Wide signalled. {bowler} loses his line.",
    "Wide ball — {bowler} sprays it outside off stump.",
]

_NOBALL_LINES = [
    "No-ball! {bowler} oversteps. Free hit coming up!",
    "No-ball called — front foot gone over the line. Free hit!",
]


_POOL = {
    "0":  _DOT_LINES,
    "1":  _SINGLE_LINES,
    "2":  _DOUBLE_LINES,
    "3":  _TRIPLE_LINES,
    "4":  _FOUR_LINES,
    "6":  _SIX_LINES,
    "W":  _WICKET_LINES,
    "Wd": _WIDE_LINES,
    "Nb": _NOBALL_LINES,
}


def ball_commentary(
    outcome: str,
    batsman: dict,
    bowler: dict,
    batsman_runs: int = 0,
) -> str:
    pool = _POOL.get(outcome, ["Ball bowled."])
    template = random.choice(pool)
    return template.format(
        batsman=batsman["name"],
        bowler=bowler["name"],
        runs=batsman_runs,
    )


def over_summary(over_num: int, runs_in_over: int, wickets_in_over: int, bowler: dict) -> str:
    parts = [f"End of over {over_num + 1}. {bowler['name']} bowled."]
    parts.append(f"{runs_in_over} run{'s' if runs_in_over != 1 else ''} from the over.")
    if wickets_in_over:
        parts.append(f"{wickets_in_over} wicket{'s' if wickets_in_over > 1 else ''} taken.")
    return " ".join(parts)
