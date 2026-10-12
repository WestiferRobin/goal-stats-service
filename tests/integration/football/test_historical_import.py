import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from football.datasets import HistoricalImportError, import_datasets
from football.historical_import import import_historical_dataset
from models.competition import Competition
from models.hold.football import FootballHistory, FootballSnapshot, FootballTeam
from models.match import Match
from models.team import Team

pytestmark = pytest.mark.postgres


def counts(database):
    with database.transaction() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (Team, Competition, Match)
        )


def run(database, fixture, target, **kwargs):
    return import_historical_dataset(database, fixture.directory, target, **kwargs)


def test_insert_joins_idempotency_and_preserved_legacy(
    import_database, import_target, pinned_fixture
):
    with import_database.transaction() as session:
        import_datasets(session)
        before = {
            model: session.execute(select(model.__table__)).all()
            for model in (FootballTeam, FootballHistory, FootballSnapshot)
        }
    first = run(import_database, pinned_fixture, import_target)
    assert first.committed and first.insert_counts == "committed"
    assert (first.teams_inserted, first.competitions_inserted, first.matches_inserted) == (
        32,
        1,
        64,
    )
    with import_database.transaction() as session:
        rows = session.execute(
            select(Match.match_id, Match.source_record_key, Match.imported_at)
        ).all()
        join = session.execute(
            select(Match, Team, Competition)
            .join(Team, Match.home_team_id == Team.team_id)
            .join(Competition, Match.competition_id == Competition.competition_id)
        ).all()
        assert len(join) == 64
        assert all(
            team.offense is None and competition.edition_label == "2023"
            for _, team, competition in join
        )
        assert all(match.away_score == 0 and match.country == "Australia" for match, _, _ in join)
        assert all(session.get(Team, match.away_team_id) is not None for match, _, _ in join)
    second = run(import_database, pinned_fixture, import_target)
    assert second.unchanged == 64 and second.matches_inserted == second.teams_inserted == 0
    assert second.competitions_inserted == 0
    with import_database.transaction() as session:
        assert (
            session.execute(
                select(Match.match_id, Match.source_record_key, Match.imported_at)
            ).all()
            == rows
        )
        for model, values in before.items():
            assert session.execute(select(model.__table__)).all() == values
    assert counts(import_database) == (32, 1, 64)


def test_repeated_dry_run_never_writes_or_advances_sequences(
    import_database, import_target, pinned_fixture
):
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(import_database.engine, "before_cursor_execute", track)
    try:
        for _ in range(2):
            result = run(import_database, pinned_fixture, import_target, dry_run=True)
            assert not result.committed and result.insert_counts == "proposed"
            assert result.matches_inserted == 64
        assert not any(
            s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER"))
            for s in statements
        )
        assert any("READ ONLY" in s for s in statements)
    finally:
        event.remove(import_database.engine, "before_cursor_execute", track)
    assert counts(import_database) == (0, 0, 0)
    with import_database.transaction() as session:
        for name in (
            "teams_team_id_seq",
            "competitions_competition_id_seq",
            "matches_match_id_seq",
        ):
            assert session.scalar(text(f"SELECT is_called FROM {name}")) is False
    run(import_database, pinned_fixture, import_target)
    assert run(import_database, pinned_fixture, import_target, dry_run=True).unchanged == 64


@pytest.mark.parametrize("dry_run", [False, True])
def test_stored_conflict_aborts_without_changes(
    import_database, import_target, pinned_fixture, dry_run
):
    run(import_database, pinned_fixture, import_target)
    with import_database.transaction() as session:
        session.execute(text("UPDATE matches SET home_score = 30 WHERE match_id = 1"))
        session.execute(text("DELETE FROM matches WHERE match_id = 64"))
    with pytest.raises(HistoricalImportError, match="conflict") as error:
        run(import_database, pinned_fixture, import_target, dry_run=dry_run)
    assert error.value.summary.conflicts == 1
    assert not error.value.summary.committed
    assert error.value.summary.matches_inserted == 0
    assert counts(import_database) == (32, 1, 63)
    with import_database.transaction() as session:
        assert session.get(Match, 1).home_score == 30


def test_late_database_failure_rolls_back_all_inserts(
    import_database, import_target, pinned_fixture
):
    # A database-side failure on the last fixture match, after team/competition writes.
    with import_database.transaction() as session:
        session.execute(
            text("ALTER TABLE matches ADD CONSTRAINT test_late_failure CHECK (source_row <> 65)")
        )
        session.add(
            Team(name="Preexisting", name_key="preexisting", category="women_senior_national")
        )
    with pytest.raises(HistoricalImportError, match="not confirmed committed") as error:
        run(import_database, pinned_fixture, import_target)
    assert (error.value.summary.teams_inserted, error.value.summary.matches_inserted) == (0, 0)
    assert counts(import_database) == (1, 0, 0)


def test_failure_at_commit_does_not_report_success(import_database, import_target, pinned_fixture):
    def fail_commit(connection):
        raise IntegrityError("commit", {}, Exception("secret-do-not-print"))

    event.listen(import_database.engine, "commit", fail_commit)
    try:
        with pytest.raises(HistoricalImportError) as error:
            run(import_database, pinned_fixture, import_target)
        assert not error.value.summary.committed
        assert "secret-do-not-print" not in str(error.value)
    finally:
        event.remove(import_database.engine, "commit", fail_commit)
    assert counts(import_database) == (0, 0, 0)


def test_versions_reordering_duplicates_and_missing_records_preserve_existing(
    import_database, import_target, pinned_fixture, monkeypatch
):
    run(import_database, pinned_fixture, import_target)
    with import_database.transaction() as session:
        before = session.execute(select(Match.__table__).order_by(Match.match_id)).all()
        # An unrelated source record is never deletion-synchronized or merged.
        extra = dict(before[0]._mapping)
        extra.pop("match_id")
        extra["source"] = "another_source"
        session.execute(Match.__table__.insert().values(**extra))
    rows = list(reversed(pinned_fixture.rows))
    manifest = pinned_fixture.write(rows).model_copy(
        update={"upstream_revision": "test-new-version"}
    )
    monkeypatch.setattr(
        "football.historical_import.load_manifest",
        lambda dataset_id="womens-world-cup-2023": manifest,
    )
    result = run(import_database, pinned_fixture, import_target)
    assert result.matches_inserted == 0 and result.unchanged == 64 and result.duplicate_input == 0
    with import_database.transaction() as session:
        assert (
            session.execute(
                select(Match.__table__)
                .where(Match.source == "martj42_womens_results")
                .order_by(Match.match_id)
            ).all()
            == before
        )
    assert counts(import_database) == (32, 1, 65)
