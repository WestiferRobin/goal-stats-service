# mypy: ignore-errors
"""RoadToTheFinal provider mapping, without dotenv or process-global match caches."""

from football.provider import api_get


def normalize_team_name(team_name):
    """
    Converts team names into a simplified form for safer comparison.

    Example:
    "United States" becomes "unitedstates".
    """
    return "".join(character for character in team_name.lower() if character.isalnum())


def team_names_match(selected_name, api_name):
    """
    Compares a selected team name with the name returned by API-Football.

    Exact normalized matches are preferred, but partial matching is allowed
    for API names that may include additional words.
    """
    selected_key = normalize_team_name(selected_name)
    api_key = normalize_team_name(api_name)
    if not selected_key or not api_key:
        return False
    return selected_key == api_key


def find_live_fixture(team1_name, team2_name):
    data = api_get("/fixtures", {"live": "all"})
    if data is None:
        return None
    fixtures = data.get("response", [])
    if not fixtures:
        return None
    for fixture_data in fixtures:
        home_team = fixture_data.get("teams", {}).get("home", {}).get("name", "")
        away_team = fixture_data.get("teams", {}).get("away", {}).get("name", "")
        normal_order = team_names_match(team1_name, home_team) and team_names_match(
            team2_name, away_team
        )
        reverse_order = team_names_match(team1_name, away_team) and team_names_match(
            team2_name, home_team
        )
        if normal_order or reverse_order:
            return fixture_data
    return None


def get_fixture_statistics(fixture_id):
    data = api_get("/fixtures/statistics", {"fixture": fixture_id})
    if data is None:
        return None
    return data.get("response", [])


def get_fixture_events(fixture_id):
    data = api_get("/fixtures/events", {"fixture": fixture_id})
    if data is None:
        return None
    return data.get("response", [])


def classify_event(event):
    event_type = str(event.get("type", "")).strip()
    event_detail = str(event.get("detail", "")).strip()
    combined = f"{event_type} {event_detail}".lower()
    if event_type.lower() == "goal":
        return "Goal"
    if event_type.lower() == "card":
        if "red" in combined:
            return "Red card"
        return "Yellow card"
    if event_type.lower() == "subst":
        return "Substitution"
    if event_type.lower() == "var":
        return "VAR"
    return event_detail or event_type or "Match event"


def format_event_detail(event):
    player_name = event.get("player", {}).get("name", "")
    assist_name = event.get("assist", {}).get("name", "")
    event_label = classify_event(event)
    detail_parts = []
    if player_name:
        detail_parts.append(player_name)
    detail_parts.append(event_label)
    if assist_name and event_label == "Goal":
        detail_parts.append(f"Assist: {assist_name}")
    return " · ".join(detail_parts)


def build_event_timeline(events):
    timeline = []
    for event in events:
        event_time = event.get("time", {})
        minute = event_time.get("elapsed") or 0
        extra = event_time.get("extra")
        if extra:
            minute_label = f"{minute}+{extra}"
        else:
            minute_label = str(minute)
        team_name = event.get("team", {}).get("name", "")
        timeline.append(
            {
                "minute": minute_label,
                "team": team_name or "Match",
                "type": classify_event(event),
                "detail": format_event_detail(event),
            }
        )
    timeline.sort(
        key=lambda item: (
            int(str(item["minute"]).split("+")[0]),
            int(str(item["minute"]).split("+")[1]) if "+" in str(item["minute"]) else 0,
        )
    )
    return timeline[-20:]


def count_cards(events, team_name):
    yellow_cards = 0
    red_cards = 0
    for event in events:
        event_team = event.get("team", {}).get("name", "")
        if team_name.lower() not in event_team.lower():
            continue
        event_type = str(event.get("type", ""))
        event_detail = str(event.get("detail", ""))
        combined = f"{event_type} {event_detail}".lower()
        if event_type.lower() != "card":
            continue
        if "red" in combined:
            red_cards += 1
        elif "yellow" in combined:
            yellow_cards += 1
    return (yellow_cards, red_cards)


