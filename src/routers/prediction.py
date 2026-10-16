"""Saved predictions and explicit-input unsaved previews."""

from flask import Response, jsonify, request, url_for
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from werkzeug.exceptions import BadRequest

from routers.openapi import created_response, errors
from schemas.prediction import (
    PredictionHistoryQuery,
    PredictionPath,
    SavedPredictionResponse,
    SavedPredictionsResponse,
)
from schemas.prediction.request import PredictionPreview
from schemas.prediction.response import SavedEngineOutput
from schemas.scenario import ScenarioPath
from services.prediction import PredictionService


def create_predictions_blueprint(service: PredictionService) -> APIBlueprint:
    api = APIBlueprint(
        "saved_predictions",
        __name__,
        url_prefix="/api/v1",
        abp_tags=[Tag(name="saved predictions")],
        abp_responses={
            **errors(),
            "404": errors()["default"],
            "409": errors()["default"],
            "500": errors()["default"],
        },
    )

    @api.post(
        "/scenarios/<scenario_id>/predictions",
        responses={201: created_response(SavedPredictionResponse)},
    )
    def generate(path: ScenarioPath) -> Response:
        """Generate and append a prediction from a saved scenario. Send no request body.

        Complete explicit scenario ratings are required. Missing/invalid inputs return 400
        identifying safe field names; no rating fallback is used. The immutable input_snapshot
        records the effective inputs at read time, including normalized shots. Calculation uses
        the existing engine without network calls; it never updates the scenario or prior results.
        Retries create another record. Engine/invalid-output failures return 500 without saving.
        """
        if request.get_data() or request.args:
            raise BadRequest()
        result = service.generate(path.scenario_id)
        response = jsonify(result)
        response.status_code = 201
        response.headers["Location"] = url_for(
            "saved_predictions.get", prediction_id=result["prediction_id"]
        )
        return response

    @api.get("/scenarios/<scenario_id>/predictions", responses={200: SavedPredictionsResponse})
    def history(path: ScenarioPath, query: PredictionHistoryQuery) -> Response:
        """Read saved results newest first, ordered by generated_at then prediction_id descending.

        Limit defaults to 50 (maximum 200), offset to zero. Missing scenario returns 404;
        an existing scenario with no predictions returns []. Results include immutable inputs
        and saved output; retrieval never reruns the engine or reads current team ratings.
        """
        return jsonify(service.history(path.scenario_id, query))

    @api.get("/predictions/<prediction_id>", responses={200: SavedPredictionResponse})
    def get(path: PredictionPath) -> Response:
        """Read one persisted prediction and its effective input snapshot; 404 if absent."""
        return jsonify(service.get(path.prediction_id))

    @api.post("/predictions/preview", responses={200: SavedEngineOutput})
    def preview(body: PredictionPreview) -> Response:
        """Calculate from explicit assumptions and normalized identities without saving."""
        return jsonify(service.preview(body))

    return api
