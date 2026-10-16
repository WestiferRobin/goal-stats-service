"""Provider payload transformation with no HTTP calls or shared live state."""

import pytest

from football import live


@pytest.mark.parametrize(
    "selected,provided,expected",
    [
        ("United States", "UNITED-STATES", True),
        ("Côte d'Ivoire", "Côte d Ivoire", True),
        ("Spain", "Spain Women", False),
        ("", "Spain", False),
        ("Spain", "---", False),
    ],
)
def test_team_matching_uses_complete_normalized_names(selected, provided, expected):
    """Ignore punctuation/case while refusing empty and partial team identities."""
    assert live.team_names_match(selected, provided) is expected


def fixture(home="Spain", away="England"):
    return {
        "fixture": {
            "id": 42,
            "status": {"elapsed": 90, "extra": 3, "short": "2h", "long": "Second half"},
        },
        "teams": {
            "home": {"name": home, "logo": "home.png"},
            "away": {"name": away, "logo": "away.png"},
        },
        "goals": {"home": 2, "away": 1},
    }


@pytest.mark.parametrize(
    "data",
    [None, {}, {"response": []}, {"response": [{}]}, {"response": [fixture("France", "Japan")]}],
)
def test_missing_live_fixture_returns_no_match(monkeypatch, data):
    """Unavailable, empty and unrelated fixtures cannot fabricate a match."""
    monkeypatch.setattr(live, "api_get", lambda *args: data)
    assert live.find_live_fixture("Spain", "England") is None
    assert live.get_real_live_data("Spain", "England") is None


@pytest.mark.parametrize(
    "function,endpoint",
    [
        (live.get_fixture_statistics, "/fixtures/statistics"),
        (live.get_fixture_events, "/fixtures/events"),
    ],
)
@pytest.mark.parametrize(
    "payload,expected", [(None, None), ({}, []), ({"response": [{"id": 1}]}, [{"id": 1}])]
)
def test_fixture_detail_request_and_optional_response(
    monkeypatch, function, endpoint, payload, expected
):
    """Forward the fixture identity and distinguish an outage from an empty result."""
    calls = []
    monkeypatch.setattr(live, "api_get", lambda path, query: calls.append((path, query)) or payload)
    assert function(42) == expected
    assert calls == [(endpoint, {"fixture": 42})]


@pytest.mark.parametrize(
    "event,expected",
    [
        ({"type": "Goal"}, "Goal"),
        ({"type": " card ", "detail": " Red Card "}, "Red card"),
        ({"type": "Card", "detail": "Yellow Card"}, "Yellow card"),
        ({"type": "subst"}, "Substitution"),
        ({"type": "Var"}, "VAR"),
        ({"type": "Other", "detail": "Review"}, "Review"),
        ({"type": "Other"}, "Other"),
        ({}, "Match event"),
    ],
)
def test_event_classification(event, expected):
    """Provider event kinds retain distinct user-facing labels and safe defaults."""
    assert live.classify_event(event) == expected


def test_event_details_order_stoppage_time_and_limit():
    """Only goals show assists; timelines sort elapsed/extra time and retain the last 20."""
    goal = {"type": "Goal", "player": {"name": "Scorer"}, "assist": {"name": "Helper"}}
    assert live.format_event_detail(goal) == "Scorer · Goal · Assist: Helper"
    assert live.format_event_detail({**goal, "type": "Card"}) == "Scorer · Yellow card"
    assert live.build_event_timeline([{}]) == [
        {"minute": "0", "team": "Match", "type": "Match event", "detail": "Match event"}
    ]
    events = [
        {"time": {"elapsed": minute}, "team": {"name": "Spain"}, **goal}
        for minute in range(22, 0, -1)
    ]
    events += [{"time": {"elapsed": 20, "extra": extra}, "type": "VAR"} for extra in [4, 2]]
    result = live.build_event_timeline(events)
    assert len(result) == 20
    assert result[0]["minute"] == "5"
    assert [r["minute"] for r in result[-5:]] == ["20", "20+2", "20+4", "21", "22"]
    assert result[-1]["team"] == "Spain"


def test_card_counts_ignore_other_teams_and_noncard_events():
    """Count each card type without treating goals or unrelated events as cards."""
    events = [
        {"team": {"name": team}, "type": kind, "detail": detail}
        for team, kind, detail in [
            ("Spain", "Card", "Yellow Card"),
            ("SPAIN", "Card", "Red Card"),
            ("Spain", "Card", "Unknown"),
            ("England", "Card", "Red Card"),
            ("Spain", "Goal", "Yellow"),
        ]
    ]
    assert live.count_cards(events, "Spain") == (1, 1)
    assert live.count_cards(events, "England") == (0, 1)


