import csv
import json
import random
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from football.datasets import HistoricalImportError
from football.historical_dataset import (
    APPROVED_DATASETS,
    load_manifest,
    name_key,
    source_record_key,
)
from football.historical_import import import_historical_dataset
from models.competition import Competition
from models.match import Match
from models.team import Team
from tests.fixtures.historical_database import invoke, snapshot

SQL = (Path(__file__).resolve().parents[3] / "sql/verify_historical_import.sql").read_text()

SQL = "\n".join(line for line in SQL.splitlines() if not line.startswith("\\"))


@pytest.mark.postgres
def test_all_editions_cli_dry_run_import_repeat_and_shared_identities(
    import_database, import_target, edition_source, monkeypatch
):
    directory, manifests = edition_source

    def forbidden(*args, **kwargs):
        pytest.fail("Historical import must never read prototype CSVs")

    from football import cli

    assert not hasattr(cli, "import_datasets")
    before = edition_snapshot(import_database)
    for dataset, manifest in manifests.items():
        result = invoke(import_database, import_target, directory, dataset, "--dry-run")
        assert result.exit_code == 0, result.output
        summary = json.loads(result.output)
        assert summary["matches_inserted"] == manifest.expected_counts.matches
        assert not summary["committed"]
    assert edition_snapshot(import_database) == before

    # Import 2023 first so later editions must reuse its team IDs without rewriting anything.
    datasets = [APPROVED_DATASETS[-1], *APPROVED_DATASETS[:-1]]
    original_2023 = None
    for dataset in datasets:
        result = invoke(import_database, import_target, directory, dataset)
        assert result.exit_code == 0, result.output
        summary = json.loads(result.output)
        assert summary["matches_inserted"] == manifests[dataset].expected_counts.matches
        if dataset.endswith("2023"):
            original_2023 = edition_snapshot(import_database)
    with import_database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Team)) == 44
        assert session.scalar(select(func.count()).select_from(Competition)) == 9
        assert session.scalar(select(func.count()).select_from(Match)) == 348
        for manifest in manifests.values():
            competition = session.scalar(
                select(Competition).where(
                    Competition.edition_label == manifest.competition.edition_label
                )
            )
            matches = session.scalars(
                select(Match).where(Match.competition_id == competition.competition_id)
            ).all()
            assert len(matches) == manifest.expected_counts.matches
            assert len({m.home_team_id for m in matches} | {m.away_team_id for m in matches}) == (
                manifest.expected_counts.teams
            )
            assert (
                sum(m.home_score + m.away_score for m in matches) == manifest.approval.total_goals
            )
    after = edition_snapshot(import_database)
    assert original_2023 is not None
    for table in ("teams", "competitions", "matches"):
        assert all(row in after[table] for row in original_2023[table])
    for table in ("football_teams", "football_history", "football_snapshots"):
        assert table not in after and table not in before
    for dataset, manifest in manifests.items():
        result = invoke(import_database, import_target, directory, dataset)
        assert result.exit_code == 0, result.output
        summary = json.loads(result.output)
        assert summary["unchanged"] == manifest.expected_counts.matches
        assert summary["teams_inserted"] == summary["competitions_inserted"] == 0
        assert summary["matches_inserted"] == 0
        dry = invoke(import_database, import_target, directory, dataset, "--dry-run")
        assert dry.exit_code == 0, dry.output
    assert edition_snapshot(import_database) == after


def edition_snapshot(database):
    with database.transaction() as session:
        return {
            model.__tablename__: session.execute(select(model.__table__)).all()
            for model in (Team, Competition, Match)
        }


