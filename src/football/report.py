"""Serialize legacy or corrected predictions without persistence or recalculation on reads."""

from typing import Any


def report(match: Any) -> dict[str, Any]:
    p1, draw, p2, score, scorelines = match.calculate_probabilities()
    advance1, advance2 = match.advancement_probabilities((p1, draw, p2))
    xg1, xg2 = match.expected_goals()
    momentum1, momentum2 = match.live_momentum_percentages()
    confidence, label, _ = match.prediction_confidence((p1, draw, p2))
    corrected = getattr(match, "regulation_horizon", False)
    reasons = match.reasoning_summary()
    if corrected:
        # The reference engine's time sentence does not describe outside-horizon summaries.
        old_time_reason = (
            f"The model is calculating remaining goals from minute {match.match_minute}."
        )
        reasons = [
            f"Supplied hypothetical state: {reason}"
            for reason in reasons
            if reason != old_time_reason
        ]
        reasons.extend(
            [
                "Team ratings and match statistics are user-provided hypothetical inputs. "
                "Historical browsing does not automatically supply these ratings.",
                "Predictions are calculated estimates, not recorded historical match results.",
                (
                    f"The model estimates additional goals from minute {match.match_minute} "
                    "through the nominal 90-minute horizon."
                    if match.match_minute < 90
                    else f"No future match period is modeled at minute {match.match_minute}. "
                    "This result summarizes the supplied current score; it does not confirm "
                    "an actual final result or reconstruct the minute-90 score."
                ),
                "Stoppage time, extra time, and penalty shootouts are not forecast.",
                "Preview status and extra_minute are metadata; they do not establish match "
                "completion, a match phase, or a supported future prediction horizon.",
                "Confidence is a heuristic based on the margin between the two leading "
                "outcome probabilities, not measured prediction accuracy.",
                "Advancement uses a hypothetical clutch-weighted tiebreak assumption when "
                "the modeled score is tied (equal shares if both clutch ratings are zero); "
                "it is not a recorded shootout outcome.",
                "For calculation, total shots are normalized upward to shots on target when "
                "shots on target exceed submitted shots. Prediction does not modify the scenario.",
            ]
        )
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
        "reasoning": reasons,
        "model": (
            "road-to-the-final-heuristic-v2" if corrected else "road-to-the-final-heuristic-v1"
        ),
    }
