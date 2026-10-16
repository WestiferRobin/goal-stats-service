"""Connection identity guards tested before any real database operation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.engine import make_url

from infra.resources.db import is_ready, verify_import_database
from settings.base import ConfigurationError
from settings.database import ImportTarget


@pytest.mark.parametrize(
    "mismatch,message,reads",
    [
        ("host", "Connected hostname", 0),
        ("database", "Connected database does not match", 1),
        ("user", "Connected database user", 2),
        ("tls", "verified TLS", 3),
    ],
)
def test_import_identity_mismatch_fails_before_table_access(mismatch, message, reads):
    """Reject a mismatched server, database, user, or plaintext connection before table access."""
    cloud = mismatch == "tls"
    host = "cloud.example" if cloud else "localhost"
    url = make_url(f"postgresql+psycopg://goalstats:test@{host}/goalstats_test_guard")
    if cloud:
        url = url.update_query_dict({"sslmode": "verify-full", "sslrootcert": "/test/ca.pem"})
    target = ImportTarget("cloud" if cloud else "test", host, "goalstats_test_guard", cloud)
    session = MagicMock()
    session.connection.return_value = SimpleNamespace(
        engine=SimpleNamespace(url=url),
        connection=SimpleNamespace(
            driver_connection=SimpleNamespace(
                info=SimpleNamespace(host="unexpected" if mismatch == "host" else host)
            )
        ),
    )
    session.scalar.side_effect = [
        "unexpected" if mismatch == "database" else "goalstats_test_guard",
        "unexpected" if mismatch == "user" else "goalstats",
        False,
    ]
    with pytest.raises(ConfigurationError, match=message) as error:
        verify_import_database(session, target)
    assert "test@" not in str(error.value)
    assert session.scalar.call_count == reads
    session.execute.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_readiness_rejects_wrong_database_and_releases_connection(monkeypatch):
    """Readiness does not inspect schema or expose a mismatched connection as healthy."""
    engine = MagicMock()
    engine.url.database = "expected"
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = "unexpected"
    scripts = SimpleNamespace(get_heads=lambda: ["head"])
    monkeypatch.setattr("infra.resources.db.ScriptDirectory", lambda _: scripts)
    assert is_ready(SimpleNamespace(engine=engine)) is False
    connection.execute.assert_not_called()
    engine.connect.return_value.__exit__.assert_called_once_with(None, None, None)
