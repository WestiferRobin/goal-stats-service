"""Normalized competition HTTP handlers on an independently registered domain blueprint."""

from flask import Response, jsonify
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from exceptions.handlers import object_body
from routers.openapi import errors
from schemas.competition import CatalogCompetitionsResponse
from schemas.competition.request import TournamentRequest
from schemas.competition.response import TournamentResponse
from services.competition import CompetitionService


def create_competition_blueprint(competition_service: CompetitionService) -> APIBlueprint:
    """Attach domain routes using this application's injected service."""
    api = APIBlueprint(
        "competition",
        __name__,
        url_prefix="/api/v1",
        abp_tags=[Tag(name="competition")],
        abp_responses=errors(),
    )
    api.before_request(object_body)

    @api.get("/catalog/competitions", responses={200: CatalogCompetitionsResponse})
    def catalog_competitions() -> Response:
        """Browse PostgreSQL competitions ordered by name, edition label and ID."""
        return jsonify(competition_service.list())

    @api.post("/competitions/simulate", responses={200: TournamentResponse})
    def simulate(body: TournamentRequest) -> Response:
        """Simulate the supplied knockout bracket; not an official tournament reconstruction."""
        return jsonify(competition_service.simulate(body))

    return api
