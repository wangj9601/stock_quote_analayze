# -*- coding: utf-8 -*-
"""迁移：板块入场闸门相关表（资金特征 / 板RS / 估值日表 / 闸门日快照）。

用法:
    python migrations/add_board_gate_tables.py
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS board_fund_flow_features (
                    board_kind VARCHAR(16) NOT NULL,
                    board_code_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
                    board_code VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    inflow_streak INTEGER,
                    outflow_streak INTEGER,
                    pos_days_5 INTEGER,
                    pos_days_20 INTEGER,
                    net_sum_5 DOUBLE PRECISION,
                    net_sum_20 DOUBLE PRECISION,
                    day_net DOUBLE PRECISION,
                    fund_stage VARCHAR(16),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (board_kind, board_code_source, board_code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_fund_flow_features_date
                ON board_fund_flow_features (trade_date DESC)
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS board_rs_ratings (
                    board_kind VARCHAR(16) NOT NULL,
                    board_code VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    rs_raw DOUBLE PRECISION,
                    rs_rating INTEGER,
                    rs_observe INTEGER,
                    rs_source VARCHAR(32),
                    universe VARCHAR(32),
                    member_rs_median DOUBLE PRECISION,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (board_kind, board_code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_rs_ratings_date
                ON board_rs_ratings (trade_date DESC)
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS board_valuation_daily (
                    board_kind VARCHAR(16) NOT NULL,
                    board_code VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    board_pe_median DOUBLE PRECISION,
                    board_pb_median DOUBLE PRECISION,
                    board_roe_median DOUBLE PRECISION,
                    pe_pct DOUBLE PRECISION,
                    pb_pct DOUBLE PRECISION,
                    coverage_ratio DOUBLE PRECISION,
                    valuation_unknown BOOLEAN NOT NULL DEFAULT TRUE,
                    member_count INTEGER,
                    valid_pe_count INTEGER,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (board_kind, board_code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_valuation_daily_date
                ON board_valuation_daily (trade_date DESC)
                """
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS board_gate_daily (
                    board_kind VARCHAR(16) NOT NULL,
                    board_code_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
                    board_code VARCHAR(32) NOT NULL,
                    trade_date DATE NOT NULL,
                    board_name VARCHAR(100),
                    trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE,
                    short_raw VARCHAR(16),
                    short_state VARCHAR(16),
                    short_confirm_count INTEGER,
                    midlong_raw VARCHAR(16),
                    midlong_state VARCHAR(16),
                    midlong_confirm_count INTEGER,
                    conflict_action VARCHAR(32),
                    evidence_json JSONB,
                    degraded_json JSONB,
                    shadow_hard_filter_hint VARCHAR(64),
                    v2_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (board_kind, board_code_source, board_code, trade_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_gate_daily_date
                ON board_gate_daily (trade_date DESC)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_gate_daily_short_state
                ON board_gate_daily (trade_date, short_state)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_board_gate_daily_midlong_state
                ON board_gate_daily (trade_date, midlong_state)
                """
            )
        )

    logger.info("board gate 相关表迁移完成")


if __name__ == "__main__":
    upgrade()