@pytest.mark.postgres
@pytest.mark.parametrize("failure", ["conflict", "wrong_target", "old_head", "missing_source"])
def test_earlier_edition_failure_preserves_records(
    import_database, import_target, edition_source, failure
):
    directory, _ = edition_source
    dataset = "womens-world-cup-1991"
    if failure == "conflict":
        import_historical_dataset(import_database, directory, import_target, dataset_id=dataset)
        with import_database.transaction() as session:
            session.execute(text("UPDATE matches SET home_score = 100 WHERE match_id = 1"))
    elif failure == "old_head":
        with import_database.transaction() as session:
            session.execute(text("UPDATE alembic_version SET version_num = 'd94f81ab2301'"))
    elif failure == "missing_source":
        (directory / "results.csv").unlink()
    before = edition_snapshot(import_database)
    options = ("--expect-host", "wrong-host") if failure == "wrong_target" else ()
    result = invoke(import_database, import_target, directory, dataset, *options)
    assert result.exit_code != 0
    assert edition_snapshot(import_database) == before
    assert not json.loads(next(s for s in result.output.splitlines() if s.startswith("{")))[
        "committed"
    ]


@pytest.mark.postgres
def test_later_transaction_failure_preserves_prior_commits_and_retry(
    import_database, import_target, edition_source
):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    directory, _ = edition_source
    for dataset in APPROVED_DATASETS[:2]:
        assert invoke(import_database, import_target, directory, dataset).exit_code == 0
    before = edition_snapshot(import_database)

    def interrupt_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO matches"):
            raise OperationalError(statement, None, RuntimeError("disposable injected failure"))

    event.listen(import_database.engine, "before_cursor_execute", interrupt_insert)
    try:
        failure = invoke(import_database, import_target, directory, APPROVED_DATASETS[2])
        assert failure.exit_code != 0
        assert "not confirmed committed" in failure.output
    finally:
        event.remove(import_database.engine, "before_cursor_execute", interrupt_insert)
    assert edition_snapshot(import_database) == before
    for dataset in APPROVED_DATASETS:
        result = invoke(import_database, import_target, directory, dataset)
        assert result.exit_code == 0, result.output
        if dataset in APPROVED_DATASETS[:2]:
            assert json.loads(result.output)["matches_inserted"] == 0
    after = edition_snapshot(import_database)
    assert [len(after[t]) for t in ("teams", "competitions", "matches")] == [44, 9, 348]
    for table in ("teams", "competitions", "matches"):
        assert all(row in after[table] for row in before[table])


@pytest.mark.postgres
def test_insert_joins_idempotency_and_preserved_legacy(
    import_database, import_target, pinned_fixture
):
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
    assert counts(import_database) == (32, 1, 64)


def counts(database):
    with database.transaction() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (Team, Competition, Match)
        )


def run(database, fixture, target, **kwargs):
    return import_historical_dataset(database, fixture.directory, target, **kwargs)


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
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


@pytest.mark.postgres
@pytest.mark.parametrize("complete", [False, True])
def test_complete_fixture_passes_both_modes_and_preserves_every_row(import_database, complete):
    populate(import_database, APPROVED_DATASETS)
    first = verify(import_database, complete=complete)
    assert first["acceptance_passed"] == 1 and first["transaction_read_only"] == "on"
    assert sum(e["matches"] for e in first["coverage"]) == 348
    assert first["preservation"]["teams"]["rows"] == 44
    second = verify(import_database, complete=complete, preservation=first["preservation"])
    assert second == first


