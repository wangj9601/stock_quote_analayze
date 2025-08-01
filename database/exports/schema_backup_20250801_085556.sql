-- PostgreSQL 数据库结构导出
-- 导出时间: 2025-08-01 08:55:57.041546
-- 数据库: stock_analysis

CREATE TABLE admins (
    id bigint NOT NULL DEFAULT nextval('admins_id_seq'::regclass),
    username text,
    password_hash text,
    role text DEFAULT 'admin'::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp without time zone,
);

CREATE TABLE data_collection_log (
    id bigint NOT NULL,
    data_type text,
    stock_code text,
    status text,
    error_message text,
    collect_time timestamp with time zone,
);

CREATE TABLE historical_collect_operation_logs (
    id bigint NOT NULL DEFAULT nextval('historical_collect_operation_logs_id_seq'::regclass),
    operation_type text,
    operation_desc text,
    affected_rows bigint,
    status text,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE historical_quotes (
    code text NOT NULL,
    name text,
    market text,
    date text NOT NULL,
    open real,
    high real,
    low real,
    close real,
    volume real,
    amount real,
    change_percent real,
    collected_date timestamp without time zone,
    ts_code text,
    collected_source text,
    pre_close real,
    change real,
    turnover_rate real,
    amplitude real,
);

CREATE TABLE index_realtime_quotes (
    code text NOT NULL,
    name text,
    price real,
    change real,
    pct_chg real,
    open real,
    pre_close real,
    high real,
    low real,
    volume real,
    amount real,
    amplitude real,
    turnover real,
    pe real,
    volume_ratio real,
    update_time text NOT NULL,
    collect_time text,
    index_spot_type integer NOT NULL,
);

CREATE TABLE industry_board_realtime_quotes (
    board_code text NOT NULL,
    board_name text,
    latest_price real,
    change_amount real,
    change_percent real,
    total_market_value real,
    volume real,
    amount real,
    turnover_rate real,
    leading_stock_name text,
    leading_stock_change_percent real,
    leading_stock_code text,
    update_time timestamp without time zone NOT NULL,
);

CREATE TABLE operation_logs (
    id bigint NOT NULL DEFAULT nextval('operation_logs_id_seq'::regclass),
    user_id bigint,
    action text,
    stock_code text,
    stock_name text,
    group_name text,
    timestamp text,
);

CREATE TABLE price_alerts (
    id bigint NOT NULL,
    user_id bigint,
    stock_code text,
    stock_name text,
    condition_type text,
    target_price real,
    current_price real,
    status text DEFAULT 'active'::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    triggered_at timestamp without time zone,
);

CREATE TABLE quote_data (
    id bigint NOT NULL,
    stock_code text,
    stock_name text,
    trade_date date,
    open double precision,
    high double precision,
    low double precision,
    last_price double precision,
    pre_close double precision,
    change_percent double precision,
    volume double precision,
    amount double precision,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
);

CREATE TABLE quote_sync_tasks (
    id bigint NOT NULL,
    task_type text,
    status text,
    progress double precision,
    error_message text,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
);

CREATE TABLE realtime_collect_operation_logs (
    id bigint NOT NULL DEFAULT nextval('realtime_collect_operation_logs_id_seq'::regclass),
    operation_type text,
    operation_desc text,
    affected_rows bigint,
    status text,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE stock_basic_info (
    code text NOT NULL,
    name text,
    create_date timestamp without time zone,
    total_share real,
);

CREATE TABLE stock_basic_info_bak (
    code text,
    name text,
);

CREATE TABLE stock_news (
    id bigint NOT NULL,
    stock_code text,
    title text,
    content text,
    keywords text,
    publish_time text,
    source text,
    url text,
    summary text,
    type text,
    rating text,
    target_price text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
);

CREATE TABLE stock_notice_report (
    id bigint NOT NULL DEFAULT nextval('stock_notice_report_id_seq'::regclass),
    code text,
    name text,
    notice_title text,
    notice_type text,
    publish_date text,
    url text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE stock_realtime_quote (
    code text NOT NULL,
    name text,
    current_price real,
    change_percent real,
    volume real,
    amount real,
    high real,
    low real,
    open real,
    pre_close real,
    turnover_rate real,
    pe_dynamic real,
    total_market_value real,
    pb_ratio real,
    circulating_market_value real,
    update_time timestamp without time zone,
);

CREATE TABLE stock_research_reports (
    id bigint NOT NULL DEFAULT nextval('stock_research_reports_id_seq'::regclass),
    stock_code text,
    stock_name text,
    report_name text,
    dongcai_rating text,
    institution text,
    monthly_report_count bigint DEFAULT '0'::bigint,
    profit_2024 real,
    pe_2024 real,
    profit_2025 real,
    pe_2025 real,
    profit_2026 real,
    pe_2026 real,
    industry text,
    report_date text,
    pdf_url text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE users (
    id bigint NOT NULL DEFAULT nextval('users_id_seq'::regclass),
    username text,
    email text,
    password_hash text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp without time zone,
    status text DEFAULT 'active'::text,
);

CREATE TABLE watchlist (
    id bigint NOT NULL DEFAULT nextval('watchlist_id_seq'::regclass),
    user_id bigint,
    stock_code text,
    stock_name text,
    group_name text DEFAULT 'default'::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE watchlist_groups (
    id bigint NOT NULL,
    user_id bigint,
    group_name text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE watchlist_history_collection_logs (
    id integer NOT NULL DEFAULT nextval('watchlist_history_collection_logs_id_seq'::regclass),
    stock_code character varying,
    affected_rows integer,
    status character varying,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
);
