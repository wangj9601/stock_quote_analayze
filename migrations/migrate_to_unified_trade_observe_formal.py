# -*- coding: utf-8 -*-
"""将旧策略交易观察 / 正式交易数据导入统一表（幂等）。

观察来源（5）：gms / urt / sbbr / rpe / triple_volume
正式交易（4）：gms / urt / sbbr / rpe

重复执行时按 (user_id, market, code, source) 跳过或更新，不产生重复 open。
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend_core.database.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _json_dump(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False, default=str)
    if isinstance(val, str):
        return val
    return json.dumps(val, ensure_ascii=False, default=str)


def _as_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()[:10]
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _as_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    return None


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :n
            LIMIT 1
            """
        ),
        {"n": name},
    ).fetchone()
    return row is not None


def _upsert_observe(conn, *, source: str, row: Dict[str, Any], extra: Optional[Dict] = None) -> str:
    """插入或跳过观察；返回 inserted|skipped。"""
    exists = conn.execute(
        text(
            """
            SELECT id FROM trade_observe_stocks
            WHERE user_id = :user_id AND market = :market AND code = :code AND source = :source
            LIMIT 1
            """
        ),
        {
            "user_id": row["user_id"],
            "market": row["market"] or "CN",
            "code": row["code"],
            "source": source,
        },
    ).fetchone()
    if exists:
        return "skipped"
    conn.execute(
        text(
            """
            INSERT INTO trade_observe_stocks (
                user_id, market, code, name, source, signal_date,
                signal_snapshot_json, extra_json, created_at, updated_at
            ) VALUES (
                :user_id, :market, :code, :name, :source, :signal_date,
                CAST(:signal_snapshot_json AS JSONB), CAST(:extra_json AS JSONB),
                COALESCE(:created_at, NOW()), COALESCE(:updated_at, NOW())
            )
            """
        ),
        {
            "user_id": row["user_id"],
            "market": row.get("market") or "CN",
            "code": row["code"],
            "name": row.get("name"),
            "source": source,
            "signal_date": _as_date(row.get("signal_date")),
            "signal_snapshot_json": _json_dump(row.get("signal_snapshot_json")),
            "extra_json": _json_dump(extra),
            "created_at": _as_dt(row.get("created_at")),
            "updated_at": _as_dt(row.get("updated_at")),
        },
    )
    return "inserted"


def _upsert_formal(conn, *, source: str, row: Dict[str, Any], extra: Optional[Dict] = None) -> str:
    """插入正式交易；同 user+market+code+source 已有 open 时跳过。"""
    status = (row.get("status") or "open").lower()
    if status == "open":
        exists_open = conn.execute(
            text(
                """
                SELECT id FROM formal_trades
                WHERE user_id = :user_id AND market = :market AND code = :code
                  AND source = :source AND status = 'open'
                LIMIT 1
                """
            ),
            {
                "user_id": row["user_id"],
                "market": row.get("market") or "CN",
                "code": row["code"],
                "source": source,
            },
        ).fetchone()
        if exists_open:
            return "skipped"

    # 用业务字段粗略去重（避免重复导入 closed）
    dup = conn.execute(
        text(
            """
            SELECT id FROM formal_trades
            WHERE user_id = :user_id AND market = :market AND code = :code
              AND source = :source AND status = :status
              AND entry_price = :entry_price
              AND COALESCE(entry_at, created_at) = COALESCE(:entry_at, :created_at)
            LIMIT 1
            """
        ),
        {
            "user_id": row["user_id"],
            "market": row.get("market") or "CN",
            "code": row["code"],
            "source": source,
            "status": status,
            "entry_price": float(row["entry_price"]),
            "entry_at": _as_dt(row.get("entry_at")),
            "created_at": _as_dt(row.get("created_at")),
        },
    ).fetchone()
    if dup:
        return "skipped"

    conn.execute(
        text(
            """
            INSERT INTO formal_trades (
                user_id, market, code, name, source, source_observe_id,
                entry_price, position_lots, exit_price, status, signal_date,
                signal_snapshot_json, notes, entry_at, exit_at,
                pnl_amount, pnl_percent, extra_json, created_at, updated_at
            ) VALUES (
                :user_id, :market, :code, :name, :source, :source_observe_id,
                :entry_price, :position_lots, :exit_price, :status, :signal_date,
                CAST(:signal_snapshot_json AS JSONB), :notes, COALESCE(:entry_at, NOW()), :exit_at,
                :pnl_amount, :pnl_percent, CAST(:extra_json AS JSONB),
                COALESCE(:created_at, NOW()), COALESCE(:updated_at, NOW())
            )
            """
        ),
        {
            "user_id": row["user_id"],
            "market": row.get("market") or "CN",
            "code": row["code"],
            "name": row.get("name"),
            "source": source,
            "source_observe_id": row.get("source_observe_id"),
            "entry_price": float(row["entry_price"]),
            "position_lots": int(row.get("position_lots") or 0),
            "exit_price": float(row["exit_price"]) if row.get("exit_price") is not None else None,
            "status": status,
            "signal_date": _as_date(row.get("signal_date")),
            "signal_snapshot_json": _json_dump(row.get("signal_snapshot_json")),
            "notes": row.get("notes"),
            "entry_at": _as_dt(row.get("entry_at")),
            "exit_at": _as_dt(row.get("exit_at")),
            "pnl_amount": row.get("pnl_amount"),
            "pnl_percent": row.get("pnl_percent"),
            "extra_json": _json_dump(extra),
            "created_at": _as_dt(row.get("created_at")),
            "updated_at": _as_dt(row.get("updated_at")),
        },
    )
    return "inserted"


