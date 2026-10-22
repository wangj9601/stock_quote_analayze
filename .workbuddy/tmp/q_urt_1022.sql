SELECT config_id, COUNT(*), ROUND(MIN(score)::numeric,1), ROUND(MAX(score)::numeric,1), ROUND(AVG(score)::numeric,1) FROM urt_signal_trace WHERE date='2026-10-21' GROUP BY config_id ORDER BY config_id;
SELECT config_id, code, name, ROUND(score::numeric,1) FROM urt_signal_trace WHERE date='2026-10-21' AND config_id IN (13,14) ORDER BY config_id, score DESC NULLS LAST LIMIT 20;
