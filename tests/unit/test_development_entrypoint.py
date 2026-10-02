"""Direct-only configuration, diagnostics, and single-process execution."""

import importlib
import os
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.exc import OperationalError

import main
from settings import environment as host
from settings.base import ConfigurationError


@pytest.fixture
def host_file(tmp_path, monkeypatch):
    path = tmp_path / ".env.local"
    path.write_text("POSTGRES_PASSWORD=abcdefghijklmnop\nDEV_POSTGRES_PASSWORD=ponmlkjihgfedcba\n")
    path.chmod(0o600)
    monkeypatch.setattr(host, "LOCAL_FILE", path)
    for key in host.DIRECT_KEYS:
        monkeypatch.delenv(key, raising=False)
    return path


@pytest.mark.parametrize("mode", [None, "local"])
def test_direct_local_constructs_once_without_reloader_or_dotenv(host_file, monkeypatch, mode):
    if mode is not None:
        monkeypatch.setenv("APP_ENV", mode)
    monkeypatch.setenv("FLASK_DEBUG", "1")
    before = dict(os.environ)
    factory = Mock()
    diagnostics = Mock()
    monkeypatch.setattr(main, "create_app", factory)
    monkeypatch.setattr(main, "_diagnose_providers", diagnostics)
    monkeypatch.setattr(main, "_check_app_port", Mock())
    main.development_main()
    factory.assert_called_once()
    values = factory.call_args.args[0]
    assert values.core.app_env == "local"
    assert (
        values.database.url.port == 55432
        and values.database.url.database == "goal_stats_service_local"
    )
    diagnostics.assert_called_once_with(factory.return_value)
    factory.return_value.run.assert_called_once_with(
        host="127.0.0.1",
        port=5300,
        debug=False,
        use_debugger=False,
        use_reloader=False,
        load_dotenv=False,
    )
    assert dict(os.environ) == before


@pytest.mark.parametrize("mode", ["dev", "test", "production", "", " "])
def test_direct_refuses_nonlocal_before_reading_file(host_file, monkeypatch, mode):
    read = Mock(side_effect=AssertionError("must not read"))
    monkeypatch.setattr(host, "read_private", read)
    with pytest.raises(ConfigurationError, match="APP_ENV"):
        host.load_local({"APP_ENV": mode})
    read.assert_not_called()


@pytest.mark.parametrize("cwd", ["root", "src"])
def test_file_location_does_not_depend_on_cwd(host_file, tmp_path, monkeypatch, cwd):
    directory = tmp_path / cwd
    directory.mkdir()
    (directory / ".env.local").write_text("must not load cwd file")
    monkeypatch.chdir(directory)
    assert host.load_local({}).core.app_env == "local"


def test_missing_file_is_actionable(host_file):
    host_file.unlink()
    with pytest.raises(ConfigurationError, match="make providers"):
        host.load_local({})


@pytest.mark.parametrize(
    "content",
    [
        "APP_ENV=local\nBROKEN",
        "APP_ENV=local\nAPP_ENV=local",
        "APP_ENV=local\nUNKNOWN=secret",
        "APP_ENV=dev",
        "APP_ENV=test",
        "APP_ENV=",
        "DATABASE_URL=secret",
        "APP_ENV=local\nLOG_LEVEL=I\x00NFO",
    ],
)
def test_bad_host_file_refused_without_values(host_file, content):
    host_file.write_text(content)
    with pytest.raises(ConfigurationError) as exc:
        host.load_local({"APP_ENV": "local"})
    assert "secret" not in str(exc.value)


def test_file_symlink_and_permissions_refused(host_file, tmp_path, monkeypatch):
    link = tmp_path / "link"
    link.symlink_to(host_file)
    with pytest.raises(ConfigurationError, match="symlinks"):
        host.read_private(link, host.LOCAL_KEYS)
    host_file.chmod(0o644)
    with pytest.raises(ConfigurationError, match="private"):
        host.read_private(host_file, host.LOCAL_KEYS)
    host_file.chmod(0o600)
    monkeypatch.setattr(host.os, "getuid", lambda: host_file.stat().st_uid + 1)
    with pytest.raises(ConfigurationError, match="owned"):
        host.read_private(host_file, host.LOCAL_KEYS)


