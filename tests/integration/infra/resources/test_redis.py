"""Shared provider/readiness checks independent of Item/Action cache adapters."""

import json
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest
from sqlalchemy import text

from models.team import Team

pytestmark = [pytest.mark.postgres, pytest.mark.redis]


def _scenario_roundtrip(app, body):
    with app.extensions["goalstats_database"].transaction() as session:
        session.add_all(
            [
                Team(team_id=i, name=f"Team {i}", name_key=f"team {i}", category="test")
                for i in (1, 2)
            ]
        )
    client = app.test_client()
    created = client.post("/api/v1/scenarios", json=body)
    assert created.status_code == 201
    path = created.headers["Location"]
    assert client.get(path).json == created.json
    changed = client.patch(path, json={"match_minute": 80})
    assert changed.status_code == 200
    assert changed.json == {**created.json, "match_minute": 80}
    assert client.get(path).json == changed.json


def test_provider_json_ttl_misses_and_namespace_isolation(redis_app):
    cache = redis_app.extensions["goalstats_cache"]
    prefix = redis_app.extensions["goalstats_settings"].redis.cache_key_prefix
    key, other = prefix + ":first:value", prefix + ":second:value"
    assert cache.get(key) is None
    payload = {"name": "日本", "values": [1, None, True]}
    cache.set(key, payload, 30)
    cache.set(other, {"other": True}, 30)
    assert json.loads(cache.client.get(key)) == payload
    assert cache.get(key) == payload
    assert 0 < cache.client.ttl(key) <= 30
    cache.delete(key)
    assert cache.get(key) is None and cache.get(other) == {"other": True}
    cache.set(key, payload, 1)
    deadline = time.monotonic() + 3
    while cache.get(key) is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert cache.get(key) is None
    assert cache.get(other) == {"other": True}
    for invalid in (b"{broken", b"[]", b"null", b"\xff"):
        cache.client.set(key, invalid)
        assert cache.get(key) is None
    cache.delete(key)
    cache.delete(other)
    assert cache.client.exists(key, other) == 0


def test_redis_permission_outage_database_fallback_and_recovery(
    redis_app, app_factory, postgres_config, redis_url, scenario_body
):
    admin = redis_app.extensions["goalstats_cache"].client
    username, password = "goalstats_test_" + uuid4().hex, uuid4().hex
    prefix = redis_app.extensions["goalstats_settings"].redis.cache_key_prefix
    admin.execute_command(
        "ACL",
        "SETUSER",
        username,
        "on",
        ">" + password,
        "~" + prefix + ":*",
        "+get",
        "+set",
        "+del",
    )
    split = urlsplit(redis_url)
    url = urlunsplit(
        (
            split.scheme,
            f"{username}:{password}@{split.hostname}:{split.port or 6379}",
            split.path,
            "",
            "",
        )
    )
    app = app_factory({**postgres_config, "REDIS_URL": url, "CACHE_KEY_PREFIX": prefix})
    client = app.test_client()
    try:
        assert client.get("/ready").text == "Healthy"
        admin.execute_command("ACL", "SETUSER", username, "-@all")
        assert client.get("/ready").status_code == 200
        assert client.get("/ready").text == "Degraded"
        cache = app.extensions["goalstats_cache"]
        key = prefix + ":provider"
        assert cache.get(key) is None
        cache.set(key, {"value": "denied"}, 30)
        cache.delete(key)
        assert admin.get(key) is None
        _scenario_roundtrip(app, scenario_body)
        admin.execute_command("ACL", "SETUSER", username, "+get", "+set", "+del")
        assert client.get("/ready").text == "Healthy"
        cache.set(key, {"value": "recovered"}, 30)
        assert cache.get(key) == {"value": "recovered"}
        cache.delete(key)
        assert admin.get(key) is None
    finally:
        app.extensions["goalstats_cache"].close()
        admin.execute_command("ACL", "DELUSER", username)


def test_readiness_migration_and_table_mismatch(redis_app):
    client = redis_app.test_client()
    db = redis_app.extensions["goalstats_database"]
    assert client.get("/ready").text == "Healthy"
    with db.engine.begin() as connection:
        original = connection.scalar(text("SELECT version_num FROM alembic_version"))
        connection.execute(text("UPDATE alembic_version SET version_num='wrong_revision'"))
    try:
        assert client.get("/ready").status_code == 503
        assert client.get("/health").text == "Healthy"
    finally:
        with db.engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num=:revision"), {"revision": original}
            )
    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE teams RENAME TO unavailable_teams"))
    try:
        assert client.get("/ready").status_code == 503
    finally:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE unavailable_teams RENAME TO teams"))
    assert client.get("/ready").text == "Healthy"


def test_connection_outage_preserves_postgres_operations(
    postgres_app, app_factory, postgres_config, scenario_body
):
    app = app_factory({**postgres_config, "REDIS_URL": "redis://127.0.0.1:1/0"})
    client = app.test_client()
    assert client.get("/ready").text == "Degraded"
    _scenario_roundtrip(app, scenario_body)


def test_missing_required_column_is_unhealthy(redis_app):
    db = redis_app.extensions["goalstats_database"]
    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE teams RENAME COLUMN name TO unavailable_name"))
    try:
        assert redis_app.test_client().get("/ready").status_code == 503
    finally:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE teams RENAME COLUMN unavailable_name TO name"))
    assert redis_app.test_client().get("/ready").text == "Healthy"
