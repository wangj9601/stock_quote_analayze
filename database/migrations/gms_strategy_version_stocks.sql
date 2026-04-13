-- ==========================================
-- 表：gms_strategy_version_stocks（GMS 策略版本观察股）
-- 与 backend_api.models.GMSStrategyVersionStock 保持一致
-- 数据库：PostgreSQL
-- ==========================================

-- 依赖：需先存在 gms_strategy_versions 表（见 add_gms_strategy_version_watchlist_tables.sql）

CREATE TABLE IF NOT EXISTS gms_strategy_version_stocks (
    id SERIAL PRIMARY KEY,
    version_id INTEGER NOT NULL,
    market VARCHAR(10) NOT NULL,
    stock_code VARCHAR(32) NOT NULL,
    stock_name VARCHAR(100),
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
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
COMMENT ON COLUMN gms_strategy_version_stocks.is_verified IS '是否已核对';
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


-- ==========================================
-- 升级：若表由旧版脚本创建且缺少 is_verified 列，执行以下语句（可重复执行）
-- ==========================================
ALTER TABLE gms_strategy_version_stocks
    ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN gms_strategy_version_stocks.is_verified IS '是否已核对';