@pytest.mark.parametrize(
    "value,expected", [(None, 0), (" 63.9% ", 63), ("invalid", 0), (4.8, 4), ([], 0), ({}, 0)]
)
def test_statistic_conversion_and_invalid_values(value, expected):
    """Parse percentages/numbers, skip unrelated fields and default malformed values."""
    stats = [{"type": "Other", "value": 99}, {"type": "BALL POSSESSION", "value": value}]
    assert live.extract_stat(stats, "Ball Possession") == expected
    assert live.extract_stat(stats, "Absent") == 0


@pytest.mark.parametrize("reverse", [False, True])
def test_live_snapshot_maps_both_team_orders(monkeypatch, reverse):
    """Transform provider statistics, scores, cards and logos into selected-team order."""
    game = fixture()
    stat_names = [
        "Ball Possession",
        "Total Shots",
        "Shots on Goal",
        "Blocked Shots",
        "Goalkeeper Saves",
        "Corner Kicks",
    ]
    events = [
        {"type": "Card", "detail": "Yellow Card", "team": {"name": "Spain"}},
        {"type": "Card", "detail": "Red Card", "team": {"name": "England"}},
    ]
    payloads = {
        "/fixtures": {"response": [fixture("France", "Japan"), game]},
        "/fixtures/statistics": {
            "response": [
                {
                    "team": {"name": name},
                    "statistics": [
                        {"type": k, "value": v} for k, v in zip(stat_names, values, strict=True)
                    ],
                }
                for name, values in [
                    ("Spain", ["60%", 10, 4, 2, 1, 3]),
                    ("England", ["40%", 7, 2, 1, 2, 4]),
                    ("Other", [0] * 6),
                ]
            ]
        },
        "/fixtures/events": {"response": events},
    }
    calls = []

    def provider(path, params):
        calls.append((path, params))
        return payloads[path]

    monkeypatch.setattr(live, "api_get", provider)
    names = ("England", "Spain") if reverse else ("Spain", "England")
    result = live.get_real_live_data(*names)
    assert result["match_minute"] == 90 and result["match_extra_minute"] == 3
    assert result["match_status_short"] == "2H" and result["match_status_long"] == "Second half"
    home = dict(
        goals=2,
        total_shots=10,
        shots_on_target=4,
        defender_blocks=2,
        goalkeeper_saves=1,
        corners=3,
        yellow_cards=1,
        red_cards=0,
        logo="home.png",
    )
    away = dict(
        goals=1,
        total_shots=7,
        shots_on_target=2,
        defender_blocks=1,
        goalkeeper_saves=2,
        corners=4,
        yellow_cards=0,
        red_cards=1,
        logo="away.png",
    )
    for side, expected in enumerate([away, home] if reverse else [home, away], 1):
        assert {key: result[f"team{side}_{key}"] for key in expected} == expected
        assert result[f"team{side}_big_chances"] == 0
        assert result[f"team{side}_bad_star"] is False
    assert result["team1_possession"] == (40 if reverse else 60)
    assert len(result["event_timeline"]) == 2
    assert calls == [
        ("/fixtures", {"live": "all"}),
        ("/fixtures/statistics", {"fixture": 42}),
        ("/fixtures/events", {"fixture": 42}),
    ]


@pytest.mark.parametrize("missing", ["id", "statistics", "events", "empty"])
def test_live_missing_details_and_optional_defaults(monkeypatch, missing):
    """Unavailable details return no snapshot; empty valid details retain neutral defaults."""
    game = fixture()
    game["goals"] = {"home": None, "away": None}
    game["fixture"]["status"] = {}
    if missing == "id":
        del game["fixture"]["id"]
    monkeypatch.setattr(live, "find_live_fixture", lambda *args: game)
    monkeypatch.setattr(
        live, "get_fixture_statistics", lambda _: None if missing == "statistics" else []
    )
    monkeypatch.setattr(live, "get_fixture_events", lambda _: None if missing == "events" else [])
    result = live.get_real_live_data("Spain", "England")
    if missing != "empty":
        assert result is None
    else:
        assert result["team1_possession"] == 50
        assert result["team1_goals"] == result["team2_goals"] == 0
        assert result["match_minute"] == result["match_extra_minute"] == 0
        assert result["match_status_short"] == result["match_status_long"] == ""
        assert result["event_timeline"] == []
