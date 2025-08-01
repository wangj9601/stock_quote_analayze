-- PostgreSQL 数据库迁移脚本
-- 股票分析系统数据库迁移
-- 创建时间: 2024年
-- 数据库: stock_analysis

-- =====================================================
-- 1. 创建数据库（如果不存在）
-- =====================================================
-- 注意：需要手动创建数据库
-- CREATE DATABASE stock_analysis;

-- =====================================================
-- 2. 创建扩展
-- =====================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 3. 创建表结构
-- =====================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- 管理员表
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- 股票基本信息表
CREATE TABLE IF NOT EXISTS stock_basic_info (
    code INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- 实时行情表
CREATE TABLE IF NOT EXISTS stock_realtime_quote (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    current_price DECIMAL(10,2),
    change_percent DECIMAL(8,2),
    volume DECIMAL(15,2),
    amount DECIMAL(15,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    open DECIMAL(10,2),
    pre_close DECIMAL(10,2),
    turnover_rate DECIMAL(8,2),
    pe_dynamic DECIMAL(10,2),
    total_market_value DECIMAL(15,2),
    pb_ratio DECIMAL(8,2),
    circulating_market_value DECIMAL(15,2),
    update_time TIMESTAMP
);

-- 历史行情表
CREATE TABLE IF NOT EXISTS historical_quotes (
    code VARCHAR(20),
    ts_code VARCHAR(20),
    name VARCHAR(100),
    market VARCHAR(20),
    date DATE,
    open DECIMAL(10,2),
    close DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    pre_close DECIMAL(10,2),
    volume BIGINT,
    amount DECIMAL(15,2),
    amplitude DECIMAL(8,2),
    change_percent DECIMAL(8,2),
    change DECIMAL(10,2),
    turnover_rate DECIMAL(8,2),
    collected_source VARCHAR(50),
    collected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date)
);

-- 自选股表
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100) NOT NULL,
    group_name VARCHAR(50) DEFAULT 'default',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 自选股分组表
