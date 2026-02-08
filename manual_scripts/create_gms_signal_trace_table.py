#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建 gms_signal_trace 表
用于存储 GMS 策略每日信号追溯记录。
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from backend_core.database.db import SessionLocal


def main():
    session = SessionLocal()
    try:
        # PostgreSQL / 兼容 SQLite 的建表语句
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS gms_signal_trace (
                code VARCHAR(20) NOT NULL,
                date VARCHAR(20) NOT NULL,
                market_type VARCHAR(10) NOT NULL,
                score_total REAL,
                score_accumulation REAL,
                score_momentum REAL,
                signal_strength REAL,
                buy_type VARCHAR(20),
                left_buy_signal BOOLEAN,
                right_buy_signal BOOLEAN,
                sell_signal BOOLEAN,
                accumulation_grade VARCHAR(5),
                momentum_grade VARCHAR(20),
                delta REAL,
                d REAL,
                ratio_d20 REAL,
                ratio_d1 REAL,
                fz_ratio REAL,
                volume_ratio REAL,
                instant_deviation REAL,
                rising_days INTEGER,
                falling_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, date, market_type)
            )
        """))
        session.commit()
        print("gms_signal_trace 表创建完成")
    except Exception as e:
        session.rollback()
        if 'already exists' in str(e).lower():
            print("gms_signal_trace 表已存在，跳过")
        else:
            raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
