# mypy: disable-error-code="no-untyped-call"
"""Adapt validated saved inputs to the unchanged RoadToTheFinal engine."""

from typing import Any

from football.engine import Match, Team
from schemas.football import TeamStats
from schemas.predictions import PredictionInputs
from services.football import report


def predict_inputs(inputs: PredictionInputs) -> dict[str, Any]:
    values = inputs.model_dump()
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
    match = Match(teams[0], teams[1], match_minute=inputs.match_minute)
    match.match_extra_minute = inputs.extra_minute
    match.match_status_short = inputs.status
    return report(match)
