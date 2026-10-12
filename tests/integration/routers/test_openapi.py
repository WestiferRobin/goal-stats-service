from html.parser import HTMLParser
from urllib.parse import urlsplit


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
        "/api/v1/teams": {"get"},
        "/api/v1/predictions": {"post"},
        "/api/v1/snapshots": {"get", "post"},
        "/api/v1/snapshots/{snapshot_id}": {"get"},
        "/api/v1/history": {"get"},
        "/api/v1/insights": {"get"},
        "/api/v1/backtests": {"get"},
        "/api/v1/tournaments/simulate": {"post"},
        "/api/v1/live/refresh": {"post"},
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
