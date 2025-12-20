DROP VIEW IF EXISTS view_daily_app_usage;

CREATE OR REPLACE VIEW view_daily_app_usage AS
SELECT
    user_id,
    DATE(usage_date) AS usage_date,
    package_name,
    SUM(total_seconds) / 60 AS total_minutes,
    COUNT(*) AS session_count
FROM
    daily_usage_log
GROUP BY
    user_id, usage_date, package_name;