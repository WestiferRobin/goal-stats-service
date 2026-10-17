"""Pure serialization of the unchanged reference prediction calculations."""

from typing import Any


def report(match: Any) -> dict[str, Any]:
    p1, draw, p2, score, scorelines = match.calculate_probabilities()
    advance1, advance2 = match.advancement_probabilities((p1, draw, p2))
    xg1, xg2 = match.expected_goals()
    momentum1, momentum2 = match.live_momentum_percentages()
    confidence, label, _ = match.prediction_confidence((p1, draw, p2))
    return {
        "team1": match.team1.name,
        "team2": match.team2.name,
        "minute": match.match_minute,
        "status": match.match_status_short,
        "probabilities": {"team1": p1, "draw": draw, "team2": p2},
        "advancement": {"team1": advance1, "team2": advance2},
        "expected_goals_remaining": {"team1": xg1, "team2": xg2},
        "momentum_percent": {"team1": momentum1, "team2": momentum2},
        "most_likely_score": list(score),
        "top_scorelines": scorelines,
        "confidence": {"percent": confidence, "label": label},
        "reasoning": match.reasoning_summary(),
        "model": "road-to-the-final-heuristic-v1",
    }
