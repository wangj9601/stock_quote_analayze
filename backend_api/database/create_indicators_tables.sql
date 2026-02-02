-- 创建技术指标数据表的SQL脚本

-- MA移动平均线指标数据表
CREATE TABLE IF NOT EXISTS ma_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
    ma5 FLOAT,
    ma10 FLOAT,
    ma20 FLOAT,
    ma30 FLOAT,
    ma60 FLOAT,
    ma120 FLOAT,
    ma200 FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type),
    INDEX idx_ma_code_date (code, date)
);

-- MAVOL成交量移动平均线指标数据表
CREATE TABLE IF NOT EXISTS mavol_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
    mavol5 FLOAT,
    mavol10 FLOAT,
    mavol20 FLOAT,
    mavol30 FLOAT,
    mavol60 FLOAT,
    mavol120 FLOAT,
    mavol200 FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type),
    INDEX idx_mavol_code_date (code, date)
);

-- KDJ随机指标数据表
CREATE TABLE IF NOT EXISTS kdj_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
    k FLOAT,
    d FLOAT,
    j FLOAT,
    rsv FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type),
    INDEX idx_kdj_code_date (code, date)
);

-- RSI相对强弱指标数据表
CREATE TABLE IF NOT EXISTS rsi_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
    rsi6 FLOAT,
    rsi12 FLOAT,
    rsi24 FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type),
    INDEX idx_rsi_code_date (code, date)
);

-- BOLL布林带指标数据表
CREATE TABLE IF NOT EXISTS boll_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,
    market_type VARCHAR(10) NOT NULL DEFAULT 'CN',
    boll_mid FLOAT,
    boll_upper FLOAT,
    boll_lower FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type),
    INDEX idx_boll_code_date (code, date)
);

-- 为现有表添加market_type字段的迁移脚本（如果需要）
-- ALTER TABLE ma_indicators ADD COLUMN market_type VARCHAR(10) NOT NULL DEFAULT 'CN';
-- ALTER TABLE mavol_indicators ADD COLUMN market_type VARCHAR(10) NOT NULL DEFAULT 'CN';
-- ALTER TABLE kdj_indicators ADD COLUMN market_type VARCHAR(10) NOT NULL DEFAULT 'CN';
-- ALTER TABLE rsi_indicators ADD COLUMN market_type VARCHAR(10) NOT NULL DEFAULT 'CN';
-- ALTER TABLE boll_indicators ADD COLUMN market_type VARCHAR(10) NOT NULL DEFAULT 'CN';
