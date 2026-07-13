"""
toss.py — stateless coin-flip toss resolution, used by the web API.
"""
import random


def flip_toss(caller_team: str, opponent_team: str, call: str, stadium: dict) -> dict:
    """
    Flip a coin against the caller's heads/tails call.
    If the caller loses, the AI (opponent) decides bat/bowl using the
    stadium's toss_decision_bias, and bat_first_team is resolved immediately.
    If the caller wins, bat_first_team is left None — the frontend resolves
    it once the caller picks bat or field.
    """
    coin     = random.choice(["heads", "tails"])
    user_won = call.lower() == coin

    result = {
        "coin_result":    coin,
        "user_call":      call.lower(),
        "user_won_toss":  user_won,
        "toss_winner":    caller_team if user_won else opponent_team,
        "ai_decision":    None,
        "bat_first_team": None,
    }

    if not user_won:
        bias     = stadium.get("toss_decision_bias", "bat first")
        ai_bats  = (bias == "bat first")
        result["ai_decision"]    = "bat" if ai_bats else "bowl"
        result["bat_first_team"] = opponent_team if ai_bats else caller_team

    return result
