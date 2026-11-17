import pytest
from sqlalchemy import text

from infra.repositories.competition import CompetitionRepository


@pytest.mark.postgres
def test_competition_reads_order_and_missing_identity(database):
    with database.transaction() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        repo = CompetitionRepository(database)
        assert [r.competition_id for r in repo.list(session)] == [10, 20, 30]
        assert repo.get_by_id(session, 10).edition_label == "2019"
        assert repo.get_by_id(session, 999) is None


@pytest.mark.postgres
@pytest.mark.parametrize(
    "column,value,sqlstate",
    [
        ("edition_label", "2023", "23505"),
        ("name", "  ", "23514"),
        ("name_key", "", "23514"),
        ("category", "", "23514"),
    ],
)
def test_competition_constraints_reject_invalid_write_without_changes(
    database, column, value, sqlstate
):
    from sqlalchemy.exc import IntegrityError

    from tests.fixtures.historical_database import snapshot

    before = snapshot(database)
    with pytest.raises(IntegrityError) as error:
        with database.transaction() as session:
            session.execute(
                text(f"UPDATE competitions SET {column}=:value WHERE competition_id=10"),
                {"value": value},
            )
    assert error.value.orig.sqlstate == sqlstate
    assert snapshot(database) == before
