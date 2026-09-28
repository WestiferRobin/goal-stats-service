# mypy: disable-error-code="no-untyped-call"
"""All football operations execute in this process against the shared database."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from werkzeug.exceptions import NotFound

from football.engine import Match, Team, simulate_tournament
from football.historical import apply_historical_row_to_match
from infra.resources.db import Database
from models.football import FootballHistory, FootballSnapshot, FootballTeam
from schemas.football import PredictionRequest, TournamentRequest


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


class FootballService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def teams(self) -> list[dict[str, Any]]:
        with self.database.transaction() as session:
            return [
                row.ratings
                for row in session.scalars(select(FootballTeam).order_by(FootballTeam.name))
            ]

    def team(self, name: str) -> Any:
        ratings = next(
            (r for r in self.teams() if r["name"].casefold() == name.strip().casefold()), None
        )
        if ratings is None:
            raise NotFound("Team not found; import the football datasets first")
        return Team(**ratings)

    def match(self, request: PredictionRequest) -> Any:
        teams = [self.team(request.team1), self.team(request.team2)]
        for team, stats in zip(teams, [request.team1_stats, request.team2_stats], strict=True):
            for key, value in stats.model_dump(exclude={"modifiers"}).items():
                setattr(team, key, value)
            team.shots = max(team.shots, team.shots_on_target)
            for modifier in stats.modifiers:
                team.add_modifier(modifier.reason, modifier.value)
        match = Match(teams[0], teams[1], match_minute=request.minute)
        match.match_extra_minute = request.extra_minute
        match.match_status_short = request.status.upper()
        return match

    def predict(self, request: PredictionRequest) -> dict[str, Any]:
        return report(self.match(request))

    def save(self, request: PredictionRequest) -> dict[str, Any]:
        prediction = self.predict(request)
        with self.database.transaction() as session:
            row = FootballSnapshot(
                team1=prediction["team1"],
                team2=prediction["team2"],
                state=request.model_dump(mode="json"),
                prediction=prediction,
            )
            session.add(row)
            session.flush()
            return {
                "id": str(row.id),
                "created_at": row.created_at.isoformat(),
                "state": row.state,
                "prediction": prediction,
            }

    def snapshot(self, snapshot_id: UUID) -> dict[str, Any]:
        with self.database.transaction() as session:
            row = session.get(FootballSnapshot, snapshot_id)
            if row is None:
                raise NotFound()
            return {
                "id": str(row.id),
                "created_at": row.created_at.isoformat(),
                "state": row.state,
                "prediction": row.prediction,
            }

    def snapshots(self, team1: str, team2: str, limit: int, offset: int) -> list[dict[str, Any]]:
        first, second = self.team(team1).name, self.team(team2).name
        with self.database.transaction() as session:
            rows = session.scalars(
                select(FootballSnapshot)
                .where(FootballSnapshot.team1 == first, FootballSnapshot.team2 == second)
                .order_by(FootballSnapshot.created_at.desc(), FootballSnapshot.id)
                .limit(limit)
                .offset(offset)
            )
            return [
                {
                    "id": str(row.id),
                    "created_at": row.created_at.isoformat(),
                    "state": row.state,
                    "prediction": row.prediction,
                }
                for row in rows
            ]

    def history(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self.database.transaction() as session:
            rows = session.scalars(
                select(FootballHistory)
                .order_by(FootballHistory.source, FootballHistory.source_row)
                .limit(limit)
                .offset(offset)
            )
            return [{"id": row.id, "source": row.source, **row.data} for row in rows]

    def backtest(self) -> dict[str, Any]:
        with self.database.transaction() as session:
            rows = list(session.scalars(select(FootballHistory).order_by(FootballHistory.id)))
        results = []
        skipped = 0
        for row in rows:
            winner = row.data.get("actual_winner")
            if not winner:
                skipped += 1
                continue
            match = Match(self.team(row.team1), self.team(row.team2))
            pregame = report(match)
            apply_historical_row_to_match(match, row.data)
            historical = report(match)

            def predicted(result: dict[str, Any]) -> str:
                return str(
                    result["team1"]
                    if result["advancement"]["team1"] >= result["advancement"]["team2"]
                    else result["team2"]
                )

            results.append(
                {
                    "id": row.id,
                    "actual_winner": winner,
                    "has_snapshot": bool(row.data.get("snapshot_minute")),
                    "pregame_correct": predicted(pregame) == winner,
                    "snapshot_correct": predicted(historical) == winner,
                }
            )
        labeled_snapshots = [r for r in results if r["has_snapshot"]]
        return {
            "evaluated": len(results),
            "skipped_unlabeled": skipped,
            "pregame_correct": sum(r["pregame_correct"] for r in results),
            "snapshots_evaluated": len(labeled_snapshots),
            "snapshot_correct": sum(r["snapshot_correct"] for r in labeled_snapshots),
            "results": results,
        }

    def tournament(self, request: TournamentRequest) -> dict[str, Any]:
        results, champion, count, final = simulate_tournament(
            [self.team(name) for name in request.teams], request.simulations
        )
        return {
            "results": results,
            "predicted_champion": champion,
            "simulations": count,
            "most_common_final": final,
            "probability_unit": "percent",
        }

    def insights(self, team1: str, team2: str) -> dict[str, Any]:
        first, second = self.team(team1).name, self.team(team2).name
        with self.database.transaction() as session:
            rows = list(
                session.scalars(
                    select(FootballHistory)
                    .where(FootballHistory.source == "match_history.csv")
                    .order_by(FootballHistory.source_row)
                )
            )
        completed = [r.data for r in rows if r.data.get("actual_winner")]
        meetings = [r for r in completed if {r["team1"], r["team2"]} == {first, second}]
        return {
            "source": "imported_csv",
            "head_to_head": meetings,
            "team1_history": [r for r in completed if first in {r["team1"], r["team2"]}],
            "team2_history": [r for r in completed if second in {r["team1"], r["team2"]}],
            "note": "Source rows have no match dates; ordering is CSV order, not recent form.",
        }

    def live(self, team1: str, team2: str) -> dict[str, Any]:
        from pydantic import ValidationError
        from werkzeug.exceptions import ServiceUnavailable

        from football.live import get_real_live_data
        from schemas.football import TeamStats

        first, second = self.team(team1).name, self.team(team2).name
        request = None
        data = None
        try:
            data = get_real_live_data(first, second)
            if data is not None:
                stats = []
                for side in (1, 2):
                    values = {
                        key: data.get(f"team{side}_{'total_shots' if key == 'shots' else key}", 0)
                        for key in TeamStats.model_fields
                        if key not in {"modifiers", "possession"}
                    }
                    values["possession"] = (
                        data["team1_possession"] if side == 1 else 100 - data["team1_possession"]
                    )
                    stats.append(TeamStats.model_validate(values))
                request = PredictionRequest(
                    team1=first,
                    team2=second,
                    minute=data["match_minute"],
                    extra_minute=data["match_extra_minute"],
                    status=data["match_status_short"],
                    team1_stats=stats[0],
                    team2_stats=stats[1],
                )
        except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
            request = None
        if request is None:
            with self.database.transaction() as session:
                previous = session.scalar(
                    select(FootballSnapshot)
                    .where(
                        FootballSnapshot.team1 == first,
                        FootballSnapshot.team2 == second,
                        FootballSnapshot.prediction["source"].as_string() == "real",
                    )
                    .order_by(FootballSnapshot.created_at.desc())
                    .limit(1)
                )
                if previous is not None:
                    return {
                        "id": str(previous.id),
                        "source": "cached",
                        "observed_at": previous.created_at.isoformat(),
                        "state": previous.state,
                        "prediction": previous.prediction,
                    }
            raise ServiceUnavailable("No real live data available")
        assert data is not None
        prediction = {
            **self.predict(request),
            "source": "real",
            "events": data.get("event_timeline", []),
        }
        with self.database.transaction() as session:
            row = FootballSnapshot(
                team1=first,
                team2=second,
                state=request.model_dump(mode="json"),
                prediction=prediction,
            )
            session.add(row)
            session.flush()
            return {
                "id": str(row.id),
                "source": "real",
                "observed_at": row.created_at.isoformat(),
                "state": row.state,
                "prediction": prediction,
            }
