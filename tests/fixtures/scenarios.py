"""Explicit synthetic model inputs shared by integration and HTTP tests."""

import pytest


@pytest.fixture
def scenario_body():
    body = {
        "title": "Synthetic scenario fixture",
        "team1_id": 1,
        "team2_id": 2,
        "match_id": None,
        "match_minute": 65,
    }
    for side in (1, 2):
        for field in (
            "goals",
            "shots",
            "shots_on_target",
            "big_chances",
            "defender_blocks",
            "goalkeeper_saves",
            "corners",
            "yellow_cards",
            "red_cards",
        ):
            body[f"team{side}_{field}"] = 0
        body[f"team{side}_possession"] = 50
        for field in ("offense", "defense", "form", "star_power", "clutch"):
            body[f"team{side}_{field}"] = 70
    return body
