import pytest
from pydantic import ValidationError

from schemas.competition import CatalogCompetitionResponse, CatalogCompetitionsResponse


def test_competition_list_and_required_fields():
    row = dict(competition_id=1, name="Cup", edition_label="2023", category="women")
    assert CatalogCompetitionsResponse([CatalogCompetitionResponse(**row)]).model_dump() == [row]
    with pytest.raises(ValidationError):
        CatalogCompetitionResponse(**row, unexpected=True)
    del row["edition_label"]
    with pytest.raises(ValidationError):
        CatalogCompetitionResponse(**row)
