"""Team request contracts; existing validation and serialization preserved."""

from schemas.common import CatalogID, Contract


class CatalogTeamPath(Contract):
    team_id: CatalogID
