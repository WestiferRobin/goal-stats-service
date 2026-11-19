"""Bounded evaluation endpoint; existing production service authentication applies."""

from flask import Response, jsonify, request
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag
from werkzeug.exceptions import RequestEntityTooLarge

from exceptions.handlers import object_body
from routers.openapi import errors
from schemas.evaluation.request import FULL_DATASET, BacktestRequest
from schemas.evaluation.response import BacktestResponse
from services.evaluation import EvaluationService


def create_evaluation_blueprint(service: EvaluationService) -> APIBlueprint:
    api = APIBlueprint(
        "evaluation",
        __name__,
        url_prefix="/api/v1",
        abp_tags=[Tag(name="evaluation")],
        abp_responses=errors(),
    )

    @api.before_request
    def bounded_body() -> Response | None:
        request.max_content_length = 131072
        if len(request.get_data()) > 32768:
            value = request.get_json(silent=True)
            if not isinstance(value, dict) or value.get("dataset_id") != FULL_DATASET:
                raise RequestEntityTooLarge()
        return object_body()

    @api.post("/evaluations/backtests", responses={200: BacktestResponse, 503: errors()["default"]})
    def backtest(body: BacktestRequest) -> Response:
        """Evaluate a bounded page of an approved package without persistence."""
        return jsonify(service.evaluate(body))

    return api
