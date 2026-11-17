import random

import pytest

from football.engine import Match, Team, simulate_tournament
from tests.fixtures.calculations import REFERENCE_TEAMS


def test_tournament_stages_count_each_team_once():
    teams = REFERENCE_TEAMS
    results, _, _, _ = simulate_tournament([Team(**team) for team in teams[:4]], 1000)
    assert all(row["semifinal_probability"] == 100 for row in results)
    assert sum(row["final_probability"] for row in results) == pytest.approx(200, abs=0.03)
    assert sum(row["champion_probability"] for row in results) == pytest.approx(100, abs=0.03)


def test_prediction_matches_original_road_to_the_final_reference():
    # Independently evaluated from source app.py at 8f17bc42e30f436f5cd860f2791695421160ccd2.
    teams = REFERENCE_TEAMS
    match = Match(Team(**teams[0]), Team(**teams[1]))
    assert match.calculate_probabilities()[:3] == pytest.approx(
        (0.37074041064032975, 0.26390886112362144, 0.36535072823604886)
    )
    match.match_minute = 65
    match.team1.goals = 1
    match.team1.shots_on_target = 4
    match.team1.possession = 60
    match.team2.possession = 40
    assert match.calculate_probabilities()[:3] == pytest.approx(
        (0.8136391843803665, 0.15959690743009677, 0.026763908189536657)
    )


@pytest.fixture
def balanced_match():
    return Match(Team("Alpha", 70, 70, 70, 70, 70), Team("Beta", 70, 70, 70, 70, 70))


@pytest.mark.parametrize("possession,expected", [(44, -3), (45, 0), (55, 0), (56, 3)])
def test_possession_boundaries_and_standalone_live_score(balanced_match, possession, expected):
    """The possession band is inclusive; the optional-opponent score adds no attack pressure."""
    team = balanced_match.team1
    team.possession = possession
    assert team.possession_score() == expected
    assert team.live_score() == 70 + expected
    assert team.event_score_breakdown() == (0, 0, False)


@pytest.mark.parametrize(
    "minute,clamped,ratio", [(-10, 0, 1), (45, 45, 0.5), (90, 90, 0.03), (200, 120, 0.03)]
)
def test_remaining_time_clamps_regulation_and_extra_time(balanced_match, minute, clamped, ratio):
    """Clamp negative minutes and retain the residual floor in finished/extra-time matches."""
    match = Match(balanced_match.team1, balanced_match.team2, minute)
    assert match.match_minute == clamped
    assert match.remaining_time_ratio() == ratio


@pytest.mark.parametrize(
    "probabilities,expected",
    [
        ((0.34, 0.33, 0.33), (5, "Extremely Even Match")),
        ((0.38, 0.32, 0.30), (4, "Very Competitive Match")),
        ((0.42, 0.30, 0.28), (3, "Competitive Match")),
        ((0.50, 0.30, 0.20), (2, "Clear Favorite")),
        ((0.70, 0.20, 0.10), (1, "Heavy Favorite")),
    ],
)
def test_difficulty_uses_leading_probability_margin(balanced_match, probabilities, expected):
    """Difficulty labels follow the difference between the two leading outcomes."""
    assert balanced_match.match_difficulty(probabilities) == expected


@pytest.mark.parametrize(
    "probabilities,expected",
    [
        ((0.6, 0.3, 0.1), (37.5, "Low", "confidence-low")),
        ((0.7, 0.2, 0.1), (62.5, "Medium", "confidence-medium")),
        ((1, 0, 0), (100, "High", "confidence-high")),
    ],
)
def test_confidence_labels_and_ceiling(balanced_match, probabilities, expected):
    """Confidence remains bounded and exposes the corresponding presentation label."""
    score, label, css = balanced_match.prediction_confidence(probabilities)
    assert score == pytest.approx(expected[0])
    assert (label, css) == expected[1:]


