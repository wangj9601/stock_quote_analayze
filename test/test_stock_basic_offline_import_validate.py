"""
离线导入解析测试（不落库）：
python test/test_stock_basic_offline_import_validate.py ./sample_stock_basic.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend_core.utils.stock_basic_importer import parse_import_file


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python test/test_stock_basic_offline_import_validate.py <csv_or_xlsx_path>")
        sys.exit(1)
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"文件不存在: {p}")
        sys.exit(1)

    rows, issues = parse_import_file(p.name, p.read_bytes())
    print(json.dumps({"valid_rows": len(rows), "invalid_rows": len(issues)}, ensure_ascii=False, indent=2))
    if issues:
        print("issues sample:")
        print(json.dumps([x.__dict__ for x in issues[:20]], ensure_ascii=False, indent=2))
    if rows:
        print("rows sample:")
        print(json.dumps(rows[:5], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

