-- ==========================================
-- GMS策略版本与观察股管理表
-- 创建时间：2026-04-10
-- 说明：用于管理 GMS 策略版本及其对应观察股（A股/港股）
-- ==========================================

-- 1) GMS策略版本主表
CREATE TABLE IF NOT EXISTS gms_strategy_versions (
    id SERIAL PRIMARY KEY,
    strategy_code VARCHAR(50) NOT NULL,
    version_name VARCHAR(100) NOT NULL,
    version_no INTEGER NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_gms_strategy_code_version_no UNIQUE (strategy_code, version_no)
);

COMMENT ON TABLE gms_strategy_versions IS 'GMS策略版本主表';
COMMENT ON COLUMN gms_strategy_versions.id IS '主键ID';
COMMENT ON COLUMN gms_strategy_versions.strategy_code IS '策略编码，例如GMS';
COMMENT ON COLUMN gms_strategy_versions.version_name IS '版本名称';
COMMENT ON COLUMN gms_strategy_versions.version_no IS '版本号（同策略内唯一）';
COMMENT ON COLUMN gms_strategy_versions.description IS '版本描述';
COMMENT ON COLUMN gms_strategy_versions.is_active IS '是否启用';
COMMENT ON COLUMN gms_strategy_versions.created_by IS '创建人';
COMMENT ON COLUMN gms_strategy_versions.created_at IS '创建时间';
COMMENT ON COLUMN gms_strategy_versions.updated_at IS '更新时间';

CREATE INDEX IF NOT EXISTS idx_gms_strategy_versions_strategy_code
ON gms_strategy_versions (strategy_code);

COMMENT ON INDEX idx_gms_strategy_versions_strategy_code IS '按策略编码查询策略版本';


-- 2) GMS策略版本观察股关系表
CREATE TABLE IF NOT EXISTS gms_strategy_version_stocks (
    id SERIAL PRIMARY KEY,
    version_id INTEGER NOT NULL,
    market VARCHAR(10) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    remark TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_gms_version_stocks_version_id
        FOREIGN KEY (version_id)
        REFERENCES gms_strategy_versions (id)
        ON DELETE CASCADE,
    CONSTRAINT uq_gms_version_market_code
        UNIQUE (version_id, market, stock_code),
    CONSTRAINT ck_gms_version_stocks_market
        CHECK (market IN ('A', 'HK'))
);

COMMENT ON TABLE gms_strategy_version_stocks IS 'GMS策略版本观察股关系表';
COMMENT ON COLUMN gms_strategy_version_stocks.id IS '主键ID';
COMMENT ON COLUMN gms_strategy_version_stocks.version_id IS '策略版本ID';
COMMENT ON COLUMN gms_strategy_version_stocks.market IS '市场类型：A=A股，HK=港股';
COMMENT ON COLUMN gms_strategy_version_stocks.stock_code IS '股票代码';
COMMENT ON COLUMN gms_strategy_version_stocks.stock_name IS '股票名称（冗余存储，便于展示）';
COMMENT ON COLUMN gms_strategy_version_stocks.sort_order IS '排序值（越小越靠前）';
COMMENT ON COLUMN gms_strategy_version_stocks.status IS '状态：active/inactive';
COMMENT ON COLUMN gms_strategy_version_stocks.remark IS '备注';
COMMENT ON COLUMN gms_strategy_version_stocks.created_at IS '创建时间';
COMMENT ON COLUMN gms_strategy_version_stocks.updated_at IS '更新时间';

CREATE INDEX IF NOT EXISTS idx_gms_version_stocks_version_id
ON gms_strategy_version_stocks (version_id);
COMMENT ON INDEX idx_gms_version_stocks_version_id IS '按策略版本查询观察股列表';

CREATE INDEX IF NOT EXISTS idx_gms_version_stocks_market
ON gms_strategy_version_stocks (market);
COMMENT ON INDEX idx_gms_version_stocks_market IS '按市场筛选观察股';

CREATE INDEX IF NOT EXISTS idx_gms_version_stocks_code
ON gms_strategy_version_stocks (stock_code);
COMMENT ON INDEX idx_gms_version_stocks_code IS '按股票代码查询观察股';

CREATE INDEX IF NOT EXISTS idx_gms_version_status
ON gms_strategy_version_stocks (version_id, status);
COMMENT ON INDEX idx_gms_version_status IS '按策略版本和状态筛选观察股';

