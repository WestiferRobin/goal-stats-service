from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from football.enrichment import import_package
from infra.repositories.team import TeamRepository
from models.enrichment import RankingObservation, RankingRelease, TeamRating
from models.team import Team
from services.team import TeamService


@pytest.fixture
def package(import_database):
    with import_database.transaction() as session:
        session.add(
            Team(
                team_id=1,
                name="United States",
                name_key="united states",
                category="women_senior_national",
            )
        )
    metadata = {
        "id": "release",
        "date": "2026-10-20",
        "sha256": "a" * 64,
        "url": "https://api.fifa.com/example",
    }
    row = {
        "IdTeam": "1882884",
        "TeamName": [{"Locale": "en-GB", "Description": "USA"}],
        "Rank": 2,
        "TotalPoints": 2042.379,
        "RankingStatus": 0,
    }
    manifest = {"retrieved_at": "2026-11-15T00:00:00+00:00", "index_sha256": "b" * 64}
    ratings = {
        "United States": {
            "offense": 0.0,
            "defense": 80.0,
            "form": 60.0,
            "evidence": {"matches": 20},
        }
    }
    return manifest, [(metadata, [row])], ratings, {"status": "experimental"}, date(2026, 6, 10)


@pytest.mark.postgres
def test_read_only_dry_run_replay_and_api_projection(import_database, package):
    with import_database.transaction() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        result = import_package(session, *package, apply=False)
        assert result["observations_inserted"] == 1
        assert session.scalar(select(func.count()).select_from(RankingRelease)) == 0
    with import_database.transaction() as session:
        result = import_package(session, *package, apply=True)
    with import_database.transaction() as session:
        replay = import_package(session, *package, apply=True)
        assert replay["observations_inserted"] == replay["ratings_inserted"] == 0
        assert replay["run_id"] == result["run_id"]
        assert session.scalar(select(RankingObservation.points)) == Decimal("2042.379")
        assert session.get(Team, 1).offense is None
    profile = TeamService(repo=TeamRepository(import_database)).get(1)
    assert profile["offense"] == 0
    assert profile["fifa_rank"] == 2 and profile["fifa_points"] == 2042.379
    assert profile["ranking_date"] == "2026-10-20"
    assert profile["ratings_metadata"]["cutoff"] == "2026-06-10"
    assert profile["star_power"] is profile["clutch"] is None
    assert profile["prediction_ready"] is False


@pytest.mark.postgres
def test_conflicting_release_rolls_back(import_database, package):
    with import_database.transaction() as session:
        import_package(session, *package, apply=True)
    package[1][0][0]["sha256"] = "c" * 64
    with pytest.raises(ValueError, match="conflicts"), import_database.transaction() as session:
        import_package(session, *package, apply=True)
    with import_database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(TeamRating)) == 1
        assert session.scalar(select(RankingRelease.sha256)) == "a" * 64


@pytest.mark.postgres
def test_unranked_does_not_carry_forward_old_rank(import_database, package):
    with import_database.transaction() as session:
        import_package(session, *package, apply=True)
    metadata = {**package[1][0][0], "id": "next", "date": "2026-11-01", "sha256": "d" * 64}
    row = {**package[1][0][1][0], "Rank": 0, "TotalPoints": None, "RankingStatus": 1}
    with import_database.transaction() as session:
        import_package(session, package[0], [(metadata, [row])], *package[2:], apply=True)
    profile = TeamService(repo=TeamRepository(import_database)).get(1)
    assert profile["fifa_rank"] is profile["fifa_points"] is None
    assert profile["ranking_date"] == "2026-11-01"
    assert profile["ranking_status"] == "unranked"


@pytest.mark.postgres
def test_populated_enrichment_downgrade_refuses_data_loss(import_database, package):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.exc import DBAPIError

    with import_database.transaction() as session:
        import_package(session, *package, apply=True)
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    with pytest.raises(DBAPIError, match="downgrade refused"):
        with import_database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "e42b7c19a603")
    with import_database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(TeamRating)) == 1
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "f31a6e208b47"
