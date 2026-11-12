# -*- coding: utf-8 -*-
"""观察池候选表 ensure / upsert；行业板 observe_lock 列。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from backend_core.board_observe.config import (
    DEFAULT_BOARD_CODE_SOURCE,
    LOCK_FOLLOW,
    SOURCE_MANUAL,
)

logger = logging.getLogger(__name__)

_READY = False


def ensure_board_observe_tables(db) -> None:
    global _READY
    if _READY:
        return
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS board_observe_candidate_daily (
            board_code VARCHAR(32) NOT NULL,
            board_code_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
            trade_date DATE NOT NULL,
            board_name VARCHAR(100),
            trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE,
            observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow',
            action VARCHAR(16) NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            sticky_count INTEGER NOT NULL DEFAULT 0,
            adoptable BOOLEAN NOT NULL DEFAULT FALSE,
            rank_in INTEGER,
            evidence_json JSONB,
            veto_json JSONB,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            PRIMARY KEY (board_code, board_code_source, trade_date)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_board_observe_candidate_date_action
        ON board_observe_candidate_daily (trade_date DESC, action)
        """,
        """
        ALTER TABLE industry_board_basic_info
        ADD COLUMN IF NOT EXISTS observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow'
        """,
        """
        ALTER TABLE industry_board_basic_info
        ADD COLUMN IF NOT EXISTS observe_source VARCHAR(32) NOT NULL DEFAULT 'manual'
        """,
        """
        ALTER TABLE industry_board_basic_info
        ADD COLUMN IF NOT EXISTS observe_updated_at TIMESTAMP WITHOUT TIME ZONE
        """,
        """
        ALTER TABLE industry_board_basic_info
        ADD COLUMN IF NOT EXISTS observe_updated_by VARCHAR(64)
        """,
        # 概念/指数列表 SQL 共用 select 列，一并加列（候选逻辑仅用行业）
        """
        ALTER TABLE concept_board_basic_info
        ADD COLUMN IF NOT EXISTS observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow'
        """,
        """
        ALTER TABLE index_board_basic_info
        ADD COLUMN IF NOT EXISTS observe_lock VARCHAR(16) NOT NULL DEFAULT 'follow'
        """,
    ]
    for sql in stmts:
        try:
            db.execute(text(sql))
            db.commit()
        except Exception as e:
            logger.warning("ensure_board_observe_tables: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
    _READY = True


def upsert_observe_candidates(db, rows: Sequence[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    ensure_board_observe_tables(db)
    sql = text(
        """
        INSERT INTO board_observe_candidate_daily (
            board_code, board_code_source, trade_date, board_name,
            trade_observe_flag, observe_lock, action, score,
            sticky_count, adoptable, rank_in, evidence_json, veto_json, updated_at
        ) VALUES (
            :board_code, :board_code_source, CAST(:trade_date AS date), :board_name,
            :trade_observe_flag, :observe_lock, :action, :score,
            :sticky_count, :adoptable, :rank_in,
            CAST(:evidence_json AS jsonb), CAST(:veto_json AS jsonb), NOW()
        )
        ON CONFLICT (board_code, board_code_source, trade_date) DO UPDATE SET
            board_name = EXCLUDED.board_name,
            trade_observe_flag = EXCLUDED.trade_observe_flag,
            observe_lock = EXCLUDED.observe_lock,
            action = EXCLUDED.action,
            score = EXCLUDED.score,
            sticky_count = EXCLUDED.sticky_count,
            adoptable = EXCLUDED.adoptable,
            rank_in = EXCLUDED.rank_in,
            evidence_json = EXCLUDED.evidence_json,
            veto_json = EXCLUDED.veto_json,
            updated_at = NOW()
        """
    )
    n = 0
    for r in rows:
        db.execute(
            sql,
            {
                "board_code": r["board_code"],
                "board_code_source": r.get("board_code_source")
                or DEFAULT_BOARD_CODE_SOURCE,
                "trade_date": str(r["trade_date"])[:10],
                "board_name": r.get("board_name"),
                "trade_observe_flag": bool(r.get("trade_observe_flag")),
                "observe_lock": r.get("observe_lock") or LOCK_FOLLOW,
                "action": r["action"],
                "score": int(r.get("score") or 0),
                "sticky_count": int(r.get("sticky_count") or 0),
                "adoptable": bool(r.get("adoptable")),
                "rank_in": r.get("rank_in"),
                "evidence_json": json.dumps(r.get("evidence_json") or {}, ensure_ascii=False),
                "veto_json": json.dumps(r.get("veto_json") or [], ensure_ascii=False),
            },
        )
        n += 1
    db.commit()
    return n


def load_prior_eligibility(
    db,
    *,
    trade_date: str,
    field: str,
    limit_days: int,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[str, List[bool]]:
    """加载 asof 之前最近 limit_days 日的 in_eligible / out_eligible（evidence 内布尔）。"""
    ensure_board_observe_tables(db)
    key = "in_eligible" if field == "in" else "out_eligible"
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, trade_date, evidence_json
                FROM board_observe_candidate_daily
                WHERE board_code_source = :src
                  AND trade_date < CAST(:td AS date)
                  AND trade_date >= CAST(:td AS date) - (:lim * INTERVAL '1 day')
                ORDER BY board_code, trade_date DESC
                """
            ),
            {"src": board_code_source, "td": trade_date[:10], "lim": int(limit_days) + 5},
        ).mappings().all()
    except Exception as e:
        logger.warning("load_prior_eligibility failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}

    by_code: Dict[str, List[bool]] = {}
    for r in rows:
        code = str(r["board_code"] or "").strip()
        if not code:
            continue
        bucket = by_code.setdefault(code, [])
        if len(bucket) >= limit_days:
            continue
        ev = r.get("evidence_json") or {}
        if isinstance(ev, str):
            try:
                ev = json.loads(ev)
            except Exception:
                ev = {}
        bucket.append(bool((ev or {}).get(key)))
    return by_code


def apply_observe_flag(
    db,
    *,
    board_code: str,
    trade_observe_flag: bool,
    observe_source: str = SOURCE_MANUAL,
    updated_by: Optional[str] = None,
    board_code_source: str = DEFAULT_BOARD_CODE_SOURCE,
) -> Dict[str, Any]:
    ensure_board_observe_tables(db)
    code = str(board_code or "").strip()
    row = db.execute(
        text(
            """
            SELECT board_name,
                   COALESCE(trade_observe_flag, FALSE) AS trade_observe_flag,
                   COALESCE(observe_lock, 'follow') AS observe_lock
            FROM industry_board_basic_info
            WHERE board_code = :c
              AND COALESCE(board_code_source, :src) = :src
            LIMIT 1
            """
        ),
        {"c": code, "src": board_code_source},
    ).mappings().first()
    if not row:
        return {"ok": False, "reason": "not_found", "board_code": code}
    lock = str(row["observe_lock"] or LOCK_FOLLOW).strip().lower() or LOCK_FOLLOW
    if lock == "exclude" and trade_observe_flag:
        return {"ok": False, "reason": "locked_exclude", "board_code": code, "observe_lock": lock}
    if lock == "include" and not trade_observe_flag:
        return {"ok": False, "reason": "locked_include", "board_code": code, "observe_lock": lock}
    params = {
        "f": bool(trade_observe_flag),
        "src_obs": observe_source,
        "by": (updated_by or "")[:64] or None,
        "c": code,
        "src": board_code_source,
    }
    db.execute(
        text(
            """
            UPDATE industry_board_basic_info
            SET trade_observe_flag = :f,
                observe_source = :src_obs,
                observe_updated_at = NOW(),
                observe_updated_by = :by
            WHERE board_code = :c
              AND COALESCE(board_code_source, :src) = :src
            """
        ),
        params,
    )
    # 同名其它来源一并同步，避免东财观察池与同花顺闸门宇宙脱节
    name = row.get("board_name")
    synced = 0
    if name:
        synced = db.execute(
            text(
                """
                UPDATE industry_board_basic_info
                SET trade_observe_flag = :f,
                    observe_source = :src_obs,
                    observe_updated_at = NOW(),
                    observe_updated_by = :by
                WHERE board_name = :name
                  AND board_code <> :c
                """
            ),
            {
                "f": bool(trade_observe_flag),
                "src_obs": observe_source,
                "by": params["by"],
                "name": name,
                "c": code,
            },
        ).rowcount or 0
    return {
        "ok": True,
        "board_code": code,
        "board_name": row.get("board_name"),
        "trade_observe_flag": bool(trade_observe_flag),
        "observe_lock": lock,
        "observe_source": observe_source,
        "synced_aliases": int(synced),
    }
