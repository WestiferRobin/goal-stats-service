"""Explicit synthetic model inputs shared by integration and HTTP tests."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from infra.repositories.scenario import ScenarioProjection
from models.scenario import Scenario


@pytest.fixture
def scenario_body():
    body = {
        "title": "Synthetic scenario fixture",
        "team1_id": 1,
        "team2_id": 2,
        "match_id": None,
        "match_minute": 65,
    }
    for side in (1, 2):
        for field in (
            "goals",
            "shots",
            "shots_on_target",
            "big_chances",
            "defender_blocks",
            "goalkeeper_saves",
            "corners",
            "yellow_cards",
            "red_cards",
        ):
            body[f"team{side}_{field}"] = 0
        body[f"team{side}_possession"] = 50
        for field in ("offense", "defense", "form", "star_power", "clutch"):
            body[f"team{side}_{field}"] = 70
    return body


@pytest.fixture
def service_context():
    events = []
    session = object()
    state = SimpleNamespace(active=False)

    @contextmanager
    def transaction():
        assert not state.active
        state.active = True
        events.append("begin")
        try:
            yield session
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")
        finally:
            state.active = False

    database = SimpleNamespace(transaction=transaction)
    repositories = {}

    def repository(name, methods):
        def checked(method):
            def call(received, *args, **kwargs):
                assert state.active and received is session
                return method(*args, **kwargs)

            return call

        repo = SimpleNamespace(
            database=database,
            transaction=transaction,
            **{name: checked(method) for name, method in vars(methods).items()},
        )
        repositories[name] = repo
        return repo

    services = {}

    def service(name, methods):
        def checked(method):
            def call(*, session: object, **kwargs):
                assert state.active and session is borrowed_session
                return method(**kwargs)

            return call

        obj = SimpleNamespace(
            database=database,
            **{name: checked(method) for name, method in vars(methods).items()},
        )
        services[name] = obj
        return obj

    borrowed_session = session
    return SimpleNamespace(
        service=service,
        services=services,
        session=session,
        database=database,
        events=events,
        state=state,
        repository=repository,
        repositories=repositories,
    )


@pytest.fixture
def scenario_projection(scenario_body):
    row = Scenario(**scenario_body)
    row.scenario_id = 7
    row.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    row.team1_modifier_total = row.team2_modifier_total = 0
    return ScenarioProjection(row, "First", "Second")
