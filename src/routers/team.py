"""Normalized team HTTP handlers on an independently registered domain blueprint."""

from flask import Response, jsonify
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from exceptions.handlers import object_body
from routers.openapi import errors
from schemas.team import CatalogTeamPath, CatalogTeamResponse, CatalogTeamsResponse
from services.team import TeamService


def create_team_blueprint(team_service: TeamService) -> APIBlueprint:
    """Attach domain routes using this application's injected service."""
    api = APIBlueprint(
        "team", __name__, url_prefix="/api/v1", abp_tags=[Tag(name="team")], abp_responses=errors()
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

    return api
