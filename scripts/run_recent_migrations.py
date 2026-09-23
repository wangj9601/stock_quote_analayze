# -*- coding: utf-8 -*-
"""执行 migrations 目录下最近 N 天内修改过的 .py 迁移脚本。

用法:
  python scripts/run_recent_migrations.py
  python scripts/run_recent_migrations.py --days 2
  python scripts/run_recent_migrations.py --days 2 --yes
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run recent migration scripts")
    parser.add_argument("--days", type=int, default=2, help="回溯天数，默认 2")
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="跳过确认直接执行",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    mig_dir = root / "migrations"
    if not mig_dir.is_dir():
        print(f"[ERROR] migrations dir not found: {mig_dir}")
        return 1

    days = abs(int(args.days or 2))
    cutoff = datetime.now() - timedelta(days=days)
    files = sorted(
        (
            p
            for p in mig_dir.glob("*.py")
            if p.is_file() and datetime.fromtimestamp(p.stat().st_mtime) >= cutoff
        ),
        key=lambda p: p.stat().st_mtime,
    )

    print("========================================")
    print(f" Recent migrations/*.py within {days} day(s)")
    print(f" Cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" Workdir: {root}")
    print("========================================")
    print()

    if not files:
        print(f"[INFO] No migration scripts in the last {days} day(s).")
        return 0

    print("Will run in LastWriteTime order:")
    print("----------------------------------------")
    for p in files:
        mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{mtime}  {p.name}")
    print("----------------------------------------")
    print()

    if not args.yes:
        try:
            confirm = input("Run these scripts? (Y/N): ").strip()
        except EOFError:
            print("Cancelled (no interactive input). Use --yes for unattended run.")
            return 0
        if confirm.upper() != "Y":
            print("Cancelled.")
            return 0

    ok = 0
    fail = 0
    for p in files:
        print()
        print(f"-------- 执行: {p}")
        proc = subprocess.run([sys.executable, str(p)], cwd=str(root))
        if proc.returncode != 0:
            print(f"[FAIL] {p.name} (exit={proc.returncode})")
            fail += 1
        else:
            print(f"[OK] {p.name}")
            ok += 1

    print()
    print("========================================")
    print(f" Done: ok={ok} fail={fail}")
    print("========================================")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
