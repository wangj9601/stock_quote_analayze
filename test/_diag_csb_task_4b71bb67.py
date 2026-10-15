# -*- coding: utf-8 -*-
"""核对任务 4b71bb67 配置与摘要。"""
import json
from sqlalchemy import text
from backend_api.database import SessionLocal

db = SessionLocal()
row = db.execute(
    text(
        """
        SELECT task_id, name, status, progress, message, error,
               config, summary, created_at, started_at, completed_at
        FROM csb_backtest_tasks
        WHERE CAST(task_id AS text) LIKE :p
        ORDER BY created_at DESC NULLS LAST
        LIMIT 3
        """
    ),
    {"p": "4b71bb67%"},
).fetchone()
if not row:
    print("TASK_NOT_FOUND")
else:
    d = dict(row._mapping)
    cfg = d.get("config") or {}
    summary = d.get("summary") or {}
    if isinstance(cfg, str):
        cfg = json.loads(cfg)
    if isinstance(summary, str):
        summary = json.loads(summary)
    print("=== META ===")
    print(
        {
            "task_id": d["task_id"],
            "name": d["name"],
            "status": d["status"],
            "progress": d["progress"],
            "message": d["message"],
            "error": d["error"],
            "created_at": str(d["created_at"]),
            "completed_at": str(d["completed_at"]),
        }
    )
    print("=== CONFIG KEYS ===")
    keep = [
        "preset_id",
        "start_date",
        "end_date",
        "exit_mode",
        "target_pct",
        "target_pct_max",
        "horizon_days",
        "min_score",
        "use_trace",
        "strategy_config_id",
        "allowed_signal_types",
        "min_touch_count",
        "probe_min_score",
        "max_signals_per_day",
        "defense_overrides",
        "compare_hit_rate",
        "signal_quality_mode",
        "stock_pool_mode",
    ]
    print({k: cfg.get(k) for k in keep})
    print("=== SUMMARY ===")
    # print compact summary
    if isinstance(summary, dict):
        skip = {"details", "equity_curve", "daily"}
        compact = {k: v for k, v in summary.items() if k not in skip}
        print(json.dumps(compact, ensure_ascii=False, indent=2, default=str)[:8000])
    else:
        print(summary)

# signal type counts in details if stored
det = db.execute(
    text(
        """
        SELECT octet_length(details_csv_bytes) AS csv_bytes, details_path
        FROM csb_backtest_tasks
        WHERE CAST(task_id AS text) LIKE :p
        LIMIT 1
        """
    ),
    {"p": "4b71bb67%"},
).fetchone()
if det:
    print("=== DETAILS ===", dict(det._mapping))

db.close()
