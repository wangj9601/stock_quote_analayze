-- MACD指标数据表建表语句（PostgreSQL）
-- 用于存储A股和港股的MACD指标数据

CREATE TABLE IF NOT EXISTS macd_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,  -- 使用VARCHAR类型以兼容A股Date和港股String
    market_type VARCHAR(10) NOT NULL,  -- 'A股' 或 '港股'
    dif REAL,  -- DIF值（快线EMA12 - 慢线EMA26）
    dea REAL,  -- DEA值（DIF的9日EMA）
    macd REAL,  -- MACD柱状图值（DIF - DEA）
    ema12 REAL,  -- 12日指数移动平均
    ema26 REAL,  -- 26日指数移动平均
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type)
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_macd_indicators_code ON macd_indicators(code);
CREATE INDEX IF NOT EXISTS idx_macd_indicators_date ON macd_indicators(date);
CREATE INDEX IF NOT EXISTS idx_macd_indicators_market_type ON macd_indicators(market_type);
CREATE INDEX IF NOT EXISTS idx_macd_indicators_code_date ON macd_indicators(code, date);

-- 添加表注释
COMMENT ON TABLE macd_indicators IS 'MACD指标数据表（A股和港股共用）';
COMMENT ON COLUMN macd_indicators.code IS '股票代码';
COMMENT ON COLUMN macd_indicators.date IS '交易日期（YYYY-MM-DD格式）';
COMMENT ON COLUMN macd_indicators.market_type IS '市场类型：A股或港股';
COMMENT ON COLUMN macd_indicators.dif IS 'DIF值（快线EMA12 - 慢线EMA26）';
COMMENT ON COLUMN macd_indicators.dea IS 'DEA值（DIF的9日EMA）';
COMMENT ON COLUMN macd_indicators.macd IS 'MACD柱状图值（DIF - DEA）';
COMMENT ON COLUMN macd_indicators.ema12 IS '12日指数移动平均';
COMMENT ON COLUMN macd_indicators.ema26 IS '26日指数移动平均';
COMMENT ON COLUMN macd_indicators.created_at IS '创建时间';

