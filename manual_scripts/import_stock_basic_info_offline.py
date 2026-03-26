#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线导入股票基本信息（A股+港股）到 stock_basic_info / stock_basic_info_hk。

默认策略：only_fill_empty（仅补空值，不覆盖已有非空数据）。

示例：
  python manual_scripts/import_stock_basic_info_offline.py --file ./data/stock_basic.csv
  python manual_scripts/import_stock_basic_info_offline.py --file ./data/stock_basic.xlsx --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from backend_api.database import SessionLocal
from backend_core.utils.stock_basic_importer import execute_import_rows, parse_import_file


def main() -> None:
    parser = argparse.ArgumentParser(description="离线导入股票基本信息（CSV/XLSX）")
    parser.add_argument("--file", required=True, help="输入文件路径（csv/xlsx）")
    parser.add_argument("--mode", default="only_fill_empty", choices=["only_fill_empty"], help="导入模式")
    parser.add_argument("--dry-run", action="store_true", help="仅验证与演练，不落库")
    parser.add_argument("--max-errors", type=int, default=100, help="最大错误数，超过即停止")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        raise SystemExit(f"文件不存在: {file_path}")

    content = file_path.read_bytes()
    rows, issues = parse_import_file(file_path.name, content)
    if issues:
        print("校验失败，示例错误如下：")
        print(json.dumps([x.__dict__ for x in issues[:20]], ensure_ascii=False, indent=2))
        raise SystemExit(2)

    session = SessionLocal()
    try:
        result = execute_import_rows(
            session,
            rows,
            mode=args.mode,
            dry_run=args.dry_run,
            max_errors=args.max_errors,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()