def extract_stat(team_stats, stat_name):
    for stat in team_stats:
        current_type = str(stat.get("type", ""))
        if current_type.lower() != stat_name.lower():
            continue
        value = stat.get("value")
        if value is None:
            return 0
        if isinstance(value, str):
            cleaned_value = value.replace("%", "").strip()
            try:
                return int(float(cleaned_value))
            except ValueError:
                return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def get_real_live_data(team1_name, team2_name):
    fixture = find_live_fixture(team1_name, team2_name)
    if fixture is None:
        return None
    fixture_information = fixture.get("fixture", {})
    fixture_id = fixture_information.get("id")
    if fixture_id is None:
        return None
    status = fixture_information.get("status", {})
    match_minute = status.get("elapsed") or 0
    match_extra_minute = status.get("extra") or 0
    match_status_short = str(status.get("short", "") or "").upper()
    match_status_long = str(status.get("long", "") or "")
    home_team_data = fixture.get("teams", {}).get("home", {})
    away_team_data = fixture.get("teams", {}).get("away", {})
    home_team = home_team_data.get("name", "")
    away_team = away_team_data.get("name", "")
    home_logo = home_team_data.get("logo", "")
    away_logo = away_team_data.get("logo", "")
    home_goals = fixture.get("goals", {}).get("home") or 0
    away_goals = fixture.get("goals", {}).get("away") or 0
    statistics = get_fixture_statistics(fixture_id)
    events = get_fixture_events(fixture_id)
    if statistics is None or events is None:
        return None
    home_stats = []
    away_stats = []
    for team_statistics in statistics:
        statistics_team_name = team_statistics.get("team", {}).get("name", "")
        current_statistics = team_statistics.get("statistics", [])
        if home_team.lower() in statistics_team_name.lower():
            home_stats = current_statistics
        elif away_team.lower() in statistics_team_name.lower():
            away_stats = current_statistics
    home_yellow_cards, home_red_cards = count_cards(events, home_team)
    away_yellow_cards, away_red_cards = count_cards(events, away_team)
    home_values = {
        "goals": home_goals,
        "possession": extract_stat(home_stats, "Ball Possession"),
        "total_shots": extract_stat(home_stats, "Total Shots"),
        "shots_on_target": extract_stat(home_stats, "Shots on Goal"),
        "blocked_shots": extract_stat(home_stats, "Blocked Shots"),
        "goalkeeper_saves": extract_stat(home_stats, "Goalkeeper Saves"),
        "corners": extract_stat(home_stats, "Corner Kicks"),
        "yellow_cards": home_yellow_cards,
        "red_cards": home_red_cards,
    }
    away_values = {
        "goals": away_goals,
        "possession": extract_stat(away_stats, "Ball Possession"),
        "total_shots": extract_stat(away_stats, "Total Shots"),
        "shots_on_target": extract_stat(away_stats, "Shots on Goal"),
        "blocked_shots": extract_stat(away_stats, "Blocked Shots"),
        "goalkeeper_saves": extract_stat(away_stats, "Goalkeeper Saves"),
        "corners": extract_stat(away_stats, "Corner Kicks"),
        "yellow_cards": away_yellow_cards,
        "red_cards": away_red_cards,
    }
    home_values["big_chances"] = 0
    away_values["big_chances"] = 0
    team1_is_home = team_names_match(team1_name, home_team)
    team1_values = home_values if team1_is_home else away_values
    team2_values = away_values if team1_is_home else home_values
    team1_logo = home_logo if team1_is_home else away_logo
    team2_logo = away_logo if team1_is_home else home_logo
    team1_possession = team1_values["possession"]
    if team1_possession == 0:
        team1_possession = 50
    return {
        "match_minute": match_minute,
        "match_extra_minute": match_extra_minute,
        "match_status_short": match_status_short,
        "match_status_long": match_status_long,
        "team1_logo": team1_logo,
        "team2_logo": team2_logo,
        "team1_goals": team1_values["goals"],
        "team2_goals": team2_values["goals"],
        "team1_possession": team1_possession,
        "team1_total_shots": team1_values["total_shots"],
        "team2_total_shots": team2_values["total_shots"],
        "team1_shots_on_target": team1_values["shots_on_target"],
        "team2_shots_on_target": team2_values["shots_on_target"],
        "team1_big_chances": team1_values["big_chances"],
        "team2_big_chances": team2_values["big_chances"],
        "team1_defender_blocks": team1_values["blocked_shots"],
        "team2_defender_blocks": team2_values["blocked_shots"],
        "team1_goalkeeper_saves": team1_values["goalkeeper_saves"],
        "team2_goalkeeper_saves": team2_values["goalkeeper_saves"],
        "team1_corners": team1_values["corners"],
        "team2_corners": team2_values["corners"],
        "team1_yellow_cards": team1_values["yellow_cards"],
        "team2_yellow_cards": team2_values["yellow_cards"],
        "team1_red_cards": team1_values["red_cards"],
        "team2_red_cards": team2_values["red_cards"],
        "team1_bad_star": False,
        "team2_bad_star": False,
        "event_timeline": build_event_timeline(events),
    }
