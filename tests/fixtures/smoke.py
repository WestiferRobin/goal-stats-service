"""HTTP clients and read-only observations of the smoke runner's owned providers."""

import os
from dataclasses import dataclass

import psycopg
import pytest
from http_client import request
from redis import Redis
from test_ownership import verify_test_providers


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
    verify_test_providers()
    url = os.environ.get("SMOKE_BASE_URL", "")
    if url != "http://app:8000":
        pytest.fail("Smoke requires the canonical owned TEST application", pytrace=False)
    database_url = os.environ["TEST_DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    redis_url = os.environ["TEST_REDIS_URL"]
    prefix = "goal-stats-service:test:v1"
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
