"""HTTP clients and read-only observations of the smoke runner's owned providers."""

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import psycopg
import pytest
from http_client import request
from redis import Redis


@dataclass
class SmokeClient:
    url: str
    prefix: str
    redis: Redis
    database: psycopg.Connection
    fault: bool

    def request(self, path, method="GET", payload=None, expected=200, raw=None):
        return request(self.url, path, method, payload, expected, raw)

    def scalar(self, query, parameters=()):
        return self.database.execute(query, parameters).fetchone()[0]


@pytest.fixture(scope="session")
def smoke_client():
    project = os.environ.get("SMOKE_PROJECT", "")
    url = os.environ.get("SMOKE_BASE_URL", "")
    database_url = os.environ.get("SMOKE_DATABASE_URL", "")
    redis_url = os.environ.get("SMOKE_REDIS_URL", "")
    prefix = os.environ.get("SMOKE_CACHE_PREFIX", "")
    if not (
        re.fullmatch(r"goal-stats-service-cert-[a-f0-9]+", project)
        and url == "http://app:8000"
        and urlsplit(database_url).hostname == "postgres"
        and urlsplit(database_url).path == "/goal_stats_service_dev"
        and redis_url == "redis://redis:6379/0"
        and prefix == "goal-stats-service:dev:v1"
    ):
        pytest.fail(
            "Smoke requires the disposable stack configuration from make smoke", pytrace=False
        )
    cache = Redis.from_url(
        redis_url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3
    )
    database = None
    try:
        try:
            database = psycopg.connect(
                database_url,
                autocommit=True,
                connect_timeout=3,
                options="-c default_transaction_read_only=on",
            )
            cache.ping()
        except Exception:
            pytest.fail("Owned smoke providers are unavailable", pytrace=False)
        yield SmokeClient(url, prefix, cache, database, os.environ.get("SMOKE_FAULT") == "1")
    finally:
        cache.close()
        if database is not None:
            database.close()


@pytest.fixture
def smoke_item(smoke_client):
    item, headers = smoke_client.request("/items", "POST", {"name": "smoke"}, 201)
    try:
        assert headers["Location"] == "/items/" + item["id"]
        yield item
    finally:
        rows, _ = smoke_client.request("/items")
        exists = any(row["id"] == item["id"] for row in rows)
        smoke_client.request("/items/" + item["id"], "DELETE", expected=204 if exists else 404)
