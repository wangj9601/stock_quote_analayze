"""GMS 筛选结果快照：相同 date+scope+config+参数 的结果集复用。"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 与 gms_selection_snapshots.scope_key 列长度对齐（迁移可扩至 256）
SCOPE_KEY_MAX_LEN = 120


def _append_cn_segment(base: str, cn_board_segment: Optional[str]) -> str:
    if not cn_board_segment:
        return base
    seg = (cn_board_segment or "").strip().upper()
    if seg and seg != "ALL":
        return f"{base}:{seg}"
    return base


def _board_codes_scope_part(
    prefix: str,
    codes: List[str],
    *,
    cn_board_segment: Optional[str] = None,
    max_len: int = SCOPE_KEY_MAX_LEN,
) -> str:
    """行业/概念板块 scope 片段；板块过多时用哈希避免超出 VARCHAR 上限。"""
    normalized = sorted({c.strip().upper() for c in codes if c and str(c).strip()})
    if not normalized:
        return _append_cn_segment(prefix, cn_board_segment)
    if len(normalized) == 1:
        return _append_cn_segment(f"{prefix}:{normalized[0]}", cn_board_segment)
    joined = ",".join(normalized)
    plain = _append_cn_segment(f"{prefix}:{joined}", cn_board_segment)
    if len(plain) <= max_len:
        return plain
    digest = hashlib.md5(joined.encode("utf-8")).hexdigest()[:16]
    return _append_cn_segment(f"{prefix}:h:{digest}", cn_board_segment)


def build_scope_key(
    scope: str,
    *,
    cn_board_segment: Optional[str] = None,
    industry_board_codes: Optional[List[str]] = None,
    concept_board_codes: Optional[List[str]] = None,
    gms_watchlist_market: Optional[str] = None,
) -> str:
    scope = (scope or "cn").strip().lower()
    if scope == "cn" and cn_board_segment:
        seg = (cn_board_segment or "").strip().upper()
        if seg and seg != "ALL":
            return f"cn:{seg}"
    if scope == "industry_board" and industry_board_codes:
        return _board_codes_scope_part(
            "industry",
            industry_board_codes,
            cn_board_segment=cn_board_segment,
        )
    if scope == "concept_board" and concept_board_codes:
        return _board_codes_scope_part(
            "concept",
            concept_board_codes,
            cn_board_segment=cn_board_segment,
        )
    if scope == "gms_watchlist":
        parts = ["gms_watchlist"]
        if gms_watchlist_market:
            m = gms_watchlist_market.strip().lower()
            if m and m != "all":
                parts.append(m)
        if cn_board_segment:
            seg = (cn_board_segment or "").strip().upper()
            if seg and seg != "ALL":
                parts.append(seg)
        return ":".join(parts)
    return scope


def build_param_hash(params: Dict[str, Any]) -> str:
    keys = sorted(params.keys())
    payload = {k: params[k] for k in keys if params.get(k) is not None}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def load_snapshot(
    db: Session,
    trade_date: str,
    config_id: int,
    scope_key: str,
    param_hash: str,
) -> Optional[List[Dict[str, Any]]]:
    try:
        row = db.execute(
            text(
                """
                SELECT result_json FROM gms_selection_snapshots
                WHERE trade_date = :d AND config_id = :cid
                  AND scope_key = :sk AND param_hash = :ph
                """
            ),
            {"d": trade_date, "cid": config_id, "sk": scope_key, "ph": param_hash},
        ).scalar()
        if row is None:
            return None
        if isinstance(row, list):
            return row
        if isinstance(row, str):
            return json.loads(row)
        return list(row) if row else None
    except Exception as e:
        logger.warning("读取 gms_selection_snapshots 失败: %s", e)
        return None


def save_snapshot(
    db: Session,
    trade_date: str,
    config_id: int,
    scope_key: str,
    param_hash: str,
    results: List[Dict[str, Any]],
) -> None:
    if not results:
        return
    try:
        slim = []
        for r in results:
            slim.append(
                {
                    k: r.get(k)
                    for k in (
                        "code",
                        "symbol",
                        "date",
                        "market_type",
                        "score_total",
                        "buy_type",
                        "signal_strength",
                        "left_buy_signal",
                        "right_buy_signal",
                        "sell_signal",
                        "risk_tags",
                        "score_detail",
                    )
                    if r.get(k) is not None
                }
            )
        db.execute(
            text(
                """
                INSERT INTO gms_selection_snapshots
                (trade_date, config_id, scope_key, param_hash, result_json, row_count)
                VALUES (:d, :cid, :sk, :ph, CAST(:rj AS JSONB), :cnt)
                ON CONFLICT (trade_date, config_id, scope_key, param_hash)
                DO UPDATE SET result_json = EXCLUDED.result_json,
                              row_count = EXCLUDED.row_count,
                              created_at = NOW()
                """
            ),
            {
                "d": trade_date,
                "cid": config_id,
                "sk": scope_key,
                "ph": param_hash,
                "rj": json.dumps(slim, ensure_ascii=False, default=str),
                "cnt": len(slim),
            },
        )
        db.commit()
    except Exception as e:
        logger.warning("写入 gms_selection_snapshots 失败: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


def enrich_trace_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """补充 trace 命中率与 cache_layer 提示。"""
    req = int(meta.get("requested_count") or 0)
    hit = int(meta.get("from_trace_count") or 0)
    meta["trace_hit_rate"] = round(hit / req, 4) if req > 0 else 1.0
    if meta.get("cache_layer"):
        return meta
    if meta.get("from_snapshot"):
        meta["cache_layer"] = "snapshot"
    elif req > 0 and hit >= req:
        meta["cache_layer"] = "trace"
    elif hit > 0 and int(meta.get("computed_count") or 0) > 0:
        meta["cache_layer"] = "mixed"
    elif int(meta.get("computed_count") or 0) > 0:
        meta["cache_layer"] = "computed"
    else:
        meta["cache_layer"] = "trace" if hit > 0 else "computed"
    return meta