@pytest.mark.parametrize(
    "probabilities,expected",
    [
        ((0.4, 0.4, 0.2), ("Alpha Win", 0.4)),
        ((0.1, 0.7, 0.2), ("Draw", 0.7)),
        ((0.1, 0.2, 0.7), ("Beta Win", 0.7)),
    ],
)
def test_outcome_selection_and_stable_ties(balanced_match, probabilities, expected):
    """Select the leading outcome and preserve stable ordering for an exact tie."""
    assert balanced_match.predicted_outcome(probabilities) == expected


@pytest.mark.parametrize(
    "probabilities,expected", [((0.2, 0.6, 0.2), (0.5, 0.5)), ((0, 0, 0), (0, 0))]
)
def test_advancement_without_clutch_or_probability_mass(balanced_match, probabilities, expected):
    """Equal zero clutch splits a draw; zero probability mass is not divided by zero."""
    balanced_match.team1.clutch = balanced_match.team2.clutch = 0
    assert balanced_match.advancement_probabilities(probabilities) == pytest.approx(expected)


@pytest.mark.parametrize("side", [1, 2])
def test_reasoning_attributes_live_events_to_each_side(balanced_match, side):
    """Reasons name the team with each advantage and distinguish red-card harm and modifier caps."""
    team = getattr(balanced_match, f"team{side}")
    team.goals = 2
    team.red_cards = 1
    team.shots_on_target = 6
    team.big_chances = 10
    team.goalkeeper_saves = 1
    team.add_modifier("Support", 50)
    balanced_match.match_minute = 65
    reasons = balanced_match.reasoning_summary()
    for message in [
        "currently has more goals.",
        "has more red cards, which hurts its chances.",
        "has more shots on target.",
        "has created more big chances.",
        "has the higher attack pressure score.",
        "currently has more live momentum.",
        "has more calculated dangerous attacks.",
    ]:
        assert f"{team.name} {message}" in reasons
    assert f"{team.name}'s goalkeeper has made more saves." in reasons
    assert f"{team.name}: Support." in reasons
    assert f"{team.name}: stacked modifiers totaled +50.0, but were capped at +20.0." in reasons
    assert "The model is calculating remaining goals from minute 65." in reasons


@pytest.mark.parametrize(
    "scores,draw,expected",
    [((2, 0), 0.5, 1), ((0, 2), 0.5, 2), ((1, 1), 0.0, 1), ((1, 1), 0.99, 2)],
)
def test_knockout_score_winners_and_tiebreaks(monkeypatch, balanced_match, scores, draw, expected):
    """Controlled goal sampling exercises regulation wins and both weighted tiebreak outcomes."""
    from football import engine

    values = iter(scores)
    monkeypatch.setattr(engine, "_sample_poisson", lambda _, rng: next(values))
    monkeypatch.setattr(engine.random, "random", lambda: draw)
    winner = engine._simulate_knockout_match(
        balanced_match.team1, balanced_match.team2, engine.random
    )
    assert winner is getattr(balanced_match, f"team{expected}")
    assert balanced_match.team1.goals == balanced_match.team2.goals == 0


