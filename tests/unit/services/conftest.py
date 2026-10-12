"""Transaction probes for normalized services; no database or provider calls."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from infra.repositories.scenario import ScenarioProjection
from models.scenario import Scenario


@pytest.fixture
def service_context(monkeypatch):
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

    def bind(module, name, repository):
        def factory(received):
            assert state.active and received is session
            return repository

        monkeypatch.setattr(module, name, factory)

    return SimpleNamespace(
        database=SimpleNamespace(transaction=transaction), events=events, state=state, bind=bind
    )


@pytest.fixture
def scenario_projection(scenario_body):
    row = Scenario(**scenario_body)
    row.scenario_id = 7
    row.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    row.team1_modifier_total = row.team2_modifier_total = 0
    return ScenarioProjection(row, "First", "Second")
