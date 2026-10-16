import hashlib
import importlib
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from pkgutil import walk_packages
from uuid import UUID

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from schemas.common import Identity, Name, Timestamp

DOMAIN_EXPORTS = {
    "team": {
        "request": "CatalogTeamPath",
        "response": "CatalogTeamResponse CatalogTeamsResponse",
    },
    "competition": {
        "response": "CatalogCompetitionResponse CatalogCompetitionsResponse",
    },
    "match": {
        "request": "CatalogMatchPath CatalogMatchQuery",
        "response": "CatalogMatchResponse CatalogMatchesResponse",
    },
    "scenario": {
        "base": (
            "ScenarioConfig ScenarioState StrictCount Percentage ModifierTotal Rating BodyID "
            "SCENARIO_EXAMPLE"
        ),
        "request": "ScenarioPath ScenarioQuery ScenarioCreate ScenarioPatch",
        "response": "ScenarioResponse ScenariosResponse",
    },
    "prediction": {
        "request": "PredictionPath PredictionHistoryQuery",
        "response": (
            "Probability FinalScore PredictionInputs ValidProbabilities ValidPair ExpectedGoals "
            "PercentPair ValidScoreline ValidConfidence SavedEngineOutput SavedPredictionResponse "
            "SavedPredictionsResponse"
        ),
    },
}


@pytest.mark.parametrize("value", [None, "", " \t\n", "x" * 201, 12])
def test_name_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        TypeAdapter(Name).validate_python(value)


def test_name_preserves_whitespace_and_accepts_maximum_length():
    adapter = TypeAdapter(Name)
    assert adapter.validate_python(" x ") == " x "
    assert adapter.validate_python("x" * 200) == "x" * 200


@pytest.mark.parametrize("value", [None, "bad", str(UUID(int=0))])
def test_identity_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        TypeAdapter(Identity).validate_python(value)


def test_identity_accepts_uuid_objects_and_strings():
    adapter = TypeAdapter(Identity)
    identity = UUID(int=1)
    assert adapter.validate_python(identity) == identity
    assert adapter.validate_python(str(identity)) == identity


def test_timestamp_requires_timezone_and_preserves_offset_serialization():
    adapter = TypeAdapter(Timestamp)
    value = datetime(2026, 1, 1, tzinfo=UTC)
    assert adapter.validate_python(value.isoformat()) == value
    assert adapter.dump_python(value, mode="json") == "2026-01-01T00:00:00+00:00"
    with pytest.raises(ValidationError):
        adapter.validate_python("2026-01-01T00:00:00")


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
    ):
        module = importlib.import_module("schemas." + name)
        modules = [module]
        if hasattr(module, "__path__"):
            modules.extend(
                importlib.import_module(info.name)
                for info in walk_packages(module.__path__, module.__name__ + ".")
            )
        for defining_module in modules:
            for name, model in vars(defining_module).items():
                if (
                    inspect.isclass(model)
                    and issubclass(model, BaseModel)
                    and model is not BaseModel
                    and model.__module__ == defining_module.__name__
                ):
                    assert name not in actual, "Duplicate contract definition"
                    actual[name] = {
                        mode: digest(model.model_json_schema(mode=mode))
                        for mode in ("validation", "serialization")
                    }
    assert len(actual) == len(baseline["schemas"])
    assert actual == baseline["schemas"]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.mark.parametrize("domain", DOMAIN_EXPORTS)
def test_domain_package_exports_original_objects(domain):
    package = importlib.import_module("schemas." + domain)
    expected = set()
    for submodule, names in DOMAIN_EXPORTS[domain].items():
        defining_module = importlib.import_module(f"schemas.{domain}.{submodule}")
        for name in names.split():
            assert getattr(package, name) is getattr(defining_module, name)
            expected.add(name)
    assert set(package.__all__) == expected
    assert not Path(package.__file__).parent.with_suffix(".py").exists()
