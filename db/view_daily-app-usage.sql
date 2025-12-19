DROP VIEW IF EXISTS view_daily_app_usage;

CREATE OR REPLACE VIEW view_daily_app_usage AS
SELECT
    user_id,
    DATE(usage_date) as usage_date,
    package_name,
    -- HATA KAYNAĞI: SUM(...) yerine MAX(...) kullanılmalı
    MAX(total_seconds) / 60 as total_minutes, 
    COUNT(*) as session_count
FROM
    daily_usage_logs -- app_session yerine işlenmiş tabloyu kullanmak daha sağlıklıdır
GROUP BY
    user_id, usage_date, package_name;