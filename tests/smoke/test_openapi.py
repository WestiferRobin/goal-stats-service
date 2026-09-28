import pytest

pytestmark = pytest.mark.smoke


def test_built_system_swagger_and_openapi(smoke_client):
    html, _ = smoke_client.request("/swagger")
    assert "/swagger/v1/swagger.json" in html and "/swagger-assets/" in html
    assert "https://" not in html and "http://" not in html
    js, _ = smoke_client.request("/swagger-assets/swagger-ui-bundle.js")
    assert "SwaggerUIBundle" in js
    spec, _ = smoke_client.request("/swagger/v1/swagger.json")
    assert set(spec["paths"]) == {
        "/api/v1/teams",
        "/api/v1/predictions",
        "/api/v1/snapshots",
        "/api/v1/snapshots/{snapshot_id}",
        "/api/v1/history",
        "/api/v1/insights",
        "/api/v1/backtests",
        "/api/v1/tournaments/simulate",
        "/api/v1/live/refresh",
        "/health",
        "/ready",
        "/items",
        "/items/{item_id}",
        "/actions",
        "/actions/{action_id}",
        "/items/{item_id}/actions",
    }
