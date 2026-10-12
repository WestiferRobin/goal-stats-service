"""All writes use the repository's ownership-verified disposable PostgreSQL fixture."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from models.action import Action
from models.base import Base
from models.catalog import Competition, Match, Team
from models.football import FootballSnapshot
from models.item import Item

pytestmark = pytest.mark.postgres
ROOT = Path(__file__).resolve().parents[3]
CATALOG = {"teams", "competitions", "matches"}
LEGACY = {"football_teams", "football_history", "football_snapshots", "items", "actions"}


@pytest.fixture
def isolated_schema(postgres_app):
    engine = postgres_app.extensions["goalstats_database"].engine
    with engine.connect() as connection:
        transaction = connection.begin()
        schema = "catalog_test_" + uuid4().hex
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["connection"] = connection
        try:
            yield connection, config
        finally:
            transaction.rollback()  # Also removes the test-only schema and its contents.


def signature(connection, table):
    inspector = inspect(connection)
    return {
        "columns": [
            (c["name"], str(c["type"]), c["nullable"], c.get("default"))
            for c in inspector.get_columns(table)
        ],
        "pk": inspector.get_pk_constraint(table),
        "fk": inspector.get_foreign_keys(table),
        "uq": inspector.get_unique_constraints(table),
        "checks": inspector.get_check_constraints(table),
        "indexes": inspector.get_indexes(table),
    }


def assert_catalog(connection):
    inspector = inspect(connection)
    for model, key in [(Team, "team_id"), (Competition, "competition_id"), (Match, "match_id")]:
        table = model.__tablename__
        assert inspector.get_pk_constraint(table)["constrained_columns"] == [key]
        assert next(c for c in inspector.get_columns(table) if c["name"] == key)["identity"]
        assert {c["name"] for c in inspector.get_check_constraints(table)} == {
            str(c.name)
            for c in model.__table__.constraints
            if c.__class__.__name__ == "CheckConstraint"
        }
    assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints("teams")} == {
        ("name_key", "category")
    }
    assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints("competitions")} == {
        ("name_key", "edition_label", "category")
    }
    assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints("matches")} == {
        ("source", "source_record_key")
    }
    foreign_keys = inspector.get_foreign_keys("matches")
    assert {tuple(fk["constrained_columns"]) for fk in foreign_keys} == {
        ("competition_id",),
        ("home_team_id",),
        ("away_team_id",),
    }
    assert all(fk["options"]["ondelete"] == "RESTRICT" for fk in foreign_keys)
    indexes = {tuple(i["column_names"]) for i in inspector.get_indexes("matches")}
    assert {("competition_id",), ("home_team_id",), ("away_team_id",), ("match_date",)} <= indexes
    context = MigrationContext.configure(
        connection, opts={"compare_type": True, "compare_server_default": True}
    )
    assert compare_metadata(context, Base.metadata) == []


def test_repeated_upgrade_preserves_schema_and_records(isolated_schema):
    connection, config = isolated_schema
    command.upgrade(config, "head")
    # Load the unchanged prototype seed into this test schema, never the development DB.
    run_sql(connection, "prototype/003_seed_football.sql")
    # Populate every legacy table so preservation is checked with real records.
    item_id = connection.execute(
        Item.__table__.insert().values(name="preserved fixture", status="active").returning(Item.id)
    ).scalar_one()
    connection.execute(
        Action.__table__.insert().values(
            item_id=item_id, action_type="create", name="preserved fixture"
        )
    )
    connection.execute(
        FootballSnapshot.__table__.insert().values(
            team1="Spain", team2="England", state={"minute": 65}, prediction={"fixture": True}
        )
    )
    before = {name: signature(connection, name) for name in LEGACY}
    records = {name: connection.execute(text(f'SELECT * FROM "{name}"')).all() for name in LEGACY}
    assert len(records["football_teams"]) == 32
    assert len(records["football_history"]) == 16
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    for name in LEGACY:
        assert signature(connection, name) == before[name]
        assert connection.execute(text(f'SELECT * FROM "{name}"')).all() == records[name]
    for name in CATALOG:
        assert connection.scalar(text(f'SELECT count(*) FROM "{name}"')) == 0
    assert_catalog(connection)


def run_sql(connection, filename):
    # Own the transaction here so SQL scripts cannot commit outside the isolated schema.
    sql = (ROOT / "sql" / filename).read_text().replace("BEGIN;", "").replace("COMMIT;", "")
    connection.exec_driver_sql(sql)


def test_standalone_sql_matches_alembic_and_metadata(isolated_schema):
    connection, _ = isolated_schema
    run_sql(connection, "001_fresh_database.sql")
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a7c93e25d104"
    assert_catalog(connection)


def test_initial_migration_round_trip(isolated_schema):
    connection, config = isolated_schema
    command.upgrade(config, "head")
    assert_catalog(connection)
    command.downgrade(config, "base")
    assert set(inspect(connection).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    assert_catalog(connection)


def test_removed_intermediate_revision_is_rejected(isolated_schema):
    from alembic.util.exc import CommandError

    connection, config = isolated_schema
    command.upgrade(config, "head")
    connection.execute(text("UPDATE alembic_version SET version_num='f6b82d14c903'"))
    before = {name: signature(connection, name) for name in Base.metadata.tables}
    with pytest.raises(CommandError, match="Can't locate revision"):
        command.upgrade(config, "head")
    assert {name: signature(connection, name) for name in Base.metadata.tables} == before


@pytest.fixture
def catalog_rows(isolated_schema):
    connection, config = isolated_schema
    command.upgrade(config, "head")
    home, away = [
        connection.execute(
            Team.__table__.insert()
            .values(name=name, name_key=name.lower(), category="women_senior_national")
            .returning(Team.team_id)
        ).scalar_one()
        for name in ("Spain", "England")
    ]
    competition = connection.execute(
        Competition.__table__.insert()
        .values(
            name="FIFA Women's World Cup",
            name_key="fifa women's world cup",
            edition_label="2023",
            category="women_senior_national",
        )
        .returning(Competition.competition_id)
    ).scalar_one()
    values = dict(
        competition_id=competition,
        home_team_id=home,
        away_team_id=away,
        match_date="2023-08-20",
        home_score=1,
        away_score=0,
        score_basis="including_extra_time_no_shootout",
        source="martj42_womens_results",
        source_record_key="a" * 64,
        source_version="test-fixture",
        source_file_sha256="b" * 64,
        source_row=2,
        source_url="https://example.org/test-fixture",
        source_home_team="Spain",
        source_away_team="England",
        source_tournament="FIFA World Cup",
    )
    return connection, values


@pytest.mark.parametrize("rating", ["offense", "defense", "form", "star_power", "clutch"])
@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf"), float("-inf")])
def test_invalid_ratings_rejected(catalog_rows, rating, value):
    connection, values = catalog_rows
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                Team.__table__.update()
                .where(Team.team_id == values["home_team_id"])
                .values(**{rating: value, "ratings_source": "fixture"})
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " \t\n"},
        {"category": ""},
        {"name_key": ""},
        {"fifa_rank": 0},
        {"offense": 50},
        {"offense": 50, "ratings_source": " \t"},
        {"fifa_rank": 1},
        {"ranking_date": "2023-08-20"},
    ],
)
def test_team_attribution_and_identity_checks(catalog_rows, changes):
    connection, values = catalog_rows
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                Team.__table__.update()
                .where(Team.team_id == values["home_team_id"])
                .values(**changes)
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"home_score": -1},
        {"away_score": -1},
        {"source_row": 0},
        {"source_record_key": "x" * 64},
        {"source_file_sha256": "a" * 63},
        *[
            {field: " \t"}
            for field in (
                "source",
                "source_version",
                "source_url",
                "score_basis",
                "source_home_team",
                "source_away_team",
                "source_tournament",
            )
        ],
        {"competition_id": -1},
        {"home_team_id": -1},
        {"away_team_id": -1},
        {"home_score": None},
    ],
)
def test_match_checks_and_foreign_keys(catalog_rows, changes):
    connection, values = catalog_rows
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(Match.__table__.insert().values(**{**values, **changes}))


def test_valid_rows_uniqueness_and_restrictive_deletion(catalog_rows):
    connection, values = catalog_rows
    match = connection.execute(
        Match.__table__.insert().values(**values).returning(Match.imported_at)
    ).scalar_one()
    assert match.tzinfo is not None
    row = (
        connection.execute(Team.__table__.select().where(Team.team_id == values["home_team_id"]))
        .mappings()
        .one()
    )
    assert row["offense"] is row["fifa_rank"] is None
    statements = [
        Match.__table__.insert().values(**values),
        Match.__table__.insert().values(
            **{**values, "source_record_key": "c" * 64, "away_team_id": values["home_team_id"]}
        ),
        Team.__table__.insert().values(
            name="SPAIN", name_key="spain", category="women_senior_national"
        ),
        Competition.__table__.insert().values(
            name="Other display",
            name_key="fifa women's world cup",
            edition_label="2023",
            category="women_senior_national",
        ),
        Team.__table__.delete().where(Team.team_id == values["home_team_id"]),
        Team.__table__.delete().where(Team.team_id == values["away_team_id"]),
        Competition.__table__.delete().where(
            Competition.competition_id == values["competition_id"]
        ),
    ]
    for statement in statements:
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(statement)
    connection.execute(
        Team.__table__.update().values(
            offense=0, defense=100, ratings_source="fixture", fifa_rank=1, ranking_source="fixture"
        )
    )
