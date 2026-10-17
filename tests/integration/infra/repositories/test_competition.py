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
