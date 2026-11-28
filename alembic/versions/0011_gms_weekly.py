"""GMS 周线：周频 MF / 周 trace / configs.timeframe / precompute_runs.timeframe

Revision ID: 0011_gms_weekly
Revises: 0010_dragon_tiger
Create Date: 2026-11-28

业务规则见 docs/strategies/gms/GMS_WEEKLY_BUSINESS_RULES.md
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_gms_weekly"
down_revision: Union[str, None] = "0010_dragon_tiger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
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
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_mfri_weekly_date_market
            ON mean_frequency_resonance_indicators_weekly (date, market_type)
            """
        )
    )

    op.execute(
        sa.text(
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
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_gms_trace_weekly_date_cfg
            ON gms_signal_trace_weekly (date, config_id, market_type)
            """
        )
    )

    op.execute(
        sa.text(
            """
            ALTER TABLE gms_strategy_configs
            ADD COLUMN IF NOT EXISTS timeframe VARCHAR(16) NOT NULL DEFAULT 'daily'
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_gms_strategy_configs_timeframe
            ON gms_strategy_configs (timeframe)
            """
        )
    )

    op.execute(
        sa.text(
            """
            ALTER TABLE gms_precompute_runs
            ADD COLUMN IF NOT EXISTS timeframe VARCHAR(16) NOT NULL DEFAULT 'daily'
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS ix_gms_precompute_runs_tf_cfg_date
            ON gms_precompute_runs (timeframe, config_id, trade_date DESC)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_gms_precompute_runs_tf_cfg_date"))
    op.execute(
        sa.text(
            """
            ALTER TABLE gms_precompute_runs DROP COLUMN IF EXISTS timeframe
            """
        )
    )
    op.execute(sa.text("DROP INDEX IF EXISTS ix_gms_strategy_configs_timeframe"))
    op.execute(
        sa.text(
            """
            ALTER TABLE gms_strategy_configs DROP COLUMN IF EXISTS timeframe
            """
        )
    )
    op.execute(sa.text("DROP TABLE IF EXISTS gms_signal_trace_weekly"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_mfri_weekly_date_market"))
    op.execute(sa.text("DROP TABLE IF EXISTS mean_frequency_resonance_indicators_weekly"))
