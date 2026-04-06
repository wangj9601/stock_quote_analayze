-- 无穷成本均线指标表（自数据起点起的累计成交量加权均价，工程口径非通达信筹码 COST）
-- 物理表名：icost_indicators（infinite cost 缩写）
-- PostgreSQL，与 models.InfiniteCostIndicators 一致

CREATE TABLE IF NOT EXISTS icost_indicators (
    -- 字段说明见下行内联注释
    code VARCHAR NOT NULL,              -- 证券代码
    date VARCHAR NOT NULL,              -- 交易日期（与行情表 date 类型一致：A 股/港股均为字符串）
    market_type VARCHAR NOT NULL,       -- 市场类型：CN（A 股）/ HK（港股）
    ic_price DOUBLE PRECISION,          -- 无穷成本均线价：有换手率为 CYC∞ 递归；否则为累计成交额/累计成交量（VWAP）
    cum_amount DOUBLE PRECISION,        -- 累计成交额（自该股最早一条行情至当日的 amount 之和）
    cum_volume DOUBLE PRECISION,        -- 累计成交量（股）：行情表 volume 为「手」，计算时先×100 再累加
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 记录写入时间
    PRIMARY KEY (code, date, market_type)
);

-- 索引名：按代码+日期查询无穷成本数据
CREATE INDEX IF NOT EXISTS idx_icost_indicators_code_date ON icost_indicators (code, date);
