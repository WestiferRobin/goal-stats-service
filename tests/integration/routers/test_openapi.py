import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from schemas.scenario import ScenarioState


def test_full_openapi_matches_original_contract(app):
    baseline = json.loads(
        (
            Path(__file__).resolve().parents[2] / "unit/schemas/contract_fingerprints.json"
        ).read_text()
    )
    response = app.test_client().get("/swagger/v1/swagger.json")
    assert response.status_code == 200
    assert (
        hashlib.sha256(
            json.dumps(response.json, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == baseline["openapi"]
    )


@pytest.mark.postgres
def test_openapi_saved_predictions(scenario_client):
    spec = scenario_client.get("/swagger/v1/swagger.json").json
    assert set(spec["paths"]["/api/v1/predictions/preview"]) == {"post"}
    assert set(spec["paths"]["/api/v1/predictions/{prediction_id}"]) == {"get"}
    op = spec["paths"]["/api/v1/scenarios/{scenario_id}/predictions"]
    assert set(op) == {"post", "get"}
    assert "requestBody" not in op["post"]
    assert "Location" in op["post"]["responses"]["201"]["headers"]
    for method in ["get", "post"]:
        assert {"400", "404", "500"} <= set(op[method]["responses"])
    assert (
        "input_snapshot" in spec["components"]["schemas"]["SavedPredictionResponse"]["properties"]
    )


@pytest.mark.postgres
def test_openapi_scenario_contract(scenario_client):
    spec = scenario_client.get("/swagger/v1/swagger.json").json
    assert set(spec["paths"][URL]) == {"get", "post"}
    assert set(spec["paths"][URL + "/{scenario_id}"]) == {"get", "patch"}
    assert "201" in spec["paths"][URL]["post"]["responses"]
    assert "Location" in spec["paths"][URL]["post"]["responses"]["201"]["headers"]
    schemas = spec["components"]["schemas"]
    for path, method in [(URL, "post"), (URL + "/{scenario_id}", "patch")]:
        assert spec["paths"][path][method]["requestBody"]["content"]["application/json"]["example"]
    for path, method, status in [(URL, "post", "201"), (URL + "/{scenario_id}", "get", "200")]:
        assert spec["paths"][path][method]["responses"][status]["content"]["application/json"][
            "example"
        ]
    assert "team1_offense" in schemas["ScenarioCreate"]["required"]
    assert "team1_id" not in schemas["ScenarioPatch"]["properties"]
    assert set(ScenarioState.model_fields) == set(schemas["ScenarioPatch"]["properties"])


URL = "/api/v1/scenarios"


@pytest.mark.postgres
def test_catalog_openapi(catalog_client):
    assert catalog_client.get("/swagger").status_code == 200
    spec = catalog_client.get("/swagger/v1/swagger.json").json
    for path in ("teams", "teams/{team_id}", "competitions", "matches", "matches/{match_id}"):
        operation = spec["paths"][f"{BASE}/{path}"]["get"]
        assert operation.get("summary") or operation.get("description")
        assert "200" in operation["responses"] and "400" in operation["responses"]
        assert "schema" in operation["responses"]["200"]["content"]["application/json"]
        if "{" in path:
            assert "404" in operation["responses"]
    parameters = spec["paths"][f"{BASE}/matches"]["get"]["parameters"]
    assert {p["name"] for p in parameters} == {
        "team_id",
        "competition_id",
        "date_from",
        "date_to",
        "limit",
        "offset",
    }
    for path in ("/teams", "/predictions", "/history", "/snapshots", "/backtests", "/insights"):
        assert f"/api/v1{path}" not in spec["paths"]


BASE = "/api/v1/catalog"


def test_exact_route_and_openapi_resource_contract(app):
    spec = app.test_client().get("/swagger/v1/swagger.json").json
    football = {
        "/api/v1/scenarios/{scenario_id}/predictions": {"get", "post"},
        "/api/v1/predictions/{prediction_id}": {"get"},
        "/api/v1/scenarios": {"get", "post"},
        "/api/v1/scenarios/{scenario_id}": {"get", "patch"},
        "/api/v1/catalog/teams": {"get"},
        "/api/v1/catalog/teams/{team_id}": {"get"},
        "/api/v1/catalog/competitions": {"get"},
        "/api/v1/catalog/matches": {"get"},
        "/api/v1/catalog/matches/{match_id}": {"get"},
        "/api/v1/predictions/preview": {"post"},
        "/api/v1/catalog/matches/insights": {"get"},
        "/api/v1/competitions/simulate": {"post"},
    }
    assert set(spec["paths"]) == set(football) | {"/health", "/ready"}
    for path, methods in football.items():
        assert set(spec["paths"][path]) - {"parameters"} == methods
    assert not any(path.startswith(("/items", "/actions")) for path in spec["paths"])
    assert not any(
        rule.rule.startswith(("/items", "/actions")) for rule in app.url_map.iter_rules()
    )
    assert not any(name.startswith(("Item", "Action")) for name in spec["components"]["schemas"])


def test_infra_documents_plain_text_readiness_states(app):
    paths = app.test_client().get("/swagger/v1/swagger.json").json["paths"]
    for path, responses in {
        "/health": {"200": ["Healthy"]},
        "/ready": {"200": ["Healthy", "Degraded"], "503": ["Unhealthy"]},
    }.items():
        operation = paths[path]["get"]
        assert operation["tags"] == ["infra"]
        for status, states in responses.items():
            content = operation["responses"][status]["content"]
            assert set(content) == {"text/plain"}
            assert content["text/plain"]["schema"]["enum"] == states


def test_swagger_uses_local_assets_and_actual_spec(app):
    client = app.test_client()
    response = client.get("/swagger")
    assert response.status_code == 200
    assert "/swagger/v1/swagger.json" in response.text
    assert "/swagger-assets/" in response.text

    class AssetReferences(HTMLParser):
        def __init__(self):
            super().__init__()
            self.references = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "script" and attributes.get("src"):
                self.references.append(attributes["src"])
            if tag == "link" and attributes.get("href"):
                self.references.append(attributes["href"])

    assets = AssetReferences()
    assets.feed(response.text)
    assert assets.references
    for reference in assets.references:
        url = urlsplit(reference.strip())
        assert url.scheme.lower() not in {"http", "https"}
        assert not url.netloc  # Also reject protocol-relative external assets.
    assert client.get("/swagger/v1/swagger.json").json["openapi"] == "3.1.0"
    # The previous UI bundle served successfully but could not render OpenAPI 3.1.
    with client.get("/swagger-assets/swagger-ui-bundle.js") as bundle:
        assert "isOAS31" in bundle.text
    for asset in ("swagger-ui.css", "swagger-ui-bundle.js", "swagger-ui-standalone-preset.js"):
        with client.get("/swagger-assets/" + asset) as asset_response:
            assert asset_response.status_code == 200
    assert client.get("/swagger-assets/../../requirements.txt").status_code == 404


def test_disabling_openapi_disables_ui_assets_and_spec(app_factory, explicit_config):
    client = app_factory({**explicit_config, "OPENAPI_ENABLED": "false"}).test_client()
    for path in ("/swagger", "/swagger/v1/swagger.json", "/swagger-assets/swagger-ui.css"):
        assert client.get(path).status_code == 404


def test_all_generated_schema_references_resolve(app):
    spec = app.test_client().get("/swagger/v1/swagger.json").json

    def visit(value):
        if isinstance(value, dict):
            if "$ref" in value:
                target = spec
                assert value["$ref"].startswith("#/")
                for part in value["$ref"][2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(spec)
