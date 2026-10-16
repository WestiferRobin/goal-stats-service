"""Handler policy in Flask contexts, independently of application routing."""

import pytest
from flask import Flask
from pydantic import TypeAdapter, ValidationError
from werkzeug.exceptions import BadRequest, HTTPException, MethodNotAllowed, TooManyRequests

from exceptions.base import DomainError
from exceptions.handlers import object_body, problem, register_error_handlers, request_validation


def test_problem_and_validation_responses_do_not_expose_invalid_input():
    app = Flask(__name__)
    with app.app_context():
        response = problem(409, "Reviewed conflict")
        assert response.status_code == 409
        assert response.content_type == "application/problem+json"
        assert response.json == {
            "type": "about:blank",
            "title": "Conflict",
            "status": 409,
            "detail": "Reviewed conflict",
        }
        with pytest.raises(ValidationError) as caught:
            TypeAdapter(int).validate_python("secret-password")
        response = request_validation(caught.value)
        assert response.status_code == 400
        assert response.json["detail"] == "The request could not be understood."
        assert "secret-password" not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "error,status,detail",
    [
        (BadRequest("private"), 400, "The request could not be understood."),
        (
            MethodNotAllowed(valid_methods=["GET"]),
            405,
            "The request method is not allowed for this resource.",
        ),
        (TooManyRequests("private", retry_after=7), 429, "Too Many Requests"),
        (HTTPException("private"), 500, "An unexpected error occurred."),
        (DomainError("private"), 400, DomainError.public_detail),
        (RuntimeError("private"), 500, "An unexpected error occurred."),
    ],
)
def test_registered_handler_sanitizes_messages_and_preserves_headers(error, status, detail, caplog):
    app = Flask(__name__)
    register_error_handlers(app)
    with app.test_request_context():
        kind = (
            DomainError
            if isinstance(error, DomainError)
            else (HTTPException if isinstance(error, HTTPException) else Exception)
        )
        response = app.error_handler_spec[None][None][kind](error)
    assert response.status_code == status
    assert response.content_type == "application/problem+json"
    assert response.json["status"] == status
    assert response.json["detail"] == detail
    assert "private" not in response.get_data(as_text=True) + caplog.text
    if isinstance(error, MethodNotAllowed):
        assert response.headers["Allow"] == "GET"
    if isinstance(error, TooManyRequests):
        assert response.headers["Retry-After"] == "7"
    if isinstance(error, RuntimeError):
        assert "RuntimeError" in caplog.text


@pytest.mark.parametrize(
    "method,payload,valid",
    [
        ("POST", {}, True),
        ("PUT", [], False),
        ("POST", "text", False),
        ("PATCH", [], True),
    ],
)
def test_object_body_checks_only_supported_write_methods(method, payload, valid):
    app = Flask(__name__)
    with app.test_request_context(method=method, json=payload):
        if valid:
            assert object_body() is None
        else:
            with pytest.raises(BadRequest):
                object_body()
    with app.test_request_context(method="POST", data="private"):
        with pytest.raises(BadRequest):
            object_body()
