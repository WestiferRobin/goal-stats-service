"""Synthetic evidence exercises interfaces only; none is exported as historical data."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from research.special_ratings import (
    RAPM_VERSION,
    SPEC,
    Forecast,
    Impact,
    Observation,
    Player,
    Reference,
    Roster,
    Source,
    clutch,
    digest,
    percentile,
    star_power,
)

D = date(2023, 7, 1)


def source(**changes):
    return Source(
        **dict(
            dict(
                url="https://example.org/synthetic",
                publisher="Test only",
                revision="fixture-v1",
                sha256="a" * 64,
                retrieved_on=D,
                rights_basis="Synthetic test fixture",
                published_on=D,
                publication_verified=True,
            ),
            **changes,
        )
    )


def bundle():
    impacts = tuple(
        Impact(
            player_id=f"{role}-{i}",
            team=f"team-{i % 6}",
            role=role,
            minutes=1000,
            value=float(i),
            lower=float(i) - 1,
            upper=float(i) + 1,
            source=source(),
        )
        for role in ["GK", "DF", "MF", "FW"]
        for i in range(30)
    )
    players = tuple(
        Player(player_id=p.player_id, team=p.team, role=p.role, available=True)
        for p in impacts
        if p.team == "team-0"
    )
    roster = Roster(
        team="team-0",
        announced_on=D,
        availability_checked_on=D,
        source=source(),
        availability_source=source(),
        players=players,
    )
    reference = Reference(
        metric_version=RAPM_VERSION,
        window_start=D - timedelta(days=730),
        through=D,
        trained_through=D,
        training_hash="b" * 64,
        source=source(),
        impacts=impacts,
    )
    return roster, reference


def altered(model, **changes):
    return type(model).model_validate(dict(model.model_dump(), **changes))


def observations():
    result = []
    for i in range(12):
        day = date(2019 if i < 3 else 2023, 6, i + 1)
        cutoff = day - timedelta(days=1)
        s = source(published_on=cutoff)
        key = digest(i)
        forecast = Forecast(
            match_key=key,
            team="A",
            cutoff=cutoff,
            trained_through=cutoff,
            training_hash="b" * 64,
            model_version="synthetic-baseline",
            feature_set="offense_defense_form_rank_only",
            horizon_minutes=90,
            win=0.4,
            draw=0.2,
            loss=0.4,
            source=s,
        )
        result.append(
            Observation(
                match_key=key,
                day=day,
                edition=day.year,
                team="A",
                opponent=f"B{i}",
                stage="quarterfinal" if i < 6 else "group",
                context_known_on=cutoff,
                context_source=s,
                regulation_minutes=90,
                goals_for=1 if i < 6 else 0,
                goals_against=0,
                source=s,
                forecast=forecast,
            )
        )
    return tuple(result)


def test_star_determinism_normalization_and_uncertainty():
    roster, reference = bundle()
    result = star_power("team-0", D, roster, reference)
    assert result == star_power("team-0", D, roster, reference)
    assert result["kind"] == "derived_model_estimate"
    assert result["value"] == 74.166667
    assert result["bounds"] == [67.5, 80.833333]
    assert 0 <= result["bounds"][0] <= result["value"] <= result["bounds"][1] <= 100
    assert result["production_eligible"] is False
    assert percentile(2, [1, 2, 2, 3]) == 50
    assert percentile(0, [1, 2]) == 0
    assert percentile(3, [1, 2]) == 100
    assert result["method_hash"] == digest(SPEC)


@pytest.mark.parametrize("change", ["missing", "publication", "stale", "squad", "minutes", "peers"])
def test_star_missing_never_default(change):
    r, ref = bundle()
    if change == "missing":
        ref = None
    if change == "publication":
        r = altered(r, source=source(publication_verified=False, published_on=None))
    if change == "stale":
        r = altered(r, availability_checked_on=D - timedelta(days=8))
    if change == "squad":
        r = altered(r, players=r.players[:5])
    if change == "minutes":
        ref = altered(ref, impacts=tuple(altered(p, minutes=1) for p in ref.impacts))
    if change == "peers":
        ref = altered(ref, impacts=tuple(p for p in ref.impacts if p.team == "team-0"))
    result = star_power("team-0", D, r, ref)
    assert result["value"] is None and result["bounds"] is None and result["reasons"]


@pytest.mark.parametrize("change", ["team", "future", "identity"])
def test_star_rejects_identity_and_future(change):
    r, ref = bundle()
    team = "wrong" if change == "team" else "team-0"
    if change == "future":
        r = altered(r, announced_on=D + timedelta(days=1))
    if change == "identity":
        ref = altered(ref, impacts=(altered(ref.impacts[0], team="wrong"),) + ref.impacts[1:])
    with pytest.raises(ValueError):
        star_power(team, D, r, ref)


def test_clutch_known_contrast_and_uncertainty():
    rows = observations()
    result = clutch("A", D, rows)
    # Pressure residual .5, group residual 0; n_eff=3; shrink=.2.
    assert result["value"] == 55
    assert result["bounds"] == [55, 55]
    assert result == clutch("A", D, tuple(reversed(rows)))
    varied = rows[:-1] + (altered(rows[-1], goals_against=1),)
    result = clutch("A", D, varied)
    assert result["bounds"][0] < result["value"] < result["bounds"][1]


def test_clutch_cutoff_and_missing():
    rows = observations()
    future = altered(
        rows[-1],
        day=D + timedelta(days=1),
        match_key=digest("future"),
        opponent="future",
        forecast=None,
    )
    assert clutch("A", D, rows) == clutch("A", D, rows + (future,))
    assert clutch("A", D, ())["value"] is None
    for changed in [
        rows[:5],
        tuple(altered(o, forecast=None) for o in rows),
        tuple(altered(o, context_known_on=None, context_source=None) for o in rows),
    ]:
        assert clutch("A", D, changed)["value"] is None
    assert clutch("A", D + timedelta(days=1462), rows)["value"] is None


def test_clutch_duplicate_and_baseline_mismatch():
    rows = observations()
    for extra in [rows[0], altered(rows[0], match_key=digest("other"), forecast=None)]:
        with pytest.raises(ValueError, match="Duplicate"):
            clutch("A", D, rows + (extra,))
    changed = altered(rows[-1], forecast=altered(rows[-1].forecast, model_version="different"))
    with pytest.raises(ValueError, match="baseline"):
        clutch("A", D, rows[:-1] + (changed,))


@pytest.mark.parametrize(
    "kind",
    [
        "publication",
        "retrieval",
        "roster_duplicate",
        "roster_team",
        "interval",
        "window",
        "training",
        "reference_duplicate",
        "probability",
        "forecast_training",
        "observation_team",
        "context_future",
        "forecast_identity",
        "forecast_future",
        "extra",
        "nan",
        "wrong_horizon",
        "edition",
    ],
)
def test_invalid_contracts(kind):
    r, ref = bundle()
    o = observations()[0]
    f = o.forecast
    with pytest.raises((ValueError, ValidationError)):
        if kind == "publication":
            source(published_on=None)
        if kind == "retrieval":
            source(published_on=D + timedelta(days=1))
        if kind == "roster_duplicate":
            altered(r, players=r.players + (r.players[0],))
        if kind == "roster_team":
            altered(r, team="wrong")
        if kind == "interval":
            altered(ref.impacts[0], lower=10.0)
        if kind == "window":
            altered(ref, window_start=D)
        if kind == "training":
            altered(ref, trained_through=D + timedelta(days=1))
        if kind == "reference_duplicate":
            altered(ref, impacts=ref.impacts + (ref.impacts[0],))
        if kind == "probability":
            altered(f, win=0.9)
        if kind == "forecast_training":
            altered(f, trained_through=D)
        if kind == "observation_team":
            altered(o, opponent="A")
        if kind == "context_future":
            altered(o, context_known_on=o.day)
        if kind == "forecast_identity":
            altered(o, forecast=altered(f, team="wrong"))
        if kind == "forecast_future":
            altered(o, forecast=altered(f, cutoff=o.day))
        if kind == "extra":
            altered(f, placeholder=50)
        if kind == "nan":
            altered(ref.impacts[0], value=float("nan"))
        if kind == "edition":
            altered(o, edition=1995)
        if kind == "wrong_horizon":
            altered(o, regulation_minutes=80)
