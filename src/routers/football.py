"""JSON API shared by React, Wix server code, and other clients."""

from flask import Response, jsonify, url_for
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from exceptions.handlers import object_body
from routers.openapi import errors
from schemas.football import (
    HistoryQuery,
    Matchup,
    PredictionRequest,
    PredictionResponse,
    SnapshotPath,
    SnapshotQuery,
    TournamentRequest,
)
from services.football import FootballService


def create_football_blueprint(service: FootballService) -> APIBlueprint:
    api = APIBlueprint(
        "football",
        __name__,
        url_prefix="/api/v1",
        abp_tags=[Tag(name="football")],
        abp_responses=errors(),
    )
    api.before_request(object_body)

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
