DROP VIEW IF EXISTS view_daily_app_usage;

CREATE VIEW view_daily_app_usage AS
SELECT
    user_id,
    DATE(started_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Istanbul') as usage_date,
    package_name,
    SUM(COALESCE((payload->>'total_seconds')::int, 0)) / 60 as total_minutes,
    COUNT(*) as session_count
FROM
    app_session
WHERE
    ended_at IS NOT NULL
GROUP BY
    user_id, usage_date, package_name;