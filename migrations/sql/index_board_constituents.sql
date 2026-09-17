-- 指数板块基础信息与成分股
-- PostgreSQL

CREATE TABLE IF NOT EXISTS index_board_basic_info (
    board_code VARCHAR(20) PRIMARY KEY,
    board_name VARCHAR(100),
    create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE,
    frontend_visible_flag BOOLEAN NOT NULL DEFAULT TRUE,
    board_code_source VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS index_board_constituents (
    board_code VARCHAR(20) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (board_code, stock_code)
);

CREATE INDEX IF NOT EXISTS ix_index_board_constituents_stock_code
    ON index_board_constituents (stock_code);

CREATE INDEX IF NOT EXISTS ix_index_board_constituents_board_code
    ON index_board_constituents (board_code);

COMMENT ON TABLE index_board_basic_info IS '指数板块列表（管理端维护）';
COMMENT ON TABLE index_board_constituents IS '指数板块成分股映射';
COMMENT ON COLUMN index_board_basic_info.trade_observe_flag IS '交易观察标志：管理端标记需重点关注的板块';
COMMENT ON COLUMN index_board_basic_info.frontend_visible_flag IS '是否对网站前端显示';
COMMENT ON COLUMN index_board_basic_info.board_code_source IS '板块代码来源：eastmoney/tonghuashun/huatai/manual/other';
