import json
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.postgres, pytest.mark.redis]


def test_real_cache_roundtrip_ttl_invalidation_and_stale_child(redis_app):
    app = redis_app
    client = app.test_client()
    redis = app.extensions["goalstats_cache"].client
    item_cache, action_cache = (
        app.extensions["goalstats_item_cache"],
        app.extensions["goalstats_action_cache"],
    )
    item = client.post("/items", json={"name": "parent"}).json
    item_url = "/items/" + item["id"]
    key = item_cache.key(UUID(item["id"]))
    assert redis.get(key) is None
    assert client.get("/items").json == [item]
    assert redis.get(key) is None
    assert client.get(item_url).json == item
    assert json.loads(redis.get(key)) == item
    # The ownership-verified provider is unique to this serial test run; the
    # fixture also gives this application a unique key prefix. INFO and health
    # PINGs do not add key hits. Require exactly the repeated request's one GET.
    before_hits = redis.info("stats")["keyspace_hits"]
    assert client.get(item_url).json == item
    assert redis.info("stats")["keyspace_hits"] == before_hits + 1
    assert json.loads(redis.get(key)) == item
    assert 0 < redis.ttl(key) <= 300
    cached = item_cache.get(UUID(item["id"]))
    assert str(cached.id) == item["id"]
    assert cached.created_at.tzinfo is not None
    client.put(item_url, json={"name": "new", "status": "archived"})
    assert redis.get(key) is None
    assert client.get(item_url).json["name"] == "new"
    redis.set(key, b"{corrupt")
    assert client.get(item_url).json["name"] == "new"
    redis.set(key, b"{}")
    assert client.get(item_url).json["name"] == "new"
    redis.pexpire(key, 30)
    time.sleep(0.05)
    assert redis.get(key) is None
    action = client.post(item_url + "/actions", json={"name": "child", "type": "create"}).json
    action_url = "/actions/" + action["id"]
    action_key = action_cache.key(UUID(action["id"]))
    assert client.get(action_url).status_code == 200
    assert client.get(action_url).status_code == 200
    assert redis.get(action_key)
    assert client.delete(item_url).status_code == 204
    assert redis.get(key) is None
    assert redis.get(action_key)  # parent deletion does not scan Redis
    assert client.get(action_url).status_code == 404
    assert redis.get(action_key) is None


def test_action_update_and_delete_invalidation(redis_app):
    client = redis_app.test_client()
    redis = redis_app.extensions["goalstats_cache"].client
    parent = client.post("/items", json={"name": "x"}).json["id"]
    action = client.post("/actions", json={"itemId": parent, "name": "x", "type": "create"}).json[
        "id"
    ]
    url = "/actions/" + action
    key = redis_app.extensions["goalstats_action_cache"].key(UUID(action))
    client.get(url)
    assert redis.get(key)
    client.put(url, json={"name": "new", "type": "update"})
    assert redis.get(key) is None
    assert client.get(url).json["type"] == "update"
    assert client.delete(url).status_code == 204
    assert redis.get(key) is None


def test_failed_real_commit_does_not_invalidate_cache(redis_app, monkeypatch):
    from sqlalchemy.orm import Session

    client = redis_app.test_client()
    item = client.post("/items", json={"name": "before"}).json
    url = "/items/" + item["id"]
    client.get(url)
    key = redis_app.extensions["goalstats_item_cache"].key(UUID(item["id"]))
    redis = redis_app.extensions["goalstats_cache"].client
    original = redis.get(key)
    # Real PostgreSQL transaction has flushed UPDATE, then fails before commit.
    from sqlalchemy import event

    def fail_commit(session):
        raise RuntimeError("private commit detail")

    event.listen(Session, "before_commit", fail_commit)
    try:
        response = client.put(url, json={"name": "after", "status": "archived"})
        assert response.status_code == 500 and "private" not in response.text
        assert redis.get(key) == original
    finally:
        event.remove(Session, "before_commit", fail_commit)
    db = redis_app.extensions["goalstats_database"]
    with db.engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT name FROM items WHERE id=:id"), {"id": item["id"]})
            == "before"
        )


def test_redis_permission_outage_database_fallback_and_recovery(
    redis_app, app_factory, postgres_config, redis_url
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
        item = client.post("/items", json={"name": "db survives"}).json
        path = "/items/" + item["id"]
        assert client.get(path).json == item
        assert client.put(path, json={"name": "updated", "status": "active"}).status_code == 200
        assert client.get(path).json["name"] == "updated"
        admin.execute_command("ACL", "SETUSER", username, "+get", "+set", "+del")
        assert client.get("/ready").text == "Healthy"
        assert client.get(path).json["name"] == "updated"
        assert admin.get(app.extensions["goalstats_item_cache"].key(UUID(item["id"])))
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
        connection.execute(text("ALTER TABLE actions RENAME TO unavailable_actions"))
    try:
        assert client.get("/ready").status_code == 503
    finally:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE unavailable_actions RENAME TO actions"))
    assert client.get("/ready").text == "Healthy"


def test_connection_outage_preserves_postgres_operations(
    postgres_app, app_factory, postgres_config
):
    app = app_factory({**postgres_config, "REDIS_URL": "redis://127.0.0.1:1/0"})
    client = app.test_client()
    assert client.get("/ready").text == "Degraded"
    item = client.post("/items", json={"name": "without cache"}).json
    path = "/items/" + item["id"]
    assert client.get(path).json == item
    assert client.put(path, json={"name": "changed", "status": "archived"}).status_code == 200
    assert client.get(path).json["name"] == "changed"
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404


def test_missing_required_column_is_unhealthy(redis_app):
    db = redis_app.extensions["goalstats_database"]
    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE items RENAME COLUMN name TO unavailable_name"))
    try:
        assert redis_app.test_client().get("/ready").status_code == 503
    finally:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE items RENAME COLUMN unavailable_name TO name"))
    assert redis_app.test_client().get("/ready").text == "Healthy"
