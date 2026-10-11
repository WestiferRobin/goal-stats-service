"""Scenario persistence endpoints; prediction generation remains a separate workflow."""

from flask import Response, jsonify, request, url_for
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from werkzeug.exceptions import BadRequest

from exceptions.handlers import object_body
from routers.openapi import created_response, errors
from schemas.scenarios import (
    ScenarioCreate,
    ScenarioPatch,
    ScenarioPath,
    ScenarioQuery,
    ScenarioResponse,
    ScenariosResponse,
)
from services.scenarios import ScenarioService


def create_scenarios_blueprint(service: ScenarioService) -> APIBlueprint:
    api = APIBlueprint(
        "scenarios",
        __name__,
        url_prefix="/api/v1/scenarios",
        abp_tags=[Tag(name="scenarios")],
        abp_responses={**errors(), "404": errors()["default"], "409": errors()["default"]},
    )

    @api.before_request
    def validate_body() -> None:
        object_body()
        if request.method == "PATCH":
            if not request.is_json or not isinstance(request.get_json(), dict):
                raise BadRequest()

    created = created_response(ScenarioResponse)
    created["content"]["application/json"]["example"] = ScenarioResponse.model_config[
        "openapi_extra"
    ]["example"]

    @api.post("", responses={201: created})
    def create(body: ScenarioCreate) -> Response:
        """Save a scenario with explicit statistics and immutable caller-supplied rating snapshots.

        Missing ratings are rejected, never filled from matching prototype names. Both teams
        and an optional historical match must exist; linked participants must match in either order.
        prediction_ready means saved inputs are complete for the saved-prediction workflow.
        """
        result = service.create(body)
        response = jsonify(result)
        response.status_code = 201
        response.headers["Location"] = url_for("scenarios.get", scenario_id=result["scenario_id"])
        return response

    @api.get("/<scenario_id>", responses={200: ScenarioResponse})
    def get(path: ScenarioPath) -> Response:
        """Reopen a saved scenario with team names, match reference, state and rating snapshots."""
        return jsonify(service.get(path.scenario_id))

    @api.get("", responses={200: ScenariosResponse})
    def list_scenarios(query: ScenarioQuery) -> Response:
        """List full saved scenarios, newest creation first (ID descending breaks ties).

        Limit defaults to 50, maximum 200; offset defaults to zero. Optional team_id matches
        either participant. Empty results return [].
        """
        return jsonify(service.list(query))

    @api.patch("/<scenario_id>", responses={200: ScenarioResponse})
    def update(path: ScenarioPath, body: ScenarioPatch) -> Response:
        """Update only supplied match-state fields atomically; validate the combined state.

        Identity, creation time and rating snapshots cannot change. Explicit null, unknown
        fields and empty patches are invalid. Saved predictions retain their
        own input snapshot so later scenario edits cannot reinterpret earlier results.
        """
        return jsonify(service.update(path.scenario_id, body))

    return api
