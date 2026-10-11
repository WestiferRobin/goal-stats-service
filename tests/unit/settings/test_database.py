import pytest

from settings.base import ConfigurationError
from settings.database import database_url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "secret",
        "sqlite:///secret.db",
        "postgresql+asyncpg://user:secret@host/db",
        "postgresql://user:secret@host",
        "postgresql://user:secret@host:abc/db",
        "postgresql://user:secret@host:65536/db",
        "postgresql://user:secret@host/db?connect_timeout=999",
    ],
)
def test_invalid_database_urls_never_echo_values(url):
    with pytest.raises(ConfigurationError) as error:
        database_url(url)
    assert "secret" not in str(error.value)
    assert "DATABASE_URL" in str(error.value)


def test_encoded_password_and_explicit_driver_are_preserved():
    result = database_url("postgresql+psycopg://u:p%40ss%25@localhost:5432/goalstats_test_url")
    assert result.password == "p@ss%"
    assert result.port == 5432


@pytest.mark.parametrize(
    "query",
    [
        "sslmode=disable",
        "sslmode=require",
        "sslmode=verify-ca&sslrootcert=/certs/root.pem",
        "sslmode=verify-full&sslrootcert=/certs/root.pem",
        "sslmode=verify-full&sslrootcert=system",
        "sslmode=verify-full&sslrootcert=/certs/root.pem&sslcert=/certs/client.pem&sslkey=/certs/client.key",
    ],
)
def test_supported_tls_settings(query):
    url = database_url("postgresql://u:secret@db.example.org/db?" + query)
    assert url.query["sslmode"] in {"disable", "require", "verify-ca", "verify-full"}


@pytest.mark.parametrize(
    "query",
    [
        "sslmode=prefer",
        "sslmode=allow",
        "sslmode=invalid",
        "sslmode=verify-full",
        "sslmode=require&sslcert=/certs/client.pem",
        "sslrootcert=/certs/root.pem",
        "sslmode=verify-full&sslrootcert=relative.pem",
        "sslmode=disable&sslrootcert=/certs/root.pem",
        "sslmode=verify-ca&sslrootcert=system",
        "sslmode=require&host=other",
        "sslmode=require&hostaddr=127.0.0.1",
        "service=hidden",
        "options=-csearch_path=other",
        "sslmode=require&sslmode=disable",
        "sslmode=verify-full&sslrootcert=",
    ],
)
def test_invalid_tls_and_connection_overrides_are_redacted(query):
    with pytest.raises(ConfigurationError) as error:
        database_url("postgresql://u:secret@db.example.org/db?" + query)
    assert "secret" not in str(error.value)
    assert query not in str(error.value)


@pytest.mark.parametrize("host,port", [("127.0.0.1", 55432), ("postgres", 5432)])
def test_explicit_local_target(host, port):
    from settings.database import ImportTarget

    url = database_url(f"postgresql://goalstats:secret@{host}:{port}/goal_stats_service_local")
    ImportTarget("local", host, "goal_stats_service_local").validate(url)


def test_production_safeguards_independent_of_app_environment(monkeypatch):
    from settings.database import ImportTarget

    plain = database_url("postgresql://u:secret@db.example.org/db")
    verified = database_url(
        "postgresql://u:secret@db.example.org/db?sslmode=verify-full&sslrootcert=system"
    )
    for environment in ["local", "test", "dev"]:
        monkeypatch.setenv("APP_ENV", environment)
        with pytest.raises(ConfigurationError, match="confirm-production"):
            ImportTarget("cloud", "db.example.org", "db").validate(verified)
        with pytest.raises(ConfigurationError, match="verify-full"):
            ImportTarget("cloud", "db.example.org", "db", True).validate(plain)
        ImportTarget("cloud", "db.example.org", "db", True).validate(verified)
        with pytest.raises(ConfigurationError):
            ImportTarget("local", "db.example.org", "db", True).validate(verified)
        with pytest.raises(ConfigurationError):
            ImportTarget("test", "db.example.org", "goalstats_test_fake").validate(verified)


def test_no_implicit_cloud_fallback_or_local_file_read(monkeypatch):
    from settings.database import DatabaseSettings, validate_prototype_target
    from settings.environment import load_application

    def forbidden(*args, **kwargs):
        pytest.fail("Direct configuration must not read local files")

    monkeypatch.setattr("settings.environment.read_private", forbidden)
    with pytest.raises(ConfigurationError):
        load_application({"APP_ENV": "local"})
    settings = load_application(
        {
            "APP_ENV": "local",
            "DATABASE_URL": "postgresql://u:secret@db.example.org/db?sslmode=verify-full&sslrootcert=system",
        }
    )
    assert isinstance(settings.database, DatabaseSettings)
    assert "secret" not in repr(settings)
    with pytest.raises(ConfigurationError):
        validate_prototype_target(settings.database.url)


def test_tls_parameters_reach_shared_engine_without_network(monkeypatch):
    from infra.resources.db import Database
    from settings.database import DatabaseSettings

    observed = {}

    def engine(url, **kwargs):
        observed.update(url=url, **kwargs)
        return object()

    monkeypatch.setattr("infra.resources.db.create_engine", engine)
    url = database_url(
        "postgresql://u:secret@db.example.org/db?sslmode=verify-full&sslrootcert=system"
    )
    Database(DatabaseSettings(url))
    assert observed["url"].query["sslmode"] == "verify-full"
    assert observed["connect_args"]["gssencmode"] == "disable"
    assert observed["hide_parameters"] is True
