# mypy: disable-error-code="no-untyped-call"
"""Adapt validated saved inputs to the unchanged RoadToTheFinal engine."""

from typing import Any

from football.engine import Match, Team
from football.report import report
from schemas.engine import TeamStats
from schemas.prediction import PredictionInputs


def predict_inputs(inputs: PredictionInputs) -> dict[str, Any]:
    return predict_state(
        inputs.model_dump(), extra_minute=inputs.extra_minute, status=inputs.status
    )


def predict_state(
    values: dict[str, Any], *, extra_minute: int = 0, status: str = ""
) -> dict[str, Any]:
    """Calculate from copied, validated inputs without persistence or data lookups."""
    teams = []
    for side in (1, 2):
        prefix = f"team{side}_"
        team = Team(
            name=values[prefix + "name"],
            **{
                field: values[prefix + field]
                for field in ("offense", "defense", "form", "star_power", "clutch", "fifa_rank")
            },
        )
        for field in TeamStats.model_fields:
            if field != "modifiers":
                setattr(team, field, values[prefix + field])
        # Scenario stores the explicit sum. Engine performs its original event-score cap.
        total = values[prefix + "modifier_total"]
        if total:
            team.add_modifier("Saved scenario modifier total", total)
        teams.append(team)
    match = Match(teams[0], teams[1], match_minute=values["match_minute"])
    match.match_extra_minute = extra_minute
    match.match_status_short = status
    return report(match)
