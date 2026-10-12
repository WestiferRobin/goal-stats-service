"""Pre-refactor contract fingerprints: change only for an intentional public API revision."""

import hashlib
import importlib
import inspect
import json
from pathlib import Path

from pydantic import BaseModel


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_all_relocated_json_schemas_match_original_contracts():
    baseline = json.loads(Path(__file__).with_name("contract_fingerprints.json").read_text())
    actual = {}
    for name in (
        "common",
        "engine",
        "team",
        "competition",
        "match",
        "scenario",
        "prediction",
        "football",
    ):
        module = importlib.import_module("schemas." + name)
        for name, model in vars(module).items():
            if (
                inspect.isclass(model)
                and issubclass(model, BaseModel)
                and model is not BaseModel
                and model.__module__ == module.__name__
            ):
                assert name not in actual, "Duplicate contract definition"
                actual[name] = {
                    mode: digest(model.model_json_schema(mode=mode))
                    for mode in ("validation", "serialization")
                }
    assert actual == baseline["schemas"]


def test_full_openapi_matches_original_contract(app):
    baseline = json.loads(Path(__file__).with_name("contract_fingerprints.json").read_text())
    response = app.test_client().get("/swagger/v1/swagger.json")
    assert response.status_code == 200
    assert digest(response.json) == baseline["openapi"]