def _migrate_observe_table(conn, table: str, source: str, extra_builder) -> Dict[str, int]:
    stats = {"inserted": 0, "skipped": 0}
    if not _table_exists(conn, table):
        logger.warning("跳过不存在的观察表: %s", table)
        return stats
    rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
    for r in rows:
        d = dict(r)
        # triple_volume 字段名不同
        if source == "triple_volume":
            if d.get("signal_date") is None:
                d["signal_date"] = d.get("observe_trade_date")
            if d.get("signal_snapshot_json") is None:
                d["signal_snapshot_json"] = d.get("observe_snapshot_json")
        extra = extra_builder(d) if extra_builder else None
        result = _upsert_observe(conn, source=source, row=d, extra=extra)
        stats[result] += 1
    logger.info("观察导入 %s → %s: %s", table, source, stats)
    return stats


def _migrate_formal_table(conn, table: str, source: str, extra_builder) -> Dict[str, int]:
    stats = {"inserted": 0, "skipped": 0}
    if not _table_exists(conn, table):
        logger.warning("跳过不存在的正式交易表: %s", table)
        return stats
    rows = conn.execute(text(f"SELECT * FROM {table}")).mappings().all()
    for r in rows:
        d = dict(r)
        # SBBR 无 position_lots，默认 0
        if d.get("position_lots") is None:
            d["position_lots"] = 0
        if d.get("entry_price") is None:
            logger.warning("跳过无 entry_price 的正式交易 %s id=%s", table, d.get("id"))
            stats["skipped"] += 1
            continue
        extra = extra_builder(d) if extra_builder else None
        result = _upsert_formal(conn, source=source, row=d, extra=extra)
        stats[result] += 1
    logger.info("正式交易导入 %s → %s: %s", table, source, stats)
    return stats


def upgrade():
    # 先确保统一表存在
    import importlib.util

    schema_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "add_unified_trade_observe_formal.py",
    )
    spec = importlib.util.spec_from_file_location(
        "add_unified_trade_observe_formal", schema_path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod.upgrade()

    with engine.connect() as conn:
        _migrate_observe_table(
            conn,
            "gms_trade_observe_stocks",
            "gms",
            lambda d: {
                "key_focus_flag": bool(d.get("key_focus_flag") or False),
                "latest_close_price": d.get("latest_close_price"),
                "latest_close_date": str(d["latest_close_date"])[:10]
                if d.get("latest_close_date")
                else None,
                "legacy_id": d.get("id"),
            },
        )
        _migrate_observe_table(
            conn,
            "urt_trade_observe_stocks",
            "urt",
            lambda d: {"config_id": d.get("config_id"), "legacy_id": d.get("id")},
        )
        _migrate_observe_table(
            conn,
            "sbbr_trade_observe_stocks",
            "sbbr",
            lambda d: {"legacy_id": d.get("id")},
        )
        _migrate_observe_table(
            conn,
            "rpe_trade_observe_stocks",
            "rpe",
            lambda d: {"legacy_id": d.get("id")},
        )
        _migrate_observe_table(
            conn,
            "triple_volume_trade_observe_stocks",
            "triple_volume",
            lambda d: {"legacy_id": d.get("id")},
        )

        _migrate_formal_table(
            conn,
            "gms_formal_trades",
            "gms",
            lambda d: {"legacy_id": d.get("id")},
        )
        _migrate_formal_table(
            conn,
            "urt_formal_trades",
            "urt",
            lambda d: {"legacy_id": d.get("id")},
        )
        _migrate_formal_table(
            conn,
            "sbbr_formal_trades",
            "sbbr",
            lambda d: {
                "legacy_id": d.get("id"),
                "stage": d.get("stage"),
                "budget_total": d.get("budget_total"),
                "allocated_pct": d.get("allocated_pct"),
                "defense_anchor_low": d.get("defense_anchor_low"),
                "defense_buffer_pct": d.get("defense_buffer_pct"),
                "exit_reason": d.get("exit_reason"),
                "last_eval_json": d.get("last_eval_json"),
            },
        )
        _migrate_formal_table(
            conn,
            "rpe_formal_trades",
            "rpe",
            lambda d: {
                "legacy_id": d.get("id"),
                "structure_support": d.get("structure_support"),
                "structure_resistance": d.get("structure_resistance"),
                "exit_reason": d.get("exit_reason"),
                "last_eval_json": d.get("last_eval_json"),
            },
        )
        conn.commit()
    logger.info("旧交易观察/正式交易数据导入统一表完成")


if __name__ == "__main__":
    upgrade()