@pytest.mark.parametrize(
    "outcomes,clutch,expected_wins",
    [
        ((60, 30, 10), (70, 70), 75),
        ((10, 80, 10), (80, 20), 74),
        ((25, 50, 25), (70, 70), 50),
        ((60, 30, 10), (0, 0), 75),
        ((70, 0, 30), (70, 70), 70),
        ((60, 30, 10), (0, 70), 60),
        ((60, 30, 10), (70, 0), 90),
    ],
)
def test_knockout_draws_use_conditional_probability(
    monkeypatch, balanced_match, outcomes, clutch, expected_wins
):
    """An exact 100-match schedule must yield p(win) + p(draw) * p(advance | draw)."""
    from football import engine

    first, draws, second = outcomes
    balanced_match.team1.clutch, balanced_match.team2.clutch = clutch
    probabilities = tuple(count / 100 for count in outcomes)
    # Predictions must retain the overall advancement probabilities, not conditional shares.
    assert balanced_match.advancement_probabilities(probabilities) == pytest.approx(
        (expected_wins / 100, 1 - expected_wins / 100)
    )
    scores = iter([1, 0] * first + [0, 0] * draws + [0, 1] * second)
    # Midpoints evenly cover [0, 1), making the expected draw split exact and repeatable.
    tiebreaks = iter((index + 0.5) / draws for index in range(draws))
    monkeypatch.setattr(engine, "_sample_poisson", lambda _, rng: next(scores))
    monkeypatch.setattr(engine.random, "random", lambda: next(tiebreaks))
    monkeypatch.setattr(Match, "calculate_probabilities", lambda self: (*probabilities, (0, 0), []))
    winners = [
        engine._simulate_knockout_match(balanced_match.team1, balanced_match.team2, engine.random)
        for _ in range(100)
    ]
    assert winners.count(balanced_match.team1) == expected_wins
    assert winners.count(balanced_match.team2) == 100 - expected_wins
    assert next(scores, None) is None
    assert next(tiebreaks, None) is None


