-- 东财概念板块基础信息与成分股
-- PostgreSQL

CREATE TABLE IF NOT EXISTS concept_board_basic_info (
    board_code VARCHAR(20) PRIMARY KEY,
    board_name VARCHAR(100),
    create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS concept_board_constituents (
    board_code VARCHAR(20) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (board_code, stock_code)
);

CREATE INDEX IF NOT EXISTS ix_concept_board_constituents_stock_code
    ON concept_board_constituents (stock_code);

CREATE INDEX IF NOT EXISTS ix_concept_board_constituents_board_code
    ON concept_board_constituents (board_code);

COMMENT ON TABLE concept_board_basic_info IS '东财概念板块列表';
COMMENT ON TABLE concept_board_constituents IS '东财概念板块成分股映射';
