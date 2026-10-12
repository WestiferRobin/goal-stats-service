"""Real shared-service concurrency, independent of retiring template caches."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Barrier, Lock

import pytest

from schemas.scenario import ScenarioCreate, ScenarioPatch
from services.scenario import ScenarioService

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("fail_one", [False, True])
def test_shared_scenario_service_isolates_concurrent_transactions(
    scenario_client, scenario_body, import_database, monkeypatch, fail_one
):
    service = ScenarioService(import_database)
    saved = [service.create(ScenarioCreate(**scenario_body)) for _ in range(2)]
    operation = ContextVar("operation")
    barrier, lock = Barrier(2, timeout=10), Lock()
    sessions, outcomes = {}, {}
    original = vars(service).copy()

    @contextmanager
    def transaction():
        index = operation.get()
        try:
            with import_database.sessions.begin() as session:
                with lock:
                    sessions[index] = session
                yield session
                # Both independent updates have flushed before either can commit.
                barrier.wait()
                if fail_one and index == 0:
                    raise RuntimeError("isolated commit failure")
            outcomes[index] = "commit"
        except BaseException:
            outcomes[index] = "rollback"
            raise

    def update(index):
        operation.set(index)
        return service.update(saved[index]["scenario_id"], ScenarioPatch(match_minute=80 + index))

    with monkeypatch.context() as patch:
        patch.setattr(import_database, "transaction", transaction)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(update, i) for i in range(2)]
            for index, future in enumerate(futures):
                if fail_one and index == 0:
                    with pytest.raises(RuntimeError, match="isolated commit failure"):
                        future.result(timeout=15)
                else:
                    assert future.result(timeout=15)["match_minute"] == 80 + index
    assert sessions[0] is not sessions[1]
    assert outcomes == {0: "rollback" if fail_one else "commit", 1: "commit"}
    assert import_database.engine.pool.checkedout() == 0
    for index in (0, 1):
        expected = (
            saved[index]
            if fail_one and index == 0
            else {**saved[index], "match_minute": 80 + index}
        )
        assert service.get(saved[index]["scenario_id"]) == expected
        from sqlalchemy import text
        from sqlalchemy.exc import InvalidRequestError

        with pytest.raises(InvalidRequestError):
            sessions[index].execute(text("SELECT 1"))
    assert vars(service) == original
