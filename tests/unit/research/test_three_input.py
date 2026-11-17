"""Synthetic mathematical/temporal tests; no synthetic historical performance evidence."""

import copy
import math
from datetime import date

import pytest

from research.model_validation import baseline, comparison, evaluate
from research.three_input import (
    FREQUENCY,
    POISSON,
    A,
    B,
    C,
    Ratings,
    calibrate,
    period,
    poisson,
    predict,
)


@pytest.mark.parametrize("model", [A, B, C])
@pytest.mark.parametrize(
    "values", [(0, 0, 0), (100, 100, 100), (100, 0, 100), (0, 100, 0), (50, 50, 50)]
)
def test_extremes_orientation_determinism(model, values):
    h = Ratings(*values)
    a = Ratings(35, 65, 20)
    p = predict(h, a, model)
    q = predict(a, h, model)
    assert all(math.isfinite(x) and 0 <= x <= 1 for x in p)
    assert sum(p) == pytest.approx(1, abs=1e-12)
    assert p == predict(h, a, model)
    assert p == pytest.approx((q[2], q[1], q[0]), abs=1e-12)
    balanced = predict(h, h, model)
    assert balanced[0] == balanced[2] and balanced[1] > 0


def test_cross_goal_math_and_sensitivity():
    h = Ratings(80, 70, 60)
    a = Ratings(40, 50, 20)
    expected = poisson(1.3 * 2**0.3 * 1.5**0.4, 1.3 * 2 ** (-0.3) * 1.5 ** (-0.4))
    assert predict(h, a) == pytest.approx(expected)
    center = Ratings(50, 50, 50)
    p = predict(center, center)
    assert predict(Ratings(60, 50, 50), center)[0] > p[0]
    assert predict(center, Ratings(50, 60, 50))[0] < p[0]
    assert predict(Ratings(50, 50, 60), center)[0] > p[0]
    assert predict(center, Ratings(60, 50, 50))[0] < p[0]
    assert predict(h, a, A) != predict(h, a, B)
    assert predict(h, a, C, temperature=1) == predict(h, a, B)
    for t in [0.75, 1.25]:
        assert max(range(3), key=lambda i: predict(h, a, C, temperature=t)[i]) == max(
            range(3), key=lambda i: predict(h, a)[i]
        )


def test_poisson_known_values_and_exact_symmetry():
    assert poisson(0, 0) == (0, 1, 0)
    p = poisson(1, 0)
    assert p == pytest.approx((1 - math.exp(-1), math.exp(-1), 0))
    for rate in [0.1, 1.3, 3.9, 20]:
        p = poisson(rate, rate)
        assert p[0] == p[2] and sum(p) == pytest.approx(1)
    for bad in [-1, float("nan"), float("inf"), 21, True]:
        with pytest.raises(ValueError):
            poisson(bad, 1)


@pytest.mark.parametrize("bad", [None, True, float("nan"), float("inf"), -1, 101, "50"])
def test_invalid_ratings(bad):
    with pytest.raises(ValueError):
        Ratings(bad, 50, 50)


def test_version_and_horizon_isolation():
    r = Ratings(50, 50, 50)
    for kwargs in [
        dict(model="road-to-the-final-heuristic-v2"),
        dict(minutes=80),
        dict(minutes=90.0),
        dict(temperature=0.75),
        dict(model=C, temperature=0),
        dict(model=C, temperature=True),
    ]:
        with pytest.raises(ValueError):
            predict(r, r, **kwargs)
    with pytest.raises(ValueError):
        predict(None, r)
    with pytest.raises(ValueError):
        period(2000)
    assert period(1991) == "excluded_horizon"


def calibration_cases():
    return [
        dict(
            match_key=str(i),
            edition=2007,
            date="2007-09-30",
            truth=i % 3,
            predictions={B: [0.5, 0.2, 0.3]},
        )
        for i in range(21)
    ]


def test_calibration_separation_and_replay():
    rows = calibration_cases()
    result = calibrate(rows, date(2011, 1, 1))
    assert result == calibrate(copy.deepcopy(rows), date(2023, 1, 1))
    assert result["through"] == "2007-09-30" and result["calibration_cases"] == 21
    invalid = [
        [],
        rows[:19],
        rows + [rows[0]],
        rows + [dict(rows[0], edition=2019)],
        rows + [dict(rows[0], truth=4)],
    ]
    for data in invalid:
        with pytest.raises(ValueError):
            calibrate(data, date(2011, 1, 1))
    with pytest.raises(ValueError):
        calibrate(rows, date(2007, 9, 30))


def historical_rows():
    return [
        dict(
            match_key=str(i),
            edition=1995,
            date="1995-06-01",
            regulation_minutes=90,
            regulation_score=[i % 3, 1],
        )
        for i in range(21)
    ]


def test_training_only_baselines():
    rows = historical_rows()
    assert baseline(rows, 1995) is None
    assert baseline(rows[:19], 1999) is None
    result = baseline(rows, 1999)
    assert result["training_cases"] == 21
    assert result["predictions"][FREQUENCY] == pytest.approx([1 / 3] * 3)
    assert result["predictions"][POISSON] == list(poisson(1, 1))
    future = dict(
        rows[0], match_key="future", edition=2023, date="2023-07-01", regulation_score=[50, 0]
    )
    assert baseline(rows + [future], 2011) == baseline(rows, 2011) == baseline(rows, 2023)
    past80 = dict(rows[0], match_key="80", edition=1991, date="1991-11-01", regulation_minutes=80)
    assert baseline(rows + [past80], 2011) == baseline(rows, 2011)
    with pytest.raises(ValueError):
        baseline(rows + [rows[0]], 1999)
    with pytest.raises(ValueError):
        baseline([dict(r, date="2023-07-01") for r in rows], 1999)


def test_same_cohort_metrics_uncertainty_and_duplicates():
    rows = [
        dict(
            match_id=i,
            match_key=str(i),
            edition=2011 if i < 3 else 2015,
            truth=i % 3,
            predictions={B: [0.6, 0.2, 0.2], A: [0.6, 0.2, 0.2]},
        )
        for i in range(6)
    ]
    rows.append(
        dict(match_id=6, match_key="6", edition=2015, truth=1, predictions={B: [0.1, 0.8, 0.1]})
    )
    report = comparison(rows, [A, B])
    assert report["sample_size"] == 6 and report["excluded_from_supplied_group"] == 1
    assert report["models"][B]["accuracy"] == pytest.approx(1 / 3)
    assert report["paired_differences"][A]["log_loss"] == {"mean": 0, "interval_95": [0, 0]}
    assert report == comparison(rows, [A, B])
    assert comparison(rows[:3], [A, B])["uncertainty_method"] == "within_edition_matches"
    assert comparison([], [A, B])["sample_size"] == 0
    for models in [[A], [B, B]]:
        with pytest.raises(ValueError):
            comparison(rows, models)
    with pytest.raises(ValueError):
        comparison(rows + rows, [A, B])
    with pytest.raises(ValueError):
        evaluate({"cases": []})
