"""Small HTTP client shared by smoke fixtures and workflow probes."""

import json
import urllib.error
import urllib.request


def request(url, path, method="GET", payload=None, expected=200, raw=None):
    data = (
        raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    )
    req = urllib.request.Request(url + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read().decode()
        assert response.status == expected, f"{method} {path}: {response.status}, wanted {expected}"
        headers = dict(response.headers)
        if expected >= 400 and path not in {"/health", "/ready"}:
            assert response.headers.get_content_type() == "application/problem+json"
            problem = json.loads(body)
            assert problem["status"] == expected
            assert {"type", "title", "detail", "status"} <= problem.keys()
            assert not any(
                secret in body.lower()
                for secret in (
                    "traceback",
                    "psycopg",
                    "postgresql://",
                    "postgresql+psycopg://",
                    "redis://",
                )
            )
        return (
            json.loads(body)
            if response.headers.get_content_type()
            in {"application/json", "application/problem+json"}
            else body
        ), headers
