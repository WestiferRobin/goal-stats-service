import re

import pytest
from flask import jsonify, request
from flask_openapi3.blueprint import APIBlueprint
from pydantic import BaseModel, ConfigDict
from werkzeug.exceptions import BadRequest

from exceptions.base import DomainError
from exceptions.handlers import object_body

PRIVATE_DETAILS = (
    "private_password internal_connection_failure psycopg.OperationalError "
    "postgresql://user:secret@database/private "
    "postgresql+psycopg://user:secret@database/private redis://cache:6379/0 "
    "Traceback (most recent call last):"
)


@pytest.fixture
def error_app(app):
    # Test-only routes exercise real Flask/Pydantic boundaries, never production debug routes.
    blueprint = APIBlueprint("boundary_test", __name__)

    class InputSchema(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str

    blueprint.before_request(object_body)

    @blueprint.post("/_validation", responses={200: InputSchema})
    def validate(body: InputSchema):
        return jsonify(body.model_dump(mode="json"))

    @app.post("/_json")
    def json_body():
        return request.get_json()

    @app.get("/_domain")
    def domain():
        raise DomainError(PRIVATE_DETAILS)

    @app.get("/_invalid_output")
    def invalid_output():
        return InputSchema.model_validate({"name": None})

    @app.get("/_http")
    def http():
        raise BadRequest(PRIVATE_DETAILS)

    @app.get("/_unexpected")
    def unexpected():
        raise RuntimeError(PRIVATE_DETAILS)

    app.register_api(blueprint)
    return app


@pytest.mark.parametrize(
    "path,method,status",
    [
        ("/missing", "get", 404),
        ("/health", "post", 405),
        ("/_domain", "get", 400),
        ("/_invalid_output", "get", 500),
        ("/_http", "get", 400),
        ("/_unexpected", "get", 500),
    ],
)
def test_consistent_safe_problem_details(error_app, path, method, status, capsys):
    response = getattr(error_app.test_client(), method)(path, headers={"Accept": "text/html"})
    assert response.status_code == status
    assert response.mimetype == "application/problem+json"
    assert set(response.json) == {"type", "title", "status", "detail"}
    assert response.json["status"] == status
    assert response.json["type"] == "about:blank"
    assert "private_password" not in response.text
    assert "internal_connection_failure" not in response.text
    # Match concrete implementation identifiers/URL schemes, not ordinary
    # user-facing words such as "database" or "connection".
    assert not re.search(
        r"traceback \(most recent call last\)|\bpsycopg\b|"
        r"postgres(?:ql)?(?:\+psycopg)?://|rediss?://",
        response.text,
        re.IGNORECASE,
    )
    assert "private_password" not in capsys.readouterr().err
    if status == 405:
        assert {"GET", "HEAD", "OPTIONS"} <= set(
            response.headers["Allow"].replace(" ", "").split(",")
        )


@pytest.mark.parametrize("path", ["/_json", "/_validation"])
def test_malformed_json_uses_problem_details(error_app, path):
    response = error_app.test_client().post(
        path, data="{broken private_password", content_type="application/json"
    )
    assert response.status_code == 400
    assert response.mimetype == "application/problem+json"
    assert "private_password" not in response.text


def test_pydantic_validation_uses_400_and_unknown_fields_are_rejected(error_app):
    client = error_app.test_client()
    for data in [{}, {"name": "valid", "unexpected": "private_password"}]:
        response = client.post("/_validation", json=data)
        assert response.status_code == 400
        assert response.mimetype == "application/problem+json"
        assert "private_password" not in response.text
    assert client.post("/_validation", json={"name": "valid"}).json == {"name": "valid"}


def test_non_json_body_is_safe_415(error_app):
    response = error_app.test_client().post(
        "/_json", data="private_password", content_type="text/plain"
    )
    assert response.status_code == 415
    assert response.mimetype == "application/problem+json"
    assert "private_password" not in response.text
