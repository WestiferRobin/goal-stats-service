"""Source/temporal invariants. Synthetic matches test mathematics, not history."""

import json
import math
from copy import deepcopy
from datetime import date, timedelta

import pytest

from football.enrichment import observations, release_index
from football.team_ratings import Result, calculate, fit, percentile, read_results, validate_model


def test_validation_report_platform_roundoff_only():
    from football.enrichment import same_validation_report

    expected = {
        "folds": [
            {
                "matches": 120,
                "baseline_nll": 3.5,
                "opponent_adjusted_nll": 3.2,
                "with_form_nll": 3.3,
            }
        ]
    }
    actual = deepcopy(expected)
    actual["folds"][0]["baseline_nll"] = math.nextafter(3.5, math.inf, steps=2)
    original = deepcopy(actual)
    assert same_validation_report(actual, expected)
    assert actual == original
    for value in (3.500001, math.nextafter(3.5, math.inf, steps=5), float("nan"), float("inf"), 3):
        actual = deepcopy(expected)
        actual["folds"][0]["baseline_nll"] = value
        assert not same_validation_report(actual, expected)
    for actual in ({}, {"folds": []}, {"folds": [None]}, {"folds": [{}]}):
        assert not same_validation_report(actual, expected)
    actual = deepcopy(expected)
    actual["folds"][0]["matches"] = 121
    assert not same_validation_report(actual, expected)


def observation(**changes):
    return {
        "IdTeam": "123",
        "Gender": 2,
        "TeamName": [{"Locale": "en-GB", "Description": "Example"}],
        "Rank": 1,
        "TotalPoints": 2000.125,
        "RankingStatus": 0,
        **changes,
    }


def raw_rows(rows, **changes):
    return json.dumps({"Results": rows, "ContinuationToken": None, **changes}).encode()


def test_release_date_comes_from_metadata_not_identifier():
    data = {
        "props": {
            "pageProps": {
                "pageData": {
                    "ranking": {
                        "allAvailableDates": [
                            {"id": "FRS_Female_Football_20260615", "date": "2026-10-20"}
                        ]
                    }
                }
            }
        }
    }
    raw = (
        '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + "</script>"
    ).encode()
    assert release_index(raw)[0]["date"] == "2026-10-20"


@pytest.mark.parametrize(
    "rows",
    [
        [observation(Gender=1)],
        [observation(), observation()],
        [observation(TotalPoints=float("nan"))],
        [observation(Rank=-1)],
        [observation(TotalPoints=None)],
        [],
    ],
)
def test_bad_observations_rejected(rows):
    with pytest.raises(ValueError):
        observations(raw_rows(rows))


def test_zero_points_and_unranked_observations_are_preserved():
    assert observations(raw_rows([observation(TotalPoints=0)]))[0]["TotalPoints"] == 0
    assert (
        observations(raw_rows([observation(Rank=0, TotalPoints=None, RankingStatus=1)]))[0]["Rank"]
        == 0
    )
    with pytest.raises(ValueError, match="pagination"):
        observations(raw_rows([observation()], ContinuationToken="next"))


def test_source_checksum_required():
    with pytest.raises(ValueError, match="checksum"):
        read_results(b"not approved")


@pytest.fixture(scope="module")
def mathematical_matches():
    start = date(2020, 1, 1)
    return [
        Result(
            start + timedelta(days=i * 7),
            "A" if i % 2 else "B",
            "B" if i % 2 else "A",
            2 if i % 2 else 0,
            0 if i % 2 else 2,
            True,
        )
        for i in range(300)
    ]


def test_cutoff_future_exclusion_and_determinism(mathematical_matches):
    cutoff = date(2024, 1, 1)
    rows = [r for r in mathematical_matches if r.day <= cutoff]
    first = calculate(rows, cutoff)
    assert first == calculate(mathematical_matches, cutoff) == calculate(rows, cutoff)
    assert first["A"]["offense"] > first["B"]["offense"]
    assert first["A"]["defense"] > first["B"]["defense"]
    assert all(0 <= r[k] <= 100 for r in first.values() for k in ("offense", "defense", "form"))


def test_sparse_team_is_not_filled_with_a_rating(mathematical_matches):
    cutoff = date(2024, 1, 1)
    result = calculate(mathematical_matches + [Result(cutoff, "New", "A", 0, 0, True)], cutoff)
    assert result["New"]["offense"] is None
    assert result["New"]["form"] is None


def test_heldout_boundary_and_percentile_ties(mathematical_matches):
    result = validate_model(mathematical_matches, date(2024, 1, 1))
    assert all(r["train_through"] < r["test_through"] and r["matches"] > 0 for r in result["folds"])
    assert percentile(1, [1, 1]) == 50
    with pytest.raises(ValueError):
        fit([], date(2024, 1, 1))


def test_balanced_poisson_fit_has_known_solution():
    cutoff = date(2024, 1, 1)
    rows = [Result(cutoff - timedelta(days=i), "A", "B", 1, 1, True) for i in range(40)]
    model = fit(rows, cutoff)
    assert model.means(rows[0]) == pytest.approx((1.0, 1.0), abs=1e-10)
    assert model.attack == {"A": 0.0, "B": 0.0}


def test_missing_team_keeps_established_fifa_identity():
    from football.enrichment import mapped_teams
    from models.enrichment import FifaTeamMapping
    from models.team import Team

    team = Team(team_id=1, name="United States")
    known = {1: FifaTeamMapping(team_id=1, fifa_team_id="1882884", source_name="USA")}
    assert mapped_teams([team], [], known) == {1: ("1882884", "USA")}
    with pytest.raises(ValueError, match="Unresolved"):
        mapped_teams([team], [])
