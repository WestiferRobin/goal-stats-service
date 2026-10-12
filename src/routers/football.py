"""JSON API shared by React, Wix server code, and other clients."""

from flask import Response, jsonify, url_for
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from exceptions.handlers import object_body
from routers.openapi import errors
from schemas.common import HistoryQuery
from schemas.competition import CatalogCompetitionsResponse
from schemas.engine import PredictionResponse
from schemas.football import (
    Matchup,
    PredictionRequest,
    SnapshotPath,
    SnapshotQuery,
    TournamentRequest,
)
from schemas.match import (
    CatalogMatchesResponse,
    CatalogMatchPath,
    CatalogMatchQuery,
    CatalogMatchResponse,
)
from schemas.team import CatalogTeamPath, CatalogTeamResponse, CatalogTeamsResponse
from services.competition import CompetitionService
from services.football import FootballService
from services.match import MatchService
from services.team import TeamService


def create_football_blueprint(
    service: FootballService,
    *,
    team_service: TeamService,
    competition_service: CompetitionService,
    match_service: MatchService,
) -> APIBlueprint:
    api = APIBlueprint(
        "football",
        __name__,
        url_prefix="/api/v1",
        abp_tags=[Tag(name="football")],
        abp_responses=errors(),
    )
    api.before_request(object_body)

    @api.get("/catalog/teams", responses={200: CatalogTeamsResponse})
    def catalog_teams() -> Response:
        """Browse PostgreSQL historical teams, ordered by name then ID; not prediction inputs."""
        return jsonify(team_service.list())

    @api.get(
        "/catalog/teams/<team_id>", responses={200: CatalogTeamResponse, "404": errors()["default"]}
    )
    def catalog_team(path: CatalogTeamPath) -> Response:
        """Read a historical team by ID. Fetch two team IDs independently for comparison."""
        return jsonify(team_service.get(path.team_id))

    @api.get("/catalog/competitions", responses={200: CatalogCompetitionsResponse})
    def catalog_competitions() -> Response:
        """Browse PostgreSQL competitions ordered by name, edition label and ID."""
        return jsonify(competition_service.list())

    @api.get("/catalog/matches", responses={200: CatalogMatchesResponse})
    def catalog_matches(query: CatalogMatchQuery) -> Response:
        """Browse PostgreSQL historical matches ordered by date then ID, oldest first.

        Filters combine with AND; team_id matches either participant. Dates are inclusive.
        Returns an array (empty if no matches). Limit defaults to 50, maximum 200;
        offset defaults to zero. Unknown filters and invalid values return 400.
        """
        return jsonify(match_service.list(query))

    @api.get(
        "/catalog/matches/<match_id>",
        responses={200: CatalogMatchResponse, "404": errors()["default"]},
    )
    def catalog_match(path: CatalogMatchPath) -> Response:
        """Read a historical match with both teams, competition, score basis and venue."""
        return jsonify(match_service.get(path.match_id))

    @api.get("/teams")
    def teams() -> Response:
        return jsonify(service.teams())

    @api.post("/predictions", responses={200: PredictionResponse})
    def predictions(body: PredictionRequest) -> Response:
        return jsonify(
            PredictionResponse.model_validate(service.predict(body)).model_dump(mode="json")
        )

    @api.post("/snapshots")
    def save_snapshot(body: PredictionRequest) -> Response:
        result = service.save(body)
        response = jsonify(result)
        response.status_code = 201
        response.headers["Location"] = url_for("football.snapshot", snapshot_id=result["id"])
        return response

    @api.get("/snapshots")
    def snapshots(query: SnapshotQuery) -> Response:
        return jsonify(service.snapshots(query.team1, query.team2, query.limit, query.offset))

    @api.get("/snapshots/<uuid:snapshot_id>")
    def snapshot(path: SnapshotPath) -> Response:
        return jsonify(service.snapshot(path.snapshot_id))

    @api.get("/history")
    def history(query: HistoryQuery) -> Response:
        return jsonify(service.history(query.limit, query.offset))

    @api.get("/insights")
    def insights(query: Matchup) -> Response:
        return jsonify(service.insights(query.team1, query.team2))

    @api.get("/backtests")
    def backtests() -> Response:
        return jsonify(service.backtest())

    @api.post("/tournaments/simulate")
    def tournament(body: TournamentRequest) -> Response:
        return jsonify(service.tournament(body))

    @api.post("/live/refresh")
    def refresh_live(body: Matchup) -> Response:
        return jsonify(service.live(body.team1, body.team2))

    return api