CREATE TABLE IF NOT EXISTS watchlist_groups (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    group_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 自选股历史采集日志表
CREATE TABLE IF NOT EXISTS watchlist_history_collection_logs (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    affected_rows INTEGER,
    status VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 股票新闻表
CREATE TABLE IF NOT EXISTS stock_news (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20),
    title TEXT NOT NULL,
    content TEXT,
    publish_time TIMESTAMP,
    source VARCHAR(100),
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 股票公告表
CREATE TABLE IF NOT EXISTS stock_notice_report (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20),
    title TEXT NOT NULL,
    content TEXT,
    publish_time TIMESTAMP,
    source VARCHAR(100),
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 股票研报表
CREATE TABLE IF NOT EXISTS stock_research_report (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20),
    title TEXT NOT NULL,
    content TEXT,
    publish_time TIMESTAMP,
    source VARCHAR(100),
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 行情数据表
CREATE TABLE IF NOT EXISTS quote_data (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    last_price DECIMAL(10,2) NOT NULL,
    pre_close DECIMAL(10,2) NOT NULL,
    change_percent DECIMAL(8,2) NOT NULL,
    volume DECIMAL(15,2) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 行情同步任务表
CREATE TABLE IF NOT EXISTS quote_sync_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 4. 创建索引
-- =====================================================

-- 用户表索引
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- 管理员表索引
CREATE INDEX IF NOT EXISTS idx_admins_username ON admins(username);
CREATE INDEX IF NOT EXISTS idx_admins_email ON admins(email);

-- 实时行情表索引
CREATE INDEX IF NOT EXISTS idx_stock_realtime_quote_name ON stock_realtime_quote(name);
CREATE INDEX IF NOT EXISTS idx_stock_realtime_quote_update_time ON stock_realtime_quote(update_time);

-- 历史行情表索引
CREATE INDEX IF NOT EXISTS idx_historical_quotes_code ON historical_quotes(code);
CREATE INDEX IF NOT EXISTS idx_historical_quotes_date ON historical_quotes(date);
CREATE INDEX IF NOT EXISTS idx_historical_quotes_ts_code ON historical_quotes(ts_code);
CREATE INDEX IF NOT EXISTS idx_historical_quotes_collected_date ON historical_quotes(collected_date);

-- 自选股表索引
CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlist(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_stock_code ON watchlist(stock_code);
CREATE INDEX IF NOT EXISTS idx_watchlist_group_name ON watchlist(group_name);

-- 自选股分组表索引
CREATE INDEX IF NOT EXISTS idx_watchlist_groups_user_id ON watchlist_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_groups_group_name ON watchlist_groups(group_name);

-- 自选股历史采集日志表索引
CREATE INDEX IF NOT EXISTS idx_watchlist_history_collection_logs_stock_code ON watchlist_history_collection_logs(stock_code);
CREATE INDEX IF NOT EXISTS idx_watchlist_history_collection_logs_status ON watchlist_history_collection_logs(status);
CREATE INDEX IF NOT EXISTS idx_watchlist_history_collection_logs_created_at ON watchlist_history_collection_logs(created_at);

-- 股票新闻表索引
CREATE INDEX IF NOT EXISTS idx_stock_news_stock_code ON stock_news(stock_code);
CREATE INDEX IF NOT EXISTS idx_stock_news_publish_time ON stock_news(publish_time);
CREATE INDEX IF NOT EXISTS idx_stock_news_source ON stock_news(source);

-- 股票公告表索引
CREATE INDEX IF NOT EXISTS idx_stock_notice_report_stock_code ON stock_notice_report(stock_code);
CREATE INDEX IF NOT EXISTS idx_stock_notice_report_publish_time ON stock_notice_report(publish_time);
CREATE INDEX IF NOT EXISTS idx_stock_notice_report_source ON stock_notice_report(source);

-- 股票研报表索引
CREATE INDEX IF NOT EXISTS idx_stock_research_report_stock_code ON stock_research_report(stock_code);
CREATE INDEX IF NOT EXISTS idx_stock_research_report_publish_time ON stock_research_report(publish_time);
CREATE INDEX IF NOT EXISTS idx_stock_research_report_source ON stock_research_report(source);

-- 行情数据表索引
CREATE INDEX IF NOT EXISTS idx_quote_data_stock_code ON quote_data(stock_code);
CREATE INDEX IF NOT EXISTS idx_quote_data_trade_date ON quote_data(trade_date);
CREATE INDEX IF NOT EXISTS idx_quote_data_stock_code_trade_date ON quote_data(stock_code, trade_date);

-- 行情同步任务表索引
CREATE INDEX IF NOT EXISTS idx_quote_sync_tasks_status ON quote_sync_tasks(status);
CREATE INDEX IF NOT EXISTS idx_quote_sync_tasks_created_at ON quote_sync_tasks(created_at);

-- =====================================================
-- 5. 创建外键约束（可选）
-- =====================================================

-- 自选股表外键约束
-- ALTER TABLE watchlist ADD CONSTRAINT fk_watchlist_user_id 
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 自选股分组表外键约束
-- ALTER TABLE watchlist_groups ADD CONSTRAINT fk_watchlist_groups_user_id 
--     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- =====================================================
-- 6. 创建视图
-- =====================================================

/*
-- 股票综合信息视图
CREATE OR REPLACE VIEW stock_summary AS
SELECT 
    sbi.code,
    sbi.name,
    srq.current_price,
    srq.change_percent,
    srq.volume,
    srq.amount,
    srq.high,
    srq.low,
    srq.open,
    srq.pre_close,
    srq.turnover_rate,
    srq.pe_dynamic,
    srq.total_market_value,
    srq.pb_ratio,
    srq.circulating_market_value,
    srq.update_time
FROM stock_basic_info sbi
LEFT JOIN stock_realtime_quote srq ON sbi.code = srq.code; */


-- =====================================================
-- 7. 创建函数
-- =====================================================

-- 更新行情数据时自动更新updated_at字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为quote_data表创建触发器
CREATE TRIGGER update_quote_data_updated_at 
    BEFORE UPDATE ON quote_data 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 为quote_sync_tasks表创建触发器
CREATE TRIGGER update_quote_sync_tasks_updated_at 
    BEFORE UPDATE ON quote_sync_tasks 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 8. 数据导出命令（需要在psql中执行）
-- =====================================================

/*
-- 导出表结构
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis --schema-only > schema_backup.sql

-- 导出所有数据
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis --data-only > data_backup.sql

-- 导出完整数据库（结构+数据）
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis > full_backup.sql

-- 导出特定表的数据
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis -t stock_realtime_quote --data-only > stock_realtime_quote_data.sql
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis -t historical_quotes --data-only > historical_quotes_data.sql
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis -t stock_news --data-only > stock_news_data.sql
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis -t users --data-only > users_data.sql
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis -t watchlist --data-only > watchlist_data.sql
*/

-- =====================================================
-- 9. 数据导入命令（需要在psql中执行）
-- =====================================================

/*
-- 导入完整数据库
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < full_backup.sql

-- 导入表结构
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < schema_backup.sql

-- 导入数据
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < data_backup.sql

-- 导入特定表数据
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < stock_realtime_quote_data.sql
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < historical_quotes_data.sql
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < stock_news_data.sql
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < users_data.sql
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < watchlist_data.sql
*/

-- =====================================================
-- 10. 权限设置
-- =====================================================

-- 为应用用户授予权限（需要根据实际情况修改用户名）
-- GRANT CONNECT ON DATABASE stock_analysis TO app_user;
-- GRANT USAGE ON SCHEMA public TO app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- =====================================================
-- 11. 完成
-- =====================================================
COMMIT; 