def populate(database, datasets):
    """Synthetic approved-sized fixture; no ignored source or runtime validation bypass."""
    with database.transaction() as session:
        teams = {}
        for dataset in datasets:
            m = load_manifest(dataset)
            for label in m.approval.participants:
                if label not in teams:
                    team = Team(name=label, name_key=name_key(label), category=m.team_category)
                    session.add(team)
                    session.flush()
                    teams[label] = team.team_id
            competition = Competition(
                name=m.competition.name,
                name_key=m.competition.name_key,
                edition_label=m.competition.edition_label,
                category=m.team_category,
            )
            session.add(competition)
            session.flush()
            names = m.approval.participants
            goals, remainder = divmod(m.approval.total_goals, m.expected_counts.matches)
            for i in range(m.expected_counts.matches):
                pair = i % (len(names) // 2)
                home, away = names[2 * pair : 2 * pair + 2]
                played = m.selection.date_from + timedelta(days=i // (len(names) // 2))
                session.add(
                    Match(
                        competition_id=competition.competition_id,
                        home_team_id=teams[home],
                        away_team_id=teams[away],
                        match_date=played,
                        home_score=goals + (i < remainder),
                        away_score=0,
                        score_basis=m.score_basis,
                        source=m.source,
                        source_record_key=source_record_key(
                            source=m.source,
                            category=m.team_category,
                            competition_key=m.competition.name_key,
                            edition=m.competition.edition_label,
                            match_date=played,
                            source_home_team=home,
                            source_away_team=away,
                        ),
                        source_version=m.upstream_revision,
                        source_file_sha256=m.sha256,
                        source_row=i + 2,
                        source_url=m.source_url,
                        source_home_team=home,
                        source_away_team=away,
                        source_tournament=m.selection.tournament,
                    )
                )


def verify(database, *, complete=False, preservation=None, database_name="", sql=SQL):
    with database.engine.connect() as connection:
        for key, value in {
            "verify_complete": str(complete).lower(),
            "verify_database": database_name,
            "verify_preservation": json.dumps(preservation) if preservation else "",
        }.items():
            connection.execute(
                text("SELECT set_config(:key, :value, false)"),
                {"key": "goalstats." + key, "value": value},
            )
        connection.commit()
        cursor = connection.connection.driver_connection.cursor()
        try:
            cursor.execute(sql)
            result = None
            while True:
                if cursor.description:
                    result = dict(
                        zip([c.name for c in cursor.description], cursor.fetchone(), strict=True)
                    )
                if not cursor.nextset():
                    break
            return result
        finally:
            cursor.close()


@pytest.mark.postgres
def test_current_2023_passes_but_complete_rejects_missing_editions(import_database):
    populate(import_database, ["womens-world-cup-2023"])
    assert verify(import_database)["acceptance_passed"] == 1
    with pytest.raises(psycopg.Error, match="Historical verification failed"):
        verify(import_database, complete=True)


@pytest.mark.postgres
@pytest.mark.parametrize(
    "mutation",
    [
        "DELETE FROM matches WHERE match_id = 1",
        "UPDATE teams SET name_key = 'unexpected' WHERE team_id = 1",
        "UPDATE competitions SET category = 'wrong'",
        "UPDATE competitions SET edition_label = '2027'",
        "UPDATE matches SET source = 'other' WHERE match_id = 1",
        "UPDATE matches SET source_version = 'wrong' WHERE match_id = 1",
        "UPDATE matches SET source_file_sha256 = repeat('0',64) WHERE match_id = 1",
        "UPDATE matches SET source_url = 'https://example.org' WHERE match_id = 1",
        "UPDATE matches SET match_date = '2022-01-01' WHERE match_id = 1",
        "UPDATE matches SET home_score = home_score + 1 WHERE match_id = 1",
        "UPDATE matches SET away_team_id = 3 WHERE away_team_id = 2",
        "UPDATE alembic_version SET version_num = 'f6b82d14c903'",
    ],
)
def test_invalid_current_state_is_rejected(import_database, mutation):
    populate(import_database, ["womens-world-cup-2023"])
    with import_database.transaction() as session:
        session.execute(text(mutation))
    with pytest.raises(psycopg.Error, match="Historical verification failed"):
        verify(import_database)


@pytest.mark.postgres
@pytest.mark.parametrize(
    "kind", ["duplicate", "orphan_team", "orphan_competition", "negative_score"]
)
def test_detects_corruption_even_if_database_constraints_were_removed(import_database, kind):
    populate(import_database, ["womens-world-cup-2023"])
    with import_database.transaction() as session:
        constraints = session.execute(
            text(
                "SELECT conname, contype FROM pg_constraint "
                "WHERE conrelid = 'matches'::regclass AND contype IN ('u','f','c')"
            )
        ).all()
        for name, _ in constraints:
            session.execute(text(f'ALTER TABLE matches DROP CONSTRAINT "{name}"'))
        mutation = {
            "duplicate": (
                "UPDATE matches SET source_record_key = "
                "(SELECT source_record_key FROM matches WHERE match_id=1) WHERE match_id=2"
            ),
            "orphan_team": "UPDATE matches SET home_team_id = -1 WHERE match_id=1",
            "orphan_competition": "UPDATE matches SET competition_id = -1 WHERE match_id=1",
            "negative_score": "UPDATE matches SET home_score = -1 WHERE match_id=1",
        }[kind]
        session.execute(text(mutation))
    with pytest.raises(psycopg.Error, match="Historical verification failed"):
        verify(import_database)


@pytest.mark.postgres
def test_preservation_and_unrelated_records(scenario_client, scenario_body, import_database):
    response = scenario_client.post("/api/v1/scenarios", json=scenario_body)
    assert response.status_code == 201
    scenario = response.json["scenario_id"]
    assert scenario_client.post(f"/api/v1/scenarios/{scenario}/predictions").status_code == 201
    first = verify(import_database)
    assert first["preservation"]["scenarios"]["rows"] == 1
    assert first["preservation"]["predictions"]["rows"] == 1
    assert set(first["preservation"]) == {
        "teams",
        "competitions",
        "matches",
        "scenarios",
        "predictions",
    }
    assert verify(import_database, preservation=first["preservation"]) == first
    with import_database.transaction() as session:
        session.execute(text("UPDATE scenarios SET title = 'changed'"))
    with pytest.raises(psycopg.Error, match="record preservation"):
        verify(import_database, preservation=first["preservation"])


@pytest.mark.postgres
def test_identity_and_read_only_enforcement(import_database):
    with pytest.raises(psycopg.Error, match="database identity"):
        verify(import_database, database_name="not-this-database")
    attempted_write = SQL.replace("WITH expected AS", "DELETE FROM teams;\nWITH expected AS", 1)
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        verify(import_database, sql=attempted_write)


@pytest.mark.pinned_source
@pytest.mark.postgres
def test_pinned_source_import_repeat_and_application_restart(
    pinned_source,
    import_database,
    import_target,
    postgres_config,
    app_factory,
    monkeypatch,
    scenario_body,
):
    source = pinned_source
    before = snapshot(import_database)
    assert all(not rows for table, rows in before.items() if table != "alembic_version")
    monkeypatch.setattr("main.Database", lambda _: import_database)
    app = app_factory(postgres_config)
    client = app.test_client()
    spec = client.get("/swagger/v1/swagger.json").json
    for path in ("/health", "/ready", "/api/v1/catalog/teams"):
        assert client.get(path).status_code == 200
    for path in ("teams", "competitions", "matches"):
        assert client.get(f"/api/v1/catalog/{path}").json == []
    assert snapshot(import_database) == before

    from football import cli

    assert not hasattr(cli, "import_datasets")
    for dataset in APPROVED_DATASETS:
        dry = invoke(import_database, import_target, source.parent, dataset, "--dry-run")
        assert dry.exit_code == 0, dry.output
        assert not json.loads(dry.output)["committed"]
    assert snapshot(import_database) == before
    preserved_user_records = None
    original_2023 = None
    reports = []
    for dataset in (APPROVED_DATASETS[-1], *APPROVED_DATASETS[:-1]):
        result = invoke(import_database, import_target, source.parent, dataset)
        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["committed"]
        assert report["matches_inserted"] == load_manifest(dataset).expected_counts.matches
        reports.append(report)
        if dataset.endswith("2023"):
            original_2023 = snapshot(import_database)
            teams = client.get("/api/v1/catalog/teams").json
            ids = {t["name"]: t["team_id"] for t in teams}
            # Ratings and in-play values are synthetic assumptions, never historical facts.
            scenario_body.update(
                title="Synthetic assumptions for real Spain/England identities",
                team1_id=ids["Spain"],
                team2_id=ids["England"],
            )
            created = client.post("/api/v1/scenarios", json=scenario_body)
            assert created.status_code == 201, created.json
            prediction = client.post(f"/api/v1/scenarios/{created.json['scenario_id']}/predictions")
            assert prediction.status_code == 201, prediction.json
            from schemas.prediction import SavedPredictionResponse

            saved_prediction = prediction.json
            SavedPredictionResponse.model_validate(saved_prediction)
            assert saved_prediction["model_version"] == "road-to-the-final-heuristic-v1"
            captured = saved_prediction["input_snapshot"]
            assert captured["adapter_version"] == "scenario-v1"
            assert captured["team1_name"] == "Spain" and captured["team2_name"] == "England"
            for key, value in scenario_body.items():
                assert captured[key] == value
            history_path = f"/api/v1/scenarios/{created.json['scenario_id']}/predictions"
            second = client.post(history_path)
            assert second.status_code == 201, second.json
            SavedPredictionResponse.model_validate(second.json)
            assert second.json["prediction_id"] > saved_prediction["prediction_id"]
            assert second.json["input_snapshot"] == captured
            assert second.json["output"] == saved_prediction["output"]
            saved_predictions = [second.json, saved_prediction]
            assert client.get(history_path).json == saved_predictions
            assert client.get(history_path + "?limit=1&offset=1").json == [saved_prediction]
            preserved_user_records = snapshot(import_database)
    after = snapshot(import_database)
    assert [len(after[t]) for t in ("teams", "competitions", "matches")] == [44, 9, 348]
    assert original_2023 is not None
    for table in ("teams", "competitions", "matches"):
        assert set(original_2023[table]) <= set(after[table])
    for table in (
        "football_teams",
        "football_history",
        "football_snapshots",
    ):
        assert table not in after and table not in before
    assert preserved_user_records is not None
    for table in ("scenarios", "predictions"):
        assert after[table] == preserved_user_records[table]
        assert len(after[table]) == (1 if table == "scenarios" else 2)

    # Verify persisted facts against the actual CSV, independently of importer reports.
    manifests = {
        load_manifest(d).competition.edition_label: load_manifest(d) for d in APPROVED_DATASETS
    }
    with source.open(newline="") as stream:
        expected = {
            (row["date"], row["home_team"], row["away_team"]): (ordinal, row)
            for ordinal, row in enumerate(csv.DictReader(stream), 2)
            if row["tournament"] == "FIFA World Cup" and row["date"][:4] in manifests
        }
    stored = [json.loads(row) for row in after["matches"]]
    team_rows = {json.loads(row)["team_id"]: json.loads(row) for row in after["teams"]}
    competition_rows = {
        json.loads(row)["competition_id"]: json.loads(row) for row in after["competitions"]
    }
    assert len(expected) == len(stored) == 348
    assert sum(row["home_score"] + row["away_score"] for row in stored) == 1081
    assert (
        set(before)
        == set(after)
        == {"teams", "competitions", "matches", "scenarios", "predictions", "alembic_version"}
    )
    for row in stored:
        key = (row["match_date"], row["source_home_team"], row["source_away_team"])
        ordinal, raw = expected[key]
        manifest = manifests[row["match_date"][:4]]
        assert row["source_row"] == ordinal
        assert row["source_version"] == manifest.upstream_revision
        assert row["source_file_sha256"] == manifest.sha256
        assert row["source_url"] == manifest.source_url
        assert row["source"] == manifest.source
        assert (row["home_score"], row["away_score"]) == (
            int(raw["home_score"]),
            int(raw["away_score"]),
        )
        assert row["score_basis"] == manifest.score_basis
        assert competition_rows[row["competition_id"]]["edition_label"] == raw["date"][:4]
        for side in ("home", "away"):
            assert team_rows[row[f"{side}_team_id"]]["name_key"] == name_key(raw[f"{side}_team"])
    assert {(r["match_date"], r["source_home_team"], r["source_away_team"]) for r in stored} == set(
        expected
    )
    for year, manifest in manifests.items():
        edition = [r for r in stored if r["match_date"][:4] == year]
        assert len(edition) == manifest.expected_counts.matches
        assert (
            sum(r["home_score"] + r["away_score"] for r in edition) == manifest.approval.total_goals
        )

    def get(path):
        response = client.get(path)
        assert response.status_code == 200, (path, response.json)
        assert response.content_type == "application/json"
        return response.json

    teams = get("/api/v1/catalog/teams")
    assert {t["team_id"] for t in teams} == set(team_rows)
    for t in teams:
        assert t["name"] == team_rows[t["team_id"]]["name"]
        assert t["category"] == "women_senior_national"
        assert all(
            t[k] is None
            for k in ("offense", "defense", "form", "star_power", "clutch", "fifa_rank")
        )
        assert t["prediction_ready"] is False
    competitions = get("/api/v1/catalog/competitions")
    assert {c["competition_id"] for c in competitions} == set(competition_rows)
    assert {c["edition_label"] for c in competitions} == set(manifests)
    catalog = get("/api/v1/catalog/matches?limit=200") + get(
        "/api/v1/catalog/matches?limit=200&offset=200"
    )
    assert len(catalog) == 348
    assert [r["match_id"] for r in catalog] == [
        r["match_id"] for r in sorted(stored, key=lambda r: (r["match_date"], r["match_id"]))
    ]
    stored_by_id = {r["match_id"]: r for r in stored}
    for row in catalog:
        original = stored_by_id[row["match_id"]]
        for key in (
            "match_date",
            "competition_id",
            "home_team_id",
            "away_team_id",
            "home_score",
            "away_score",
            "score_basis",
            "neutral",
            "city",
            "country",
        ):
            assert row[key] == original[key]
        assert row["home_team_name"] == team_rows[row["home_team_id"]]["name"]
        assert row["away_team_name"] == team_rows[row["away_team_id"]]["name"]
    final = next(r for r in catalog if r["match_date"] == "2023-08-20")
    assert (
        final["home_team_name"],
        final["away_team_name"],
        final["home_score"],
        final["away_score"],
    ) == ("Spain", "England", 1, 0)
    assert get(f"/api/v1/catalog/matches/{final['match_id']}") == final
    assert get(f"/api/v1/catalog/matches?competition_id={final['competition_id']}&limit=200") == [
        r for r in catalog if r["edition_label"] == "2023"
    ]
    assert (
        get(f"/api/v1/catalog/matches?team_id={ids['Spain']}&limit=2&offset=1")
        == [r for r in catalog if ids["Spain"] in (r["home_team_id"], r["away_team_id"])][1:3]
    )
    insight = get(
        f"/api/v1/catalog/matches/insights?team1_id={ids['Spain']}&team2_id={ids['England']}&limit=200"
    )
    assert insight["head_to_head"] == [final]
    assert insight["team1_history"] == [
        r for r in catalog if ids["Spain"] in (r["home_team_id"], r["away_team_id"])
    ]
    assert insight["source"] == "approved_historical_results"
    # Unsaved calculation and hypothetical simulation do not insert any records.
    preview = client.post(
        "/api/v1/predictions/preview",
        json={k: v for k, v in scenario_body.items() if k not in {"title", "match_id"}},
    )
    assert preview.status_code == 200 and preview.json == saved_prediction["output"]
    state = random.getstate()
    try:
        random.seed(514)
        simulation = client.post(
            "/api/v1/competitions/simulate",
            json={
                "teams": [
                    dict(
                        team_id=t["team_id"],
                        offense=70,
                        defense=70,
                        form=70,
                        star_power=70,
                        clutch=70,
                    )
                    for t in teams[:4]
                ]
            },
        )
    finally:
        random.setstate(state)
    assert simulation.status_code == 200, simulation.json
    from schemas.competition.response import TournamentResponse

    TournamentResponse.model_validate(simulation.json)
    assert simulation.json["kind"] == "hypothetical_knockout"
    assert {r["team"] for r in simulation.json["results"]} == {t["name"] for t in teams[:4]}
    assert sum(r["champion_probability"] for r in simulation.json["results"]) == pytest.approx(100)
    assert snapshot(import_database) == after
    inventory = json.loads(
        (Path(__file__).resolve().parents[1] / "router_inventory.json").read_text()
    )
    # The separately maintained approved inventory also guards against legacy API reintroduction.
    assert (
        sorted(
            [
                rule.rule,
                rule.endpoint,
                sorted(rule.methods),
                rule.strict_slashes,
                {key: type(value).__name__ for key, value in rule._converters.items()},
            ]
            for rule in app.url_map.iter_rules()
        )
        == inventory["routes"]
    )
    assert list(app.blueprints) == inventory["blueprints"]
    for path in (
        "/api/v1/teams",
        "/api/v1/snapshots",
        "/api/v1/history",
        "/api/v1/insights",
        "/api/v1/live",
    ):
        assert client.get(path).status_code == 404
    check = verify(import_database, complete=True, database_name=import_target.expect_database)
    assert check["acceptance_passed"] == 1
    for dataset in APPROVED_DATASETS:
        result = invoke(import_database, import_target, source.parent, dataset)
        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["teams_inserted"] == report["competitions_inserted"] == 0
        assert report["matches_inserted"] == 0
        assert report["unchanged"] == load_manifest(dataset).expected_counts.matches
    assert snapshot(import_database) == after

    # A conflicting factual row must reject the edition without partial writes.
    with import_database.engine.begin() as connection:
        connection.execute(
            text("UPDATE matches SET home_score=home_score+1 WHERE match_id=:id"),
            {"id": final["match_id"]},
        )
    conflicting = snapshot(import_database)
    rejected = invoke(import_database, import_target, source.parent, "womens-world-cup-2023")
    assert rejected.exit_code != 0
    assert snapshot(import_database) == conflicting
    with import_database.engine.begin() as connection:
        connection.execute(
            text("UPDATE matches SET home_score=home_score-1 WHERE match_id=:id"),
            {"id": final["match_id"]},
        )
    assert snapshot(import_database) == after

    # Recreate the Flask application and connection pool against the same disposable schema.
    app.extensions["goalstats_cache"].close()
    import_database.dispose()
    restarted = app_factory(postgres_config).test_client()
    assert restarted.get("/ready").status_code == 200
    assert restarted.get("/swagger/v1/swagger.json").json == spec
    assert snapshot(import_database) == after
    assert restarted.get(f"/api/v1/scenarios/{created.json['scenario_id']}").json == created.json
    assert restarted.get(history_path).json == saved_predictions
    for prediction in saved_predictions:
        fetched = restarted.get(f"/api/v1/predictions/{prediction['prediction_id']}")
        assert fetched.status_code == 200 and fetched.json == prediction
    assert (
        verify(import_database, complete=True, preservation=check["preservation"])[
            "acceptance_passed"
        ]
        == 1
    )
    with import_database.engine.connect() as connection:
        inspector = inspect(connection)
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext

        from models.base import Base

        assert set(inspector.get_table_names()) == set(after)
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    print(
        "Pinned-source acceptance: 44 teams, 9 competitions, 348 matches, "
        "1081 goals; repeat inserts=0"
    )
    print(json.dumps(reports, sort_keys=True))