def test_nonregular_file_refused(tmp_path):
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo, 0o600)
    with pytest.raises(ConfigurationError, match="regular"):
        host.read_private(fifo, host.LOCAL_KEYS)


def test_literal_values_are_not_evaluated_or_interpolated(host_file):
    with host_file.open("a") as stream:
        stream.write("LOG_LEVEL=${HOME}\n")
    assert host.read_private(host_file, host.LOCAL_KEYS)["LOG_LEVEL"] == "${HOME}"
    with pytest.raises(ConfigurationError, match="LOG_LEVEL"):
        host.load_local({})


def test_precedence_defaults_and_optional_redis(host_file):
    with host_file.open("a") as stream:
        stream.write("HOST_APP_PORT=5400\nLOG_LEVEL=WARNING\n")
    config = host.load_local({"HOST_APP_PORT": "5500", "REDIS_URL": "", "LOG_LEVEL": "DEBUG"})
    assert config.core.host_app_port == 5500
    assert config.core.openapi_enabled is True
    assert config.core.log_level == "DEBUG"
    assert config.redis.url is None
    assert config.redis.cache_key_prefix == "goal-stats-service:local:v1"


@pytest.mark.parametrize(
    "key,value",
    [
        ("DATABASE_URL", ""),
        ("DATABASE_URL", "secret"),
        ("DATABASE_URL", "postgresql://u:secret@remote/db"),
        ("REDIS_URL", "secret"),
        ("REDIS_URL", "redis://remote/0"),
        ("CACHE_KEY_PREFIX", "?"),
        ("CACHE_TTL_SECONDS", "0"),
        ("OPENAPI_ENABLED", "maybe"),
        ("LOG_LEVEL", "secret"),
        *[("HOST_APP_PORT", v) for v in ("0", "65536", "-1", "", "５３００", "abc")],
    ],
)
def test_invalid_override_refused(host_file, key, value):
    with pytest.raises(ConfigurationError) as exc:
        host.load_local({key: value})
    assert "secret" not in str(exc.value)


def test_missing_database_refused(host_file):
    host_file.write_text("DEV_POSTGRES_PASSWORD=abcdefghijklmnop\n")
    with pytest.raises(ConfigurationError, match="POSTGRES_PASSWORD"):
        host.load_local({})


def test_occupied_app_port_is_actionable(monkeypatch):
    socket = MagicMock()
    socket.return_value.__enter__.return_value.bind.side_effect = OSError("occupied")
    monkeypatch.setattr(main.socket, "socket", socket)
    with pytest.raises(ConfigurationError, match="choose HOST_APP_PORT"):
        main._check_app_port(5300)


@pytest.fixture
def diagnostic_app():
    db, cache, settings = Mock(), Mock(), Mock(redis=Mock(cache_key_prefix="unit"))
    app = Mock(
        extensions={
            "goalstats_database": db,
            "goalstats_cache": cache,
            "goalstats_settings": settings,
        }
    )
    return app, db, cache


def test_postgres_unavailable_is_redacted(diagnostic_app):
    app, db, _ = diagnostic_app
    db.engine.connect.side_effect = OperationalError("secret", {}, Exception("password"))
    with pytest.raises(ConfigurationError, match="LOCAL PostgreSQL is unavailable") as exc:
        main._diagnose_providers(app)
    assert "secret" not in str(exc.value) and "password" not in str(exc.value)
    db.dispose.assert_called_once()


def test_unmigrated_database_and_redis_outage_only_warn(diagnostic_app, monkeypatch):
    app, db, cache = diagnostic_app
    db.engine.connect.return_value.__enter__ = Mock()
    db.engine.connect.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(main, "is_ready", lambda _: False)
    cache.ready.return_value = False
    main._diagnose_providers(app)
    messages = [call.args[0] for call in app.logger.warning.call_args_list]
    assert any("make migrate ENV=local" in m for m in messages)
    assert any("database fallback" in m for m in messages)


def test_import_and_factory_never_read_host_file(monkeypatch):
    reader = Mock(side_effect=AssertionError("host file accessed"))
    monkeypatch.setattr(host, "read_private", reader)
    importlib.reload(main)
    before = dict(os.environ)
    app = main.create_app({"APP_ENV": "test", "DATABASE_URL": "postgresql://u:p@localhost/unit"})
    app.extensions["goalstats_database"].dispose()
    reader.assert_not_called()
    assert dict(os.environ) == before
