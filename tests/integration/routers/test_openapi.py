def test_exact_route_and_openapi_resource_contract(app):
    expected = {
        "/items": {"get", "post"},
        "/items/{item_id}": {"get", "put", "delete"},
        "/actions": {"get", "post"},
        "/actions/{action_id}": {"get", "put", "delete"},
        "/items/{item_id}/actions": {"get", "post"},
    }
    spec = app.test_client().get("/swagger/v1/swagger.json").json
    football = {
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
    assert set(spec["paths"]) == set(expected) | set(football) | {"/health", "/ready"}
    for path, methods in football.items():
        assert set(spec["paths"][path]) - {"parameters"} == methods
    for path, methods in expected.items():
        operations = spec["paths"][path]
        assert set(operations) - {"parameters"} == methods
        for method in methods:
            response = operations[method]["responses"]
            assert "default" in response
            assert (
                response["default"]["content"]["application/problem+json"]["schema"]["$ref"]
                == "#/components/schemas/ProblemDetailSchema"
            )
        if "post" in methods:
            assert "Location" in operations["post"]["responses"]["201"]["headers"]
            assert "400" in operations["post"]["responses"]
    schemas = spec["components"]["schemas"]
    assert schemas["ItemStatus"]["enum"] == ["active", "archived"]
    assert schemas["ActionType"]["enum"] == ["create", "update", "delete"]
    assert "itemId" not in schemas["ActionWriteRequest"]["properties"]
    assert "itemId" in schemas["ActionCreateRequest"]["required"]
    assert schemas["ItemCreateRequest"]["additionalProperties"] is False
    assert schemas["ItemCreateRequest"]["properties"]["name"]["maxLength"] == 200
    assert schemas["ActionCreateRequest"]["properties"]["name"]["maxLength"] == 200
    assert schemas["ItemResponse"]["properties"]["id"]["format"] == "uuid"
    assert schemas["ActionResponse"]["properties"]["createdAt"]["format"] == "date-time"
    # A Blueprint registers one Rule per view; merge methods for the exact route surface.
    actual = {}
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith(("/items", "/actions")):
            actual.setdefault(rule.rule, set()).update(rule.methods - {"HEAD", "OPTIONS"})
    assert actual == {
        "/items": {"GET", "POST"},
        "/items/<uuid:item_id>": {"GET", "PUT", "DELETE"},
        "/actions": {"GET", "POST"},
        "/actions/<uuid:action_id>": {"GET", "PUT", "DELETE"},
        "/items/<uuid:item_id>/actions": {"GET", "POST"},
    }


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
    assert "https://" not in response.text
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
