# -*- coding: utf-8 -*-
"""闸门相关表 ensure / upsert / load。"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)

_TABLES_READY = False

_DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS board_fund_flow_features (
        board_kind VARCHAR(16) NOT NULL,
        board_code_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
        board_code VARCHAR(32) NOT NULL,
        trade_date DATE NOT NULL,
        inflow_streak INTEGER,
        outflow_streak INTEGER,
        pos_days_5 INTEGER,
        pos_days_20 INTEGER,
        net_sum_5 DOUBLE PRECISION,
        net_sum_20 DOUBLE PRECISION,
        day_net DOUBLE PRECISION,
        fund_stage VARCHAR(16),
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (board_kind, board_code_source, board_code, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS board_rs_ratings (
        board_kind VARCHAR(16) NOT NULL,
        board_code VARCHAR(32) NOT NULL,
        trade_date DATE NOT NULL,
        rs_raw DOUBLE PRECISION,
        rs_rating INTEGER,
        rs_observe INTEGER,
        rs_source VARCHAR(32),
        universe VARCHAR(32),
        member_rs_median DOUBLE PRECISION,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (board_kind, board_code, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS board_valuation_daily (
        board_kind VARCHAR(16) NOT NULL,
        board_code VARCHAR(32) NOT NULL,
        trade_date DATE NOT NULL,
        board_pe_median DOUBLE PRECISION,
        board_pb_median DOUBLE PRECISION,
        board_roe_median DOUBLE PRECISION,
        pe_pct DOUBLE PRECISION,
        pb_pct DOUBLE PRECISION,
        coverage_ratio DOUBLE PRECISION,
        valuation_unknown BOOLEAN NOT NULL DEFAULT TRUE,
        member_count INTEGER,
        valid_pe_count INTEGER,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (board_kind, board_code, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS board_gate_daily (
        board_kind VARCHAR(16) NOT NULL,
        board_code_source VARCHAR(32) NOT NULL DEFAULT 'tonghuashun',
        board_code VARCHAR(32) NOT NULL,
        trade_date DATE NOT NULL,
        board_name VARCHAR(100),
        trade_observe_flag BOOLEAN NOT NULL DEFAULT FALSE,
        short_raw VARCHAR(16),
        short_state VARCHAR(16),
        short_confirm_count INTEGER,
        midlong_raw VARCHAR(16),
        midlong_state VARCHAR(16),
        midlong_confirm_count INTEGER,
        conflict_action VARCHAR(32),
        evidence_json JSONB,
        degraded_json JSONB,
        shadow_hard_filter_hint VARCHAR(64),
        v2_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (board_kind, board_code_source, board_code, trade_date)
    )
    """,
]


def _as_date_str(v: Any) -> str:
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v or "")[:10]


