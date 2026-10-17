from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Barrier, Lock

import pytest

from infra.repositories.match import MatchRepository
from infra.repositories.scenario import ScenarioRepository
from infra.repositories.team import TeamRepository
from schemas.scenario import ScenarioCreate, ScenarioPatch
from services.match import MatchService
from services.scenario import ScenarioService
from services.team import TeamService


@pytest.mark.postgres
@pytest.mark.parametrize("fail_one", [False, True])
def test_shared_scenario_service_isolates_concurrent_transactions(
    scenario_client, scenario_body, import_database, monkeypatch, fail_one
):
    service = ScenarioService(
        repo=ScenarioRepository(import_database),
        team_service=TeamService(repo=TeamRepository(import_database)),
        match_service=MatchService(
            repo=MatchRepository(import_database),
            team_service=TeamService(repo=TeamRepository(import_database)),
        ),
    )
    repositories = [service.repo, service.team_service.repo, service.match_service.repo]
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

    assert all(vars(repo) == {"database": import_database} for repo in repositories)


@pytest.mark.postgres
@pytest.mark.parametrize("fail", [False, True])
def test_composed_creation_shares_session_and_holds_locks_until_completion(
    scenario_client, scenario_body, import_database, monkeypatch, fail
):
    from sqlalchemy import func, select, text
    from sqlalchemy.exc import OperationalError

    from models.scenario import Scenario

    teams = TeamService(repo=TeamRepository(import_database))
    matches = MatchService(
        repo=MatchRepository(import_database),
        team_service=TeamService(repo=TeamRepository(import_database)),
    )
    service = ScenarioService(
        repo=ScenarioRepository(import_database), team_service=teams, match_service=matches
    )
    observed = []
    team_call = teams.require_participants_in_transaction
    match_call = matches.require_match_participants_in_transaction
    add = service.repo.add

    def team_check(instance, **kwargs):
        assert instance is teams
        observed.append(kwargs["session"])
        return team_call(**kwargs)

    def match_check(instance, **kwargs):
        assert instance is matches
        observed.append(kwargs["session"])
        return match_call(**kwargs)

    def checked_add(instance, session, row):
        assert instance is service.repo
        assert observed == [session, session]
        # Probe after both collaborators return: locks must belong to the outer transaction.
        for table, column in [("teams", "team_id"), ("matches", "match_id")]:
            with import_database.sessions() as contender:
                with pytest.raises(OperationalError) as error:
                    contender.execute(
                        text(f"SELECT * FROM {table} WHERE {column}=1 FOR UPDATE NOWAIT")
                    )
                assert error.value.orig.sqlstate == "55P03"
        add(session, row)
        if fail:
            raise RuntimeError("rollback after insertion")

    original_states = [vars(obj).copy() for obj in (service, teams, matches)]
    with monkeypatch.context() as patch:
        patch.setattr(TeamService, "require_participants_in_transaction", team_check)
        patch.setattr(MatchService, "require_match_participants_in_transaction", match_check)
        patch.setattr(ScenarioRepository, "add", checked_add)
        body = ScenarioCreate(**{**scenario_body, "match_id": 1})
        if fail:
            with pytest.raises(RuntimeError, match="rollback after insertion"):
                service.create(body)
        else:
            assert service.create(body)["match_id"] == 1
    with import_database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Scenario)) == (0 if fail else 1)
        for table, column in [("teams", "team_id"), ("matches", "match_id")]:
            session.execute(text(f"SELECT * FROM {table} WHERE {column}=1 FOR UPDATE NOWAIT"))
    assert import_database.engine.pool.checkedout() == 0
    assert [vars(obj) for obj in (service, teams, matches)] == original_states
