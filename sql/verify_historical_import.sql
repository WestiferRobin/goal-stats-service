-- Read-only current/complete historical acceptance. See sql/README.md for settings.
-- Approved facts mirror data/verification/womens-world-cup-coverage.json.
\set ON_ERROR_STOP on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
WITH expected AS (
    SELECT * FROM jsonb_to_recordset($approved$
[
  {
    "edition": "1991",
    "start": "1991-11-16",
    "finish": "1991-11-30",
    "matches": 26,
    "participants": [
      "brazil",
      "china",
      "denmark",
      "germany",
      "italy",
      "japan",
      "new zealand",
      "nigeria",
      "norway",
      "sweden",
      "taiwan",
      "united states"
    ],
    "goals": 99
  },
  {
    "edition": "1995",
    "start": "1995-06-05",
    "finish": "1995-06-18",
    "matches": 26,
    "participants": [
      "australia",
      "brazil",
      "canada",
      "china",
      "denmark",
      "england",
      "germany",
      "japan",
      "nigeria",
      "norway",
      "sweden",
      "united states"
    ],
    "goals": 99
  },
  {
    "edition": "1999",
    "start": "1999-06-19",
    "finish": "1999-07-10",
    "matches": 32,
    "participants": [
      "australia",
      "brazil",
      "canada",
      "china",
      "denmark",
      "germany",
      "ghana",
      "italy",
      "japan",
      "mexico",
      "nigeria",
      "north korea",
      "norway",
      "russia",
      "sweden",
      "united states"
    ],
    "goals": 123
  },
  {
    "edition": "2003",
    "start": "2003-09-20",
    "finish": "2003-10-12",
    "matches": 32,
    "participants": [
      "argentina",
      "australia",
      "brazil",
      "canada",
      "china",
      "france",
      "germany",
      "ghana",
      "japan",
      "nigeria",
      "north korea",
      "norway",
      "russia",
      "south korea",
      "sweden",
      "united states"
    ],
    "goals": 107
  },
  {
    "edition": "2007",
    "start": "2007-09-10",
    "finish": "2007-09-30",
    "matches": 32,
    "participants": [
      "argentina",
      "australia",
      "brazil",
      "canada",
      "china",
      "denmark",
      "england",
      "germany",
      "ghana",
      "japan",
      "new zealand",
      "nigeria",
      "north korea",
      "norway",
      "sweden",
      "united states"
    ],
    "goals": 111
  },
  {
    "edition": "2011",
    "start": "2011-06-26",
    "finish": "2011-07-17",
    "matches": 32,
    "participants": [
      "australia",
      "brazil",
      "canada",
      "colombia",
      "england",
      "equatorial guinea",
      "france",
      "germany",
      "japan",
      "mexico",
      "new zealand",
      "nigeria",
      "north korea",
      "norway",
      "sweden",
      "united states"
    ],
    "goals": 86
  },
  {
    "edition": "2015",
    "start": "2015-06-06",
    "finish": "2015-07-05",
    "matches": 52,
    "participants": [
      "australia",
      "brazil",
      "cameroon",
      "canada",
      "china",
      "colombia",
      "costa rica",
      "ecuador",
      "england",
      "france",
      "germany",
      "ivory coast",
      "japan",
      "mexico",
      "netherlands",
      "new zealand",
      "nigeria",
      "norway",
      "south korea",
      "spain",
      "sweden",
      "switzerland",
      "thailand",
      "united states"
    ],
    "goals": 146
  },
  {
    "edition": "2019",
    "start": "2019-06-07",
    "finish": "2019-07-07",
    "matches": 52,
    "participants": [
      "argentina",
      "australia",
      "brazil",
      "cameroon",
      "canada",
      "chile",
      "china",
      "england",
      "france",
      "germany",
      "italy",
      "jamaica",
      "japan",
      "netherlands",
      "new zealand",
      "nigeria",
      "norway",
      "scotland",
      "south africa",
      "south korea",
      "spain",
      "sweden",
      "thailand",
      "united states"
    ],
    "goals": 146
  },
  {
    "edition": "2023",
    "start": "2023-07-20",
    "finish": "2023-08-20",
    "matches": 64,
    "participants": [
      "argentina",
      "australia",
      "brazil",
      "canada",
      "china",
      "colombia",
      "costa rica",
      "denmark",
      "england",
      "france",
      "germany",
      "haiti",
      "italy",
      "jamaica",
      "japan",
      "morocco",
      "netherlands",
      "new zealand",
      "nigeria",
      "norway",
      "panama",
      "philippines",
      "portugal",
      "republic of ireland",
      "south africa",
      "south korea",
      "spain",
      "sweden",
      "switzerland",
      "united states",
      "vietnam",
      "zambia"
    ],
    "goals": 164
  }
]
$approved$::jsonb) AS e(edition text, start date, finish date, matches integer,
                       participants text[], goals integer)
), settings AS (
    SELECT coalesce(nullif(current_setting('goalstats.verify_complete', true), ''), 'false')::boolean
               AS complete,
           nullif(current_setting('goalstats.verify_database', true), '') AS database_name,
           nullif(current_setting('goalstats.verify_preservation', true), '')::jsonb AS preservation
), selected_competitions AS (
    SELECT c.* FROM competitions c JOIN expected e ON e.edition = c.edition_label
    WHERE c.name_key = 'fifa women''s world cup' OR c.name = 'FIFA Women''s World Cup'
), selected AS (
    SELECT m.*, c.edition_label, c.name AS competition_name, c.name_key AS competition_key,
           c.category AS competition_category, h.name_key AS home_key, a.name_key AS away_key,
           h.category AS home_category, a.category AS away_category
    FROM matches m
    LEFT JOIN competitions c ON c.competition_id = m.competition_id
    LEFT JOIN teams h ON h.team_id = m.home_team_id
    LEFT JOIN teams a ON a.team_id = m.away_team_id
    WHERE m.source = 'martj42_womens_results' AND (
        c.competition_id IN (SELECT competition_id FROM selected_competitions)
        OR (m.source_tournament = 'FIFA World Cup' AND
            extract(year FROM m.match_date)::text IN (SELECT edition FROM expected))
    )
), participants AS (
    SELECT edition_label, home_key AS name_key FROM selected
    UNION SELECT edition_label, away_key FROM selected
), coverage AS (
    SELECT e.edition, e.matches AS expected_matches, cardinality(e.participants) AS expected_teams,
           (SELECT count(*) FROM selected_competitions c WHERE c.edition_label = e.edition)
               AS competitions,
           count(m.match_id) AS matches, min(m.match_date) AS first_date, max(m.match_date) AS last_date,
           coalesce(sum(m.home_score + m.away_score), 0) AS goals,
           (SELECT count(*) FROM participants p WHERE p.edition_label = e.edition) AS teams,
           (SELECT array_agg(p.name_key::text ORDER BY p.name_key COLLATE "C")
            FROM participants p WHERE p.edition_label = e.edition) AS team_keys,
           e.start, e.finish, e.goals AS expected_goals, e.participants AS expected_participants
    FROM expected e LEFT JOIN selected m ON m.edition_label = e.edition
    GROUP BY e.edition, e.matches, e.participants, e.start, e.finish, e.goals
), preservation AS (
    SELECT 'teams' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM teams t
    UNION ALL
    SELECT 'competitions' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM competitions t
    UNION ALL
    SELECT 'matches' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM matches t
    UNION ALL
    SELECT 'scenarios' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM scenarios t
    UNION ALL
    SELECT 'predictions' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM predictions t
    UNION ALL
    SELECT 'football_teams' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM football_teams t
    UNION ALL
    SELECT 'football_history' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM football_history t
    UNION ALL
    SELECT 'football_snapshots' AS entity, count(*) AS rows,
           md5(coalesce(string_agg(to_jsonb(t)::text, E'\n' ORDER BY to_jsonb(t)::text COLLATE "C"), '')) AS digest
    FROM football_snapshots t
), preservation_report AS (
    SELECT jsonb_object_agg(entity, jsonb_build_object('rows', rows, 'digest', digest)) AS evidence
    FROM preservation
), checks AS (
    SELECT 'database identity' AS check_name,
           s.database_name IS NULL OR s.database_name = current_database() AS passed FROM settings s
    UNION ALL SELECT 'Alembic head',
        (SELECT count(*) = 1 AND min(version_num) = 'a7c93e25d104' FROM alembic_version)
    UNION ALL SELECT 'competition identity/category', NOT EXISTS (
        SELECT 1 FROM selected_competitions WHERE name <> 'FIFA Women''s World Cup'
          OR name_key <> 'fifa women''s world cup' OR category <> 'women_senior_national')
    UNION ALL SELECT 'edition coverage: ' || c.edition,
        CASE WHEN c.competitions = 0 AND c.matches = 0 AND NOT s.complete THEN true
             ELSE c.competitions = 1 AND c.matches = c.expected_matches
               AND c.teams = c.expected_teams AND c.team_keys = c.expected_participants
               AND c.goals = c.expected_goals AND c.first_date >= c.start AND c.last_date <= c.finish
        END
        FROM coverage c CROSS JOIN settings s
    UNION ALL SELECT 'source facts/provenance/references', NOT EXISTS (
        SELECT 1 FROM selected m WHERE
            m.edition_label IS NULL OR m.edition_label NOT IN (SELECT edition FROM expected)
            OR m.competition_name IS DISTINCT FROM 'FIFA Women''s World Cup'
            OR m.competition_key IS DISTINCT FROM 'fifa women''s world cup'
            OR m.competition_category IS DISTINCT FROM 'women_senior_national'
            OR m.home_key IS NULL OR m.away_key IS NULL OR m.home_team_id = m.away_team_id
            OR m.home_category IS DISTINCT FROM 'women_senior_national'
            OR m.away_category IS DISTINCT FROM 'women_senior_national'
            OR m.home_score IS NULL OR m.away_score IS NULL OR m.home_score < 0 OR m.away_score < 0
            OR m.score_basis IS DISTINCT FROM 'including_extra_time_no_shootout'
            OR m.source_tournament IS DISTINCT FROM 'FIFA World Cup'
            OR m.source_version IS DISTINCT FROM '1855e313ae8bcd0330426e62c8e4cf15ce45077c'
            OR m.source_file_sha256 IS DISTINCT FROM
                'de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0'
            OR m.source_url IS DISTINCT FROM
                'https://github.com/martj42/womens-international-results/blob/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv'
            OR m.source_row IS NULL OR m.source_row NOT BETWEEN 2 AND 11651
            OR m.source_record_key IS NULL OR m.source_record_key !~ '^[0-9a-f]{64}$'
            OR m.source_home_team IS NULL OR btrim(m.source_home_team) = ''
            OR m.source_away_team IS NULL OR btrim(m.source_away_team) = ''
            OR lower(btrim(m.source_home_team)) IS DISTINCT FROM m.home_key
            OR lower(btrim(m.source_away_team)) IS DISTINCT FROM m.away_key
            OR m.imported_at IS NULL
    )
    UNION ALL SELECT 'duplicate source identities', NOT EXISTS (
        SELECT 1 FROM selected GROUP BY source, source_record_key HAVING count(*) > 1)
    UNION ALL SELECT 'complete totals', NOT s.complete OR (
        (SELECT count(*) FROM selected) = 348 AND
        (SELECT count(DISTINCT name_key) FROM participants) = 44
    ) FROM settings s
    UNION ALL SELECT 'record preservation', s.preservation IS NULL OR s.preservation = p.evidence
        FROM settings s CROSS JOIN preservation_report p
), verdict AS (
    SELECT bool_and(coalesce(passed, false)) AS passed,
           string_agg(check_name, ', ' ORDER BY check_name) FILTER (WHERE NOT coalesce(passed, false))
               AS failures FROM checks
)
SELECT current_database() AS database, current_user AS database_user,
       (SELECT version_num FROM alembic_version LIMIT 1) AS alembic_head,
       CASE WHEN s.complete THEN 'complete' ELSE 'current' END AS acceptance_level,
       current_setting('transaction_read_only') AS transaction_read_only,
       (SELECT jsonb_agg(jsonb_build_object('edition', edition, 'matches', matches, 'teams', teams,
                                           'goals', goals, 'first_date', first_date, 'last_date', last_date)
                         ORDER BY edition) FROM coverage) AS coverage,
       p.evidence AS preservation,
       CASE WHEN v.passed THEN 1
            ELSE ('Historical verification failed: ' || v.failures)::integer END AS acceptance_passed
FROM settings s CROSS JOIN verdict v CROSS JOIN preservation_report p;
COMMIT;
