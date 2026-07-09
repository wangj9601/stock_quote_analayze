#!/usr/bin/env python3
"""执行数据库中 pending 状态的 GMS 回测任务（同步），并可导出 xlsx。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main() -> int:
    parser = argparse.ArgumentParser(description="同步执行 pending GMS 回测")
    parser.add_argument("--prefix", default="P0对比", help="仅处理任务名包含该前缀的 pending 任务")
    parser.add_argument("--export-dir", default="reports", help="完成后导出 xlsx 目录")
    parser.add_argument("--limit", type=int, default=20, help="最多处理条数")
    args = parser.parse_args()

    from backend_core.strategies.gms import admin_interface, backtest_storage, backtest_worker

    tasks = backtest_storage.list_tasks(status="pending", limit=args.limit)
    if args.prefix:
        tasks = [t for t in tasks if args.prefix in (t.get("name") or "")]
    if not tasks:
        print("没有匹配的 pending 任务")
        return 0

    export_dir = Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    for t in tasks:
        tid = t.get("task_id")
        name = t.get("name") or tid
        print(f"[执行] {name} ({tid})")
        backtest_worker._run_task(tid)
        row = admin_interface.get_task(tid) or {}
        print(f"  -> status={row.get('status')}, progress={row.get('progress')}")
        if row.get("status") == "completed":
            payload = admin_interface.download_report(tid, variant="xlsx")
            if payload:
                data, filename, _ = payload
                out = export_dir / filename
                out.write_bytes(data)
                print(f"  -> 已导出 {out}")
        elif row.get("error"):
            print(f"  -> error: {row.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
