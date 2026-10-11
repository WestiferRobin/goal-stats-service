-- Read-only Task #2 acceptance checks. No migrations, imports or repairs.
\set ON_ERROR_STOP on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

SELECT current_database() AS database, current_user AS database_user;
SELECT version_num FROM alembic_version;

SELECT 'teams' AS entity, count(*) FROM teams
UNION ALL SELECT 'competitions', count(*) FROM competitions
UNION ALL SELECT 'matches', count(*) FROM matches;

SELECT source, source_version, count(*) AS matches
FROM matches GROUP BY source, source_version ORDER BY source, source_version;

SELECT count(DISTINCT team_id) AS selected_teams FROM (
    SELECT home_team_id AS team_id FROM matches WHERE source = 'martj42_womens_results'
    UNION
    SELECT away_team_id FROM matches WHERE source = 'martj42_womens_results'
) AS participants;

SELECT source, source_record_key, count(*)
FROM matches GROUP BY source, source_record_key HAVING count(*) > 1;

SELECT m.match_id
FROM matches m
LEFT JOIN teams h ON h.team_id = m.home_team_id
LEFT JOIN teams a ON a.team_id = m.away_team_id
LEFT JOIN competitions c ON c.competition_id = m.competition_id
WHERE h.team_id IS NULL OR a.team_id IS NULL OR c.competition_id IS NULL;

SELECT m.match_date, c.name AS competition, c.edition_label,
       h.name AS home_team, a.name AS away_team,
       m.home_score, m.away_score, m.score_basis,
       m.city, m.country, m.neutral, m.match_id
FROM matches m
JOIN teams h ON h.team_id = m.home_team_id
JOIN teams a ON a.team_id = m.away_team_id
JOIN competitions c ON c.competition_id = m.competition_id
WHERE m.source = 'martj42_womens_results'
ORDER BY m.match_date, m.match_id;

SELECT 'football_teams' AS entity, count(*) FROM football_teams
UNION ALL SELECT 'football_history', count(*) FROM football_history
UNION ALL SELECT 'football_snapshots', count(*) FROM football_snapshots;

-- A stable digest includes keys, facts, timestamps, and original provenance.
SELECT md5(string_agg(to_jsonb(m)::text, E'\n' ORDER BY match_id)) AS source_record_digest
FROM matches m WHERE source = 'martj42_womens_results';
COMMIT;