def ensure_board_gate_tables(db) -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    try:
        for ddl in _DDL_STATEMENTS:
            db.execute(text(ddl))
        try:
            db.commit()
        except Exception:
            pass
        _TABLES_READY = True
    except Exception as e:
        logger.error("ensure_board_gate_tables failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


def upsert_fund_features(db, rows: Sequence[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = text(
        """
        INSERT INTO board_fund_flow_features (
            board_kind, board_code_source, board_code, trade_date,
            inflow_streak, outflow_streak, pos_days_5, pos_days_20,
            net_sum_5, net_sum_20, day_net, fund_stage, updated_at
        ) VALUES (
            :board_kind, :board_code_source, :board_code, CAST(:trade_date AS date),
            :inflow_streak, :outflow_streak, :pos_days_5, :pos_days_20,
            :net_sum_5, :net_sum_20, :day_net, :fund_stage, NOW()
        )
        ON CONFLICT (board_kind, board_code_source, board_code, trade_date)
        DO UPDATE SET
            inflow_streak = EXCLUDED.inflow_streak,
            outflow_streak = EXCLUDED.outflow_streak,
            pos_days_5 = EXCLUDED.pos_days_5,
            pos_days_20 = EXCLUDED.pos_days_20,
            net_sum_5 = EXCLUDED.net_sum_5,
            net_sum_20 = EXCLUDED.net_sum_20,
            day_net = EXCLUDED.day_net,
            fund_stage = EXCLUDED.fund_stage,
            updated_at = NOW()
        """
    )
    for r in rows:
        db.execute(sql, r)
    return len(rows)


def upsert_board_rs_ratings(db, rows: Sequence[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = text(
        """
        INSERT INTO board_rs_ratings (
            board_kind, board_code, trade_date,
            rs_raw, rs_rating, rs_observe, rs_source, universe,
            member_rs_median, updated_at
        ) VALUES (
            :board_kind, :board_code, CAST(:trade_date AS date),
            :rs_raw, :rs_rating, :rs_observe, :rs_source, :universe,
            :member_rs_median, NOW()
        )
        ON CONFLICT (board_kind, board_code, trade_date)
        DO UPDATE SET
            rs_raw = EXCLUDED.rs_raw,
            rs_rating = EXCLUDED.rs_rating,
            rs_observe = EXCLUDED.rs_observe,
            rs_source = EXCLUDED.rs_source,
            universe = EXCLUDED.universe,
            member_rs_median = EXCLUDED.member_rs_median,
            updated_at = NOW()
        """
    )
    for r in rows:
        db.execute(sql, r)
    return len(rows)


def upsert_board_valuation(db, rows: Sequence[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = text(
        """
        INSERT INTO board_valuation_daily (
            board_kind, board_code, trade_date,
            board_pe_median, board_pb_median, board_roe_median,
            pe_pct, pb_pct, coverage_ratio, valuation_unknown,
            member_count, valid_pe_count, updated_at
        ) VALUES (
            :board_kind, :board_code, CAST(:trade_date AS date),
            :board_pe_median, :board_pb_median, :board_roe_median,
            :pe_pct, :pb_pct, :coverage_ratio, :valuation_unknown,
            :member_count, :valid_pe_count, NOW()
        )
        ON CONFLICT (board_kind, board_code, trade_date)
        DO UPDATE SET
            board_pe_median = EXCLUDED.board_pe_median,
            board_pb_median = EXCLUDED.board_pb_median,
            board_roe_median = EXCLUDED.board_roe_median,
            pe_pct = EXCLUDED.pe_pct,
            pb_pct = EXCLUDED.pb_pct,
            coverage_ratio = EXCLUDED.coverage_ratio,
            valuation_unknown = EXCLUDED.valuation_unknown,
            member_count = EXCLUDED.member_count,
            valid_pe_count = EXCLUDED.valid_pe_count,
            updated_at = NOW()
        """
    )
    for r in rows:
        db.execute(sql, r)
    return len(rows)


def upsert_board_gates(db, rows: Sequence[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = text(
        """
        INSERT INTO board_gate_daily (
            board_kind, board_code_source, board_code, trade_date,
            board_name, trade_observe_flag,
            short_raw, short_state, short_confirm_count,
            midlong_raw, midlong_state, midlong_confirm_count,
            conflict_action, evidence_json, degraded_json,
            shadow_hard_filter_hint, v2_enabled, updated_at
        ) VALUES (
            :board_kind, :board_code_source, :board_code, CAST(:trade_date AS date),
            :board_name, :trade_observe_flag,
            :short_raw, :short_state, :short_confirm_count,
            :midlong_raw, :midlong_state, :midlong_confirm_count,
            :conflict_action, CAST(:evidence_json AS jsonb), CAST(:degraded_json AS jsonb),
            :shadow_hard_filter_hint, :v2_enabled, NOW()
        )
        ON CONFLICT (board_kind, board_code_source, board_code, trade_date)
        DO UPDATE SET
            board_name = EXCLUDED.board_name,
            trade_observe_flag = EXCLUDED.trade_observe_flag,
            short_raw = EXCLUDED.short_raw,
            short_state = EXCLUDED.short_state,
            short_confirm_count = EXCLUDED.short_confirm_count,
            midlong_raw = EXCLUDED.midlong_raw,
            midlong_state = EXCLUDED.midlong_state,
            midlong_confirm_count = EXCLUDED.midlong_confirm_count,
            conflict_action = EXCLUDED.conflict_action,
            evidence_json = EXCLUDED.evidence_json,
            degraded_json = EXCLUDED.degraded_json,
            shadow_hard_filter_hint = EXCLUDED.shadow_hard_filter_hint,
            v2_enabled = EXCLUDED.v2_enabled,
            updated_at = NOW()
        """
    )
    for r in rows:
        payload = dict(r)
        for k in ("evidence_json", "degraded_json"):
            v = payload.get(k)
            if isinstance(v, (dict, list)):
                payload[k] = json.dumps(v, ensure_ascii=False)
            elif v is None:
                payload[k] = "{}"
        db.execute(sql, payload)
    return len(rows)


def load_gate_raw_history(
    db,
    *,
    board_kind: str,
    board_code: str,
    board_code_source: str,
    before_date: str,
    limit: int,
    field: str = "short_raw",
) -> List[str]:
    col = "short_raw" if field == "short_raw" else "midlong_raw"
    rows = db.execute(
        text(
            f"""
            SELECT {col} AS raw_v
            FROM board_gate_daily
            WHERE board_kind = :kind
              AND board_code_source = :src
              AND board_code = :code
              AND trade_date < CAST(:td AS date)
              AND {col} IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT :lim
            """
        ),
        {
            "kind": board_kind,
            "src": board_code_source,
            "code": board_code,
            "td": before_date[:10],
            "lim": int(limit),
        },
    ).fetchall()
    return [str(r[0]) for r in reversed(rows) if r and r[0]]


def load_board_gates_for_date(
    db,
    trade_date: str,
    *,
    board_kind: Optional[str] = None,
    board_codes: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    params: Dict[str, Any] = {"td": trade_date[:10]}
    clauses = ["trade_date = CAST(:td AS date)"]
    if board_kind:
        clauses.append("board_kind = :kind")
        params["kind"] = board_kind
    sql = f"SELECT * FROM board_gate_daily WHERE {' AND '.join(clauses)}"
    if board_codes is not None:
        codes = [str(c).strip() for c in board_codes if c]
        if not codes:
            return {}
        q = text(sql + " AND board_code IN :codes").bindparams(
            bindparam("codes", expanding=True)
        )
        params["codes"] = codes
        rows = db.execute(q, params).mappings().all()
    else:
        rows = db.execute(text(sql), params).mappings().all()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        code = str(d.get("board_code") or "").strip()
        if code:
            out[code] = d
    return out


def resolve_asof_trade_date(db, trade_date: Optional[str] = None) -> str:
    if trade_date:
        return str(trade_date)[:10]
    try:
        row = db.execute(
            text("SELECT MAX(trade_date) FROM board_fund_flow_daily")
        ).fetchone()
        if row and row[0]:
            return _as_date_str(row[0])
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return date.today().strftime("%Y-%m-%d")
