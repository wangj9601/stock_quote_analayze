-- 东财行业板块成分股：board_code ↔ stock_code（多对多）
-- PostgreSQL

CREATE TABLE IF NOT EXISTS industry_board_constituents (
    board_code VARCHAR(20) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (board_code, stock_code)
);

CREATE INDEX IF NOT EXISTS ix_industry_board_constituents_stock_code
    ON industry_board_constituents (stock_code);

CREATE INDEX IF NOT EXISTS ix_industry_board_constituents_board_code
    ON industry_board_constituents (board_code);

COMMENT ON TABLE industry_board_constituents IS '东财行业板块成分股映射';
COMMENT ON COLUMN industry_board_constituents.board_code IS '板块代码，如 BK0479';
COMMENT ON COLUMN industry_board_constituents.stock_code IS 'A股代码，6位';
COMMENT ON COLUMN industry_board_constituents.stock_name IS '成分股名称快照';
COMMENT ON COLUMN industry_board_constituents.updated_at IS '本次同步时间';
