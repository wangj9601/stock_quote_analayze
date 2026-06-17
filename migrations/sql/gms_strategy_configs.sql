-- GMS 策略参数多版本（PostgreSQL）
-- 执行前请备份 gms_signal_trace

CREATE TABLE IF NOT EXISTS gms_strategy_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    version_label VARCHAR(32),
    description TEXT,
    config_params JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    precompute_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    parent_id INTEGER REFERENCES gms_strategy_configs(id) ON DELETE SET NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_gms_strategy_configs_is_default ON gms_strategy_configs (is_default);
CREATE INDEX IF NOT EXISTS ix_gms_strategy_configs_precompute ON gms_strategy_configs (precompute_enabled);

-- 导入默认版本后，再执行 trace 主键变更（需将 :default_id 替换为实际 id）
-- ALTER TABLE gms_signal_trace ADD COLUMN config_id INTEGER NOT NULL DEFAULT 1;
-- ALTER TABLE gms_signal_trace DROP CONSTRAINT IF EXISTS gms_signal_trace_pkey;
-- ALTER TABLE gms_signal_trace ADD PRIMARY KEY (code, date, market_type, config_id);

ALTER TABLE gms_strategy_versions
    ADD COLUMN IF NOT EXISTS config_id INTEGER REFERENCES gms_strategy_configs(id) ON DELETE SET NULL;
