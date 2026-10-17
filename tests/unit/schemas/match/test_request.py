from datetime import date

import pytest
from pydantic import ValidationError

from schemas.match import CatalogMatchQuery


def test_match_dates_and_pagination_defaults():
    query = CatalogMatchQuery(date_from="2023-07-20", date_to="2023-07-20")
    assert query.date_from == date(2023, 7, 20)
    assert query.model_dump(mode="json")["date_to"] == "2023-07-20"
    assert (query.limit, query.offset) == (50, 0)


@pytest.mark.parametrize(
    "values",
    [
        {"date_from": "2023-7-20"},
        {"date_from": "2023-02-30"},
        {"date_from": "2023-07-21", "date_to": "2023-07-20"},
        {"limit": 201},
        {"offset": -1},
        {"offset": 9223372036854775808},
        {"team_id": 0},
        {"unexpected": 1},
    ],
)
def test_match_query_rejections(values):
    with pytest.raises(ValidationError):
        CatalogMatchQuery(**values)
