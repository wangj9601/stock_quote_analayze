"""
GMS 周线相关表（可选补齐脚本，与 Alembic 0011_gms_weekly 同步）。

优先使用: python scripts/db_migrate.py upgrade --yes
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from sqlalchemy import text
from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 对应 alembic revision
ALEMBIC_REVISION = "0011_gms_weekly"


def upgrade():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mean_frequency_resonance_indicators_weekly (
                    code TEXT NOT NULL,
                    date VARCHAR NOT NULL,
                    market_type VARCHAR NOT NULL,
                    macro_displacement_delta DOUBLE PRECISION,
                    amplitude DOUBLE PRECISION,
                    ratio_d20 DOUBLE PRECISION,
                    ratio_d1 DOUBLE PRECISION,
                    instant_deviation DOUBLE PRECISION,
                    rising_days_z INTEGER,
                    falling_days_f INTEGER,
                    efficiency_m20_minus_m DOUBLE PRECISION,
                    ma20_d DOUBLE PRECISION,
                    ma60_d DOUBLE PRECISION,
                    mavol20_m DOUBLE PRECISION,
                    bias DOUBLE PRECISION,
                    d1 DOUBLE PRECISION,
                    d1_date VARCHAR(20),
                    d20 DOUBLE PRECISION,
                    d20_date VARCHAR(20),
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, date, market_type)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gms_signal_trace_weekly (
                    code TEXT NOT NULL,
                    date VARCHAR(20) NOT NULL,
                    market_type VARCHAR(10) NOT NULL,
                    config_id INTEGER NOT NULL REFERENCES gms_strategy_configs(id) ON DELETE CASCADE,
                    score_total DOUBLE PRECISION,
                    score_accumulation DOUBLE PRECISION,
                    score_momentum DOUBLE PRECISION,
                    signal_strength DOUBLE PRECISION,
                    buy_type VARCHAR(20),
                    left_buy_signal BOOLEAN,
                    right_buy_signal BOOLEAN,
                    sell_signal BOOLEAN,
                    accumulation_grade VARCHAR(5),
                    momentum_grade VARCHAR(20),
                    delta DOUBLE PRECISION,
                    d DOUBLE PRECISION,
                    ratio_d20 DOUBLE PRECISION,
                    ratio_d1 DOUBLE PRECISION,
                    fz_ratio DOUBLE PRECISION,
                    volume_ratio DOUBLE PRECISION,
                    instant_deviation DOUBLE PRECISION,
                    rising_days INTEGER,
                    falling_days INTEGER,
                    score_acc_fz DOUBLE PRECISION,
                    score_acc_balance DOUBLE PRECISION,
                    score_acc_volume DOUBLE PRECISION,
                    score_mom_ratio_d1 DOUBLE PRECISION,
                    score_mom_deviation DOUBLE PRECISION,
                    score_mom_volume DOUBLE PRECISION,
                    acc_fz_judge VARCHAR(50),
                    acc_balance_judge VARCHAR(50),
                    acc_volume_judge VARCHAR(50),
                    mom_ratio_d1_judge VARCHAR(50),
                    mom_deviation_judge VARCHAR(50),
                    mom_volume_judge VARCHAR(50),
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    risk_tags JSONB,
                    score_detail JSONB,
                    PRIMARY KEY (code, date, market_type, config_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE gms_strategy_configs
                ADD COLUMN IF NOT EXISTS timeframe VARCHAR(16) NOT NULL DEFAULT 'daily'
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE gms_precompute_runs
                ADD COLUMN IF NOT EXISTS timeframe VARCHAR(16) NOT NULL DEFAULT 'daily'
                """
            )
        )
    logger.info("GMS weekly tables ready (alembic %s)", ALEMBIC_REVISION)


if __name__ == "__main__":
    upgrade()
