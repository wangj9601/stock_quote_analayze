#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 mean_frequency_resonance_indicators 表添加 d1、d1_date、d20、d20_date 列
用于 PVFRS 指标采集时记录周期起点与末位价格及对应交易日期。
执行后需重新生成指标以回填数据。
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
        cols = [
            ('d1', 'REAL'),
            ('d1_date', 'TEXT'),
            ('d20', 'REAL'),
            ('d20_date', 'TEXT'),
        ]
        for col, dtype in cols:
            try:
                session.execute(text(
                    f'ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN {col} {dtype}'
                ))
                session.commit()
                print(f"已添加列: {col}")
            except Exception as e:
                session.rollback()
                if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                    print(f"列 {col} 已存在，跳过")
                else:
                    raise
        print("done.")
    finally:
        session.close()


if __name__ == '__main__':
    main()