@pytest.mark.parametrize("size", [4, 8, 16, 32])
def test_seeded_tournament_advancement_invariants(monkeypatch, size):
    """Real Poisson sampling preserves stage totals and nested advancement across rounds."""

    teams = [Team(str(index), 70, 70, 70, 70, 70) for index in range(size)]
    results, champion, count, final = simulate_tournament(teams, 1000, seed=2026)
    assert count == 1000
    assert {row["team"] for row in results} == {team.name for team in teams}
    assert champion == results[0]["team"]
    for row in results:
        assert (
            0
            <= row["champion_probability"]
            <= row["final_probability"]
            <= row["semifinal_probability"]
            <= 100
        )
    for field, total in (
        ("semifinal_probability", 400),
        ("final_probability", 200),
        ("champion_probability", 100),
    ):
        assert sum(row[field] for row in results) == pytest.approx(total, abs=size * 0.005)
    assert final is not None
    finalists = {final["team1"], final["team2"]}
    assert len(finalists & {team.name for team in teams[: size // 2]}) == 1
    assert len(finalists & {team.name for team in teams[size // 2 :]}) == 1
    assert 0 < final["probability"] <= 100


@pytest.mark.parametrize("size", [0, 1, 3, 8])
def test_tournament_empty_singleton_byes_and_semifinal_entry(monkeypatch, size):
    """Bracket counting handles byes and entry into semifinals without double counting stages."""
    from football import engine

    teams = [Team(str(i), 70, 70, 70, 70, 70) for i in range(size)]
    monkeypatch.setattr(engine, "_simulate_knockout_match", lambda first, second, rng: first)
    results, champion, count, final = simulate_tournament(teams, 1)
    assert count == 1000
    assert champion == ("0" if size else None)
    assert sum(row["champion_probability"] for row in results) == (100 if size else 0)
    assert final == (
        None
        if size < 2
        else {
            "team1": str(2 if size == 3 else 4),
            "team2": "0",
            "team1_id": -(3 if size == 3 else 5),
            "team2_id": -1,
            "probability": 100,
        }
    )
    if size == 8:
        assert {r["team"] for r in results if r["semifinal_probability"] == 100} == {
            "0",
            "2",
            "4",
            "6",
        }


@pytest.mark.parametrize(
    "means,clutch",
    [((1.3, 1.3), (70, 70)), ((2, 0.6), (80, 20)), ((2, 0.6), (0, 0)), ((0.05, 0.02), (80, 20))],
)
def test_sampling_matches_independent_advancement(monkeypatch, means, clutch):
    import math

    from football import engine

    a = Team("Same", 70, 70, 70, 70, clutch[0], team_id=1)
    b = Team("Same", 70, 70, 70, 70, clutch[1], team_id=2)
    monkeypatch.setattr(Match, "expected_goals", lambda self: means)
    distributions = [
        [math.exp(-mean) * mean**k / math.factorial(k) for k in range(40)] for mean in means
    ]
    first, second = distributions
    win = sum(first[i] * sum(second[:i]) for i in range(40))
    draw = sum(x * y for x, y in zip(first, second, strict=True))
    q = clutch[0] / sum(clutch) if sum(clutch) else 0.5
    expected = win + draw * q
    rng = random.Random(2026)
    n = 20000
    observed = sum(engine._simulate_knockout_match(a, b, rng) is a for _ in range(n)) / n
    assert abs(observed - expected) < 6 * math.sqrt(expected * (1 - expected) / n)


@pytest.fixture
def regulation_match(balanced_match):
    return Match(balanced_match.team1, balanced_match.team2, regulation_horizon=True)


@pytest.mark.parametrize(
    "minute,ratio", [(0, 1), (45, 0.5), (89, 1 / 90), (90, 0), (91, 0), (105, 0), (120, 0)]
)
def test_regulation_horizon_time_and_expected_goals(regulation_match, minute, ratio):
    regulation_match.match_minute = minute
    assert regulation_match.remaining_time_ratio() == ratio
    assert regulation_match.expected_goals() == pytest.approx((1.3 * ratio, 1.3 * ratio))
    assert regulation_match.match_minute == minute


@pytest.mark.parametrize("minute", [90, 91, 105, 120])
@pytest.mark.parametrize(
    "score,probabilities", [((2, 1), (1, 0, 0)), ((1, 2), (0, 0, 1)), ((0, 0), (0, 1, 0))]
)
def test_regulation_horizon_summarizes_supplied_score(
    regulation_match, minute, score, probabilities
):
    match = regulation_match
    match.match_minute = minute
    match.team1.goals, match.team2.goals = score
    # Extreme accepted events cannot restore future goals after the modeled horizon.
    match.team1.red_cards = 11
    match.team2.shots_on_target = 1000
    match.team2.big_chances = 1000
    assert match.expected_goals() == (0, 0)
    p1, draw, p2, most_likely, scorelines = match.calculate_probabilities()
    assert (p1, draw, p2) == probabilities
    assert most_likely == score
    assert scorelines == [{"team1_goals": score[0], "team2_goals": score[1], "probability": 1}]
    assert match.match_minute == minute
    assert match.match_status_short == ""  # No completion inferred or recorded.


@pytest.mark.parametrize("minute", [45, 90, 105])
@pytest.mark.parametrize("status,extra", [("", 0), ("FT", 0), ("ET", 30), ("arbitrary", 5)])
def test_regulation_horizon_does_not_infer_phases(regulation_match, minute, status, extra):
    match = regulation_match
    match.match_minute = minute
    baseline = match.calculate_probabilities()
    match.match_status_short = status
    match.match_extra_minute = extra
    assert match.calculate_probabilities() == baseline
    assert (match.match_status_short, match.match_extra_minute) == (status, extra)


@pytest.mark.parametrize("minute", [0, 45, 89])
@pytest.mark.parametrize("red_cards", [0, 11])
def test_regulation_expected_goals_preserve_weights_without_positive_floor(
    regulation_match, minute, red_cards
):
    import math

    match = regulation_match
    match.match_minute = minute
    match.team1.offense = match.team1.defense = match.team1.form = 0
    match.team1.star_power = match.team1.clutch = 0
    match.team1.red_cards = red_cards
    match.team2.offense = match.team2.defense = match.team2.form = 100
    match.team2.star_power = match.team2.clutch = 100
    match.team2.fifa_rank = 1
    # The score functions themselves are unchanged; independently apply the xG equation.
    strength1, strength2 = 1, 101.92
    ratio = (90 - minute) / 90
    expected = (
        max(2.6 * ratio * strength1 / (strength1 + strength2) - 0.22 * ratio * red_cards, 0),
        2.6 * ratio * strength2 / (strength1 + strength2) + 0.18 * ratio * red_cards,
    )
    actual = match.expected_goals()
    assert actual == pytest.approx(expected, abs=1e-15)
    assert all(math.isfinite(value) and value >= 0 for value in actual)
    if red_cards:
        assert actual[0] == 0
    if minute == 89 and not red_cards:
        assert 0 < actual[0] < 0.02


def independent_poisson(mean, count=80):
    """High-precision direct PMFs, independent of the engine's recurrence and stopping rule."""
    import math
    from decimal import Decimal, localcontext

    with localcontext() as context:
        context.prec = 70
        value = Decimal.from_float(float(mean))
        return [
            (-value).exp() * (value**k if k else Decimal(1)) / Decimal(math.factorial(k))
            for k in range(count)
        ]


@pytest.mark.parametrize("mean", [0, 1e-14, 0.02, 0.039, 0.5, 1, 1.3, 2.6, 4.58])
def test_adaptive_poisson_tail_against_independent_decimal_probabilities(mean):
    import math
    from decimal import Decimal, localcontext

    actual = Match._prediction_poisson_distribution(mean)
    reference = independent_poisson(mean)
    with localcontext() as context:
        context.prec = 70
        omitted = Decimal(1) - sum(reference[: len(actual)])
        assert 0 <= omitted <= Decimal("2.5e-13")
        # Also bound the retained floating-point distribution, rather than only exact terms.
        retained = sum(Decimal.from_float(value) for value in actual)
        assert abs(1 - retained * retained) < Decimal("1e-12")
    assert all(math.isfinite(value) and value >= 0 for value in actual)
    assert actual == pytest.approx([float(p) for p in reference[: len(actual)]], abs=1e-16)
    if mean == 0:
        assert actual == [1]


def test_adaptive_poisson_bound_across_accepted_mean_range():
    from decimal import Decimal, localcontext

    # lambda <= 2.6 + 0.18*11: allocation cannot exceed the full goal budget,
    # and own red cards only decrease it. Include every hundredth and the endpoint.
    lengths = []
    for index in range(459):
        mean = index / 100
        distribution = Match._prediction_poisson_distribution(mean)
        lengths.append(len(distribution))
        with localcontext() as context:
            context.prec = 70
            retained = sum(independent_poisson(mean, len(distribution)))
            assert 0 <= 1 - retained <= Decimal("2.5e-13")
    assert lengths[0] == 1
    assert lengths[-1] > 11
    assert lengths == sorted(lengths)


@pytest.mark.parametrize(
    "means,score",
    [
        ((0, 0), (0, 0)),
        ((1e-14, 0), (0, 0)),
        ((0, 1.3), (2, 0)),
        ((1.3, 1.3), (0, 0)),
        ((2, 0.6), (1, 2)),
        ((4.58, 0), (0, 10)),
        ((4.58, 4.58), (1000, 1000)),
    ],
)
def test_regulation_probabilities_against_independent_joint_distribution(
    regulation_match, monkeypatch, means, score
):
    import math

    match = regulation_match
    match.team1.goals, match.team2.goals = score
    monkeypatch.setattr(match, "expected_goals", lambda: means)
    first, second = ([float(p) for p in independent_poisson(mean)] for mean in means)
    cells = [
        {"team1_goals": score[0] + i, "team2_goals": score[1] + j, "probability": p * q}
        for i, p in enumerate(first)
        for j, q in enumerate(second)
        if p * q > 0
    ]
    expected = [
        math.fsum(
            cell["probability"]
            for cell in cells
            if compare(cell["team1_goals"], cell["team2_goals"])
        )
        for compare in (lambda a, b: a > b, lambda a, b: a == b, lambda a, b: a < b)
    ]
    actual = match.calculate_probabilities()
    assert actual[:3] == pytest.approx(expected, abs=1e-12)
    assert math.fsum(actual[:3]) == pytest.approx(1, abs=1e-15)
    cells.sort(key=lambda cell: cell["probability"], reverse=True)
    assert actual[3] == (cells[0]["team1_goals"], cells[0]["team2_goals"])
    assert len(actual[4]) == min(5, len(cells))
    for observed, reference in zip(actual[4], cells[:5], strict=False):
        assert observed.keys() == reference.keys()
        assert (observed["team1_goals"], observed["team2_goals"]) == (
            reference["team1_goals"],
            reference["team2_goals"],
        )
        assert observed["probability"] == pytest.approx(reference["probability"], abs=1e-12)


def test_regulation_ten_goal_deficit_includes_comeback():
    a, b = Team("A", 100, 100, 100, 100, 100), Team("B", 0, 0, 0, 0, 0)
    b.goals, b.red_cards = 10, 11
    corrected = Match(a, b, regulation_horizon=True)
    # B has 80 scoreline points, -132 red-card points and 60 goal-pressure points:
    # strength 8. A has strength 100; B's adjusted expected goals clamp to zero.
    mean = 2.6 * 100 / 108 + 0.18 * 11
    assert corrected.expected_goals() == pytest.approx((mean, 0))
    distribution = independent_poisson(mean)
    expected_draw = float(distribution[10])
    expected_win = float(sum(distribution[11:]))
    win, draw, loss, _, _ = corrected.calculate_probabilities()
    assert win == pytest.approx(expected_win, abs=1e-12)
    assert draw == pytest.approx(expected_draw, abs=1e-12)
    assert loss == pytest.approx(1 - expected_win - expected_draw, abs=1e-12)
    assert win > 0.005
    assert Match(a, b).calculate_probabilities()[0] == 0


@pytest.mark.parametrize("mean", [-1, float("nan"), float("inf"), -float("inf"), 1000])
def test_prediction_poisson_rejects_unsupported_numerical_means(mean):
    with pytest.raises(ValueError, match="Poisson mean"):
        Match._prediction_poisson_distribution(mean)


def test_poisson_zero_mean_pmf():
    assert Match.poisson_probability(0, 0) == 1
    assert all(Match.poisson_probability(goals, 0) == 0 for goals in range(1, 12))


def test_regulation_scoreline_ties_preserve_nested_loop_order(regulation_match, monkeypatch):
    monkeypatch.setattr(regulation_match, "expected_goals", lambda: (1, 1))
    result = regulation_match.calculate_probabilities()
    assert [(cell["team1_goals"], cell["team2_goals"]) for cell in result[4]] == [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
        (0, 2),
    ]
    assert result == regulation_match.calculate_probabilities(max_additional_goals=0)


def test_regulation_retains_advancement_momentum_and_confidence_formulas(regulation_match):
    match = regulation_match
    match.team1.clutch, match.team2.clutch = 80, 20
    match.team1.shots = 8
    match.team1.shots_on_target = 3
    match.team2.corners = 4
    legacy = Match(match.team1, match.team2)
    probabilities = match.calculate_probabilities()[:3]
    assert match.advancement_probabilities(probabilities) == legacy.advancement_probabilities(
        probabilities
    )
    assert match.live_momentum_percentages() == legacy.live_momentum_percentages()
    assert match.prediction_confidence(probabilities) == legacy.prediction_confidence(probabilities)


def test_seeded_tournament_matches_recorded_pre_correction_output():
    # Captured before introducing the prediction-only opt-in, not regenerated afterward.
    teams = [
        Team(
            f"Team {i % 3}",
            40 + i,
            100 - i,
            50 + i,
            i,
            20 + i,
            fifa_rank=i + 1,
            team_id=i + 1,
        )
        for i in range(4)
    ]
    results, champion, count, final = simulate_tournament(teams, 1000, seed=2026)
    assert champion == "Team 2" and count == 1000
    assert [(r["team_id"], r["final_probability"], r["champion_probability"]) for r in results] == [
        (3, 52.8, 25.4),
        (4, 47.2, 25.3),
        (1, 48.5, 24.9),
        (2, 51.5, 24.4),
    ]
    assert all(r["semifinal_probability"] == 100 for r in results)
    assert final == {
        "team1": "Team 1",
        "team1_id": 2,
        "team2": "Team 2",
        "team2_id": 3,
        "probability": 27.6,
    }
