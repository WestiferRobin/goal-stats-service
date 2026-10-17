"""Normalized match HTTP handlers on an independently registered domain blueprint."""

from flask import Response, jsonify
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from exceptions.handlers import object_body
from routers.openapi import errors
from schemas.match import (
    CatalogMatchesResponse,
    CatalogMatchPath,
    CatalogMatchQuery,
    CatalogMatchResponse,
)
from schemas.match.request import HistoricalComparison
from schemas.match.response import HistoricalInsights
from services.match import MatchService


def create_match_blueprint(match_service: MatchService) -> APIBlueprint:
    """Attach domain routes using this application's injected service."""
    api = APIBlueprint(
        "match",
        __name__,
        url_prefix="/api/v1",
        abp_tags=[Tag(name="match")],
        abp_responses=errors(),
    )
    api.before_request(object_body)

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

    @api.get(
        "/catalog/matches/insights", responses={200: HistoricalInsights, "404": errors()["default"]}
    )
    def insights(query: HistoricalComparison) -> Response:
        """Dated head-to-head and team histories; limit/offset apply independently to each list."""
        return jsonify(match_service.insights(query))

    return api
