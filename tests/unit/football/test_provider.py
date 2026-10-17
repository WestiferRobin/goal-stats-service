import pytest

from football.provider import api_get


def test_no_key_never_calls_provider(monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    monkeypatch.setattr("football.provider.urlopen", lambda *a, **k: pytest.fail("network call"))
    assert api_get("/fixtures") is None


@pytest.mark.parametrize("size", [2_000_000, 2_000_001])
def test_response_byte_limit_and_request_contract(monkeypatch, size):
    """Accept the exact byte limit, reject overflow, and bound the network read."""
    import io
    from urllib.parse import parse_qs, urlsplit

    payload = b'{"response": [], "errors": []}'
    stream = io.BytesIO(payload + b" " * (size - len(payload)))
    reads = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            stream.close()

        def read(self, amount):
            reads.append(amount)
            return stream.read(amount)

    def open_request(request, timeout):
        url = urlsplit(request.full_url)
        assert (url.scheme, url.netloc, url.path) == (
            "https",
            "v3.football.api-sports.io",
            "/fixtures",
        )
        assert parse_qs(url.query) == {"team": ["A & B"], "fixture": ["42"]}
        assert dict(request.header_items()) == {"X-apisports-key": "test-secret"}
        assert timeout == 5
        return Response()

    monkeypatch.setenv("API_FOOTBALL_KEY", "test-secret")
    monkeypatch.setattr("football.provider.urlopen", open_request)
    result = api_get("/fixtures", {"team": "A & B", "fixture": 42})
    assert result == ({"response": [], "errors": []} if size == 2_000_000 else None)
    assert reads == [2_000_001]
    assert stream.closed


@pytest.mark.parametrize(
    "payload",
    [
        b"{bad",
        b"\xff",
        b"[]",
        b"null",
        b"{}",
        b'{"response": {}}',
        b'{"response": [], "errors": {"token": "private"}}',
    ],
)
def test_invalid_provider_payload_falls_back_without_logging(monkeypatch, payload, capsys):
    """Malformed JSON, encoding, and envelope types never become provider data."""
    import io

    monkeypatch.setenv("API_FOOTBALL_KEY", "test-secret")
    monkeypatch.setattr("football.provider.urlopen", lambda *args, **kwargs: io.BytesIO(payload))
    assert api_get("/fixtures") is None
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("failure", ["http", "transport", "timeout", "os"])
def test_network_failures_are_optional_and_do_not_leak(monkeypatch, failure, capsys):
    """Network boundary failures return no data without exposing URLs or keys."""
    from urllib.error import HTTPError, URLError

    errors = {
        "http": HTTPError("https://private/?secret=test-secret", 503, "private", {}, None),
        "transport": URLError("test-secret"),
        "timeout": TimeoutError("test-secret"),
        "os": OSError("test-secret"),
    }

    def unavailable(*args, **kwargs):
        raise errors[failure]

    monkeypatch.setenv("API_FOOTBALL_KEY", "test-secret")
    monkeypatch.setattr("football.provider.urlopen", unavailable)
    assert api_get("/fixtures") is None
    assert capsys.readouterr() == ("", "")
