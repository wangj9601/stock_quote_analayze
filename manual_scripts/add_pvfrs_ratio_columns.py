#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 mean_frequency_resonance_indicators 表添加 ratio_d20、ratio_d1 列
用于 PVFRS 价格指标生成逻辑扩展（幅度比例 Δ/d₂₀、Δ/d₁）
执行后需重新生成指标以回填数据；可配合 backfill_pvfrs 等脚本使用。
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
        for col in ('ratio_d20', 'ratio_d1'):
            try:
                session.execute(text(
                    f'ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN {col} REAL'
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
