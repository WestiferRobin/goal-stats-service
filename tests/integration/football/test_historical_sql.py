"""Read-only acceptance SQL; corrupt fixtures exist only in owned disposable schemas."""

import json
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import text

from football.datasets import import_datasets
from football.historical_dataset import (
    APPROVED_DATASETS,
    load_manifest,
    name_key,
    source_record_key,
)
from models.competition import Competition
from models.match import Match
from models.team import Team

pytestmark = pytest.mark.postgres
SQL = (Path(__file__).resolve().parents[3] / "sql/verify_historical_import.sql").read_text()
SQL = "\n".join(line for line in SQL.splitlines() if not line.startswith("\\"))


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


@pytest.mark.parametrize("complete", [False, True])
def test_complete_fixture_passes_both_modes_and_preserves_every_row(import_database, complete):
    populate(import_database, APPROVED_DATASETS)
    first = verify(import_database, complete=complete)
    assert first["acceptance_passed"] == 1 and first["transaction_read_only"] == "on"
    assert sum(e["matches"] for e in first["coverage"]) == 348
    assert first["preservation"]["teams"]["rows"] == 44
    second = verify(import_database, complete=complete, preservation=first["preservation"])
    assert second == first


def test_current_2023_passes_but_complete_rejects_missing_editions(import_database):
    populate(import_database, ["womens-world-cup-2023"])
    assert verify(import_database)["acceptance_passed"] == 1
    with pytest.raises(psycopg.Error, match="Historical verification failed"):
        verify(import_database, complete=True)


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


def test_preservation_and_unrelated_records(scenario_client, scenario_body, import_database):
    response = scenario_client.post("/api/v1/scenarios", json=scenario_body)
    assert response.status_code == 201
    scenario = response.json["scenario_id"]
    assert scenario_client.post(f"/api/v1/scenarios/{scenario}/predictions").status_code == 201
    with import_database.transaction() as session:
        import_datasets(session)
    first = verify(import_database)
    assert first["preservation"]["scenarios"]["rows"] == 1
    assert first["preservation"]["predictions"]["rows"] == 1
    assert first["preservation"]["football_teams"]["rows"] == 32
    assert verify(import_database, preservation=first["preservation"]) == first
    with import_database.transaction() as session:
        session.execute(text("UPDATE scenarios SET title = 'changed'"))
    with pytest.raises(psycopg.Error, match="record preservation"):
        verify(import_database, preservation=first["preservation"])


def test_identity_and_read_only_enforcement(import_database):
    with pytest.raises(psycopg.Error, match="database identity"):
        verify(import_database, database_name="not-this-database")
    attempted_write = SQL.replace(
        "WITH expected AS", "DELETE FROM football_teams;\nWITH expected AS", 1
    )
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        verify(import_database, sql=attempted_write)
