#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将历史 GMS 文件存储（backend_core/strategies/gms/backtest_data/）导入 gms_backtest_tasks。
任务 JSON 与 details 目录下 csv/xlsx 需同时存在（或至少任务 JSON）。
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend_api.database import SessionLocal  # noqa: E402
from backend_api.models import GMSBacktestTask  # noqa: E402


def _parse_dt(val):
    if not val:
        return None
    s = str(val).strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def main():
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "backend_core", "strategies", "gms", "backtest_data")
    )
    tasks_dir = os.path.join(base, "tasks")
    details_dir = os.path.join(base, "details")
    if not os.path.isdir(tasks_dir):
        print("无 tasks 目录，跳过:", tasks_dir)
        return

    db = SessionLocal()
    n = 0
    try:
        for fn in os.listdir(tasks_dir):
            if not fn.endswith(".json"):
                continue
            tid = fn[:-5]
            path = os.path.join(tasks_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception as e:
                print("跳过损坏文件", path, e)
                continue
            if not isinstance(raw, dict):
                continue
            exists = db.query(GMSBacktestTask).filter(GMSBacktestTask.task_id == tid).first()
            if exists:
                print("已存在，跳过", tid)
                continue

            csv_p = os.path.join(details_dir, f"{tid}.csv")
            xlsx_p = os.path.join(details_dir, f"{tid}.xlsx")
            csv_b = None
            xlsx_b = None
            if os.path.isfile(csv_p):
                with open(csv_p, "rb") as f:
                    csv_b = f.read()
            if os.path.isfile(xlsx_p):
                with open(xlsx_p, "rb") as f:
                    xlsx_b = f.read()

            row = GMSBacktestTask(
                task_id=tid,
                name=raw.get("name"),
                status=raw.get("status") or "pending",
                progress=int(raw.get("progress") or 0),
                message=raw.get("message"),
                config=raw.get("config") or {},
                logs=raw.get("logs") if isinstance(raw.get("logs"), list) else [],
                summary=raw.get("summary"),
                error=raw.get("error"),
                details_path=raw.get("details_path"),
                details_csv_bytes=csv_b,
                details_xlsx_bytes=xlsx_b,
                created_at=_parse_dt(raw.get("created_at")) or datetime.utcnow(),
                started_at=_parse_dt(raw.get("started_at")),
                completed_at=_parse_dt(raw.get("completed_at")),
            )
            db.add(row)
            n += 1
        db.commit()
        print(f"OK: 导入 {n} 条任务")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
