"""日终：从 historical_quotes(_hk) 扫描「当日量 >= ratio * 前一日量」并写入 triple_volume_observe_stocks。"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_api.models import TripleVolumeObserveStock
from backend_core.strategies.triple_volume_observe.env_config import load_scan_env
from backend_core.strategies.volume_shrink_breakout.data_loader import (
    VSB_BOARD_PREFIX_GROUPS,
    normalize_vsb_board_keys,
)

logger = logging.getLogger(__name__)


def _board_filter_sql(table_alias: str = "h") -> str:
    cfg = load_scan_env()
    keys = normalize_vsb_board_keys(cfg.board_keys)
    if not keys:
        return ""
    parts: List[str] = []
    for k in keys:
        for p in VSB_BOARD_PREFIX_GROUPS.get(k, ()):
            parts.append(f"{table_alias}.code LIKE '{p}%%'")
    if not parts:
        return ""
    return " AND (" + " OR ".join(parts) + ")"


def _scan_cn(db: Session, ratio: float) -> Tuple[str, List[Dict[str, Any]]]:
    board_sql = _board_filter_sql("h")
    q = text(
        f"""
        WITH mx AS (SELECT MAX(historical_quotes.date)::date AS md FROM historical_quotes),
        ordered AS (
            SELECT h.code,
                   COALESCE(h.name, '') AS name,
                   h.date::date AS d,
                   CAST(h.volume AS DOUBLE PRECISION) AS vol,
                   LEAD(CAST(h.volume AS DOUBLE PRECISION)) OVER (
                       PARTITION BY h.code ORDER BY h.date DESC
                   ) AS prev_vol,
                   LEAD(h.date::date) OVER (
                       PARTITION BY h.code ORDER BY h.date DESC
                   ) AS prev_d
            FROM historical_quotes h
            WHERE EXISTS (
                SELECT 1 FROM stock_basic_info s
                WHERE s.code = h.code
                  AND s.name NOT LIKE '%ST%'
                  AND (s.collect_enabled IS TRUE OR s.collect_enabled IS NULL)
            )
            {board_sql}
        )
        SELECT o.code, o.name, o.d, o.vol, o.prev_vol, o.prev_d
        FROM ordered o, mx
        WHERE o.d = mx.md
          AND o.prev_vol IS NOT NULL AND o.prev_vol > 0
          AND o.vol >= :ratio * o.prev_vol
        """
    )
    rows = db.execute(q, {"ratio": ratio}).fetchall()
    hits: List[Dict[str, Any]] = []
    trade_date: Optional[str] = None
    for r in rows:
        d = r[2]
        ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        trade_date = trade_date or ds
        prev_d = r[5]
        prev_ds = prev_d.strftime("%Y-%m-%d") if hasattr(prev_d, "strftime") else str(prev_d)[:10] if prev_d else None
        hits.append(
            {
                "code": str(r[0]),
                "name": str(r[1] or ""),
                "observe_trade_date": ds,
                "prev_trade_date": prev_ds,
                "prev_volume": float(r[4]) if r[4] is not None else None,
                "curr_volume": float(r[3]) if r[3] is not None else None,
                "volume_ratio_actual": (float(r[3]) / float(r[4])) if r[4] else None,
            }
        )
    return trade_date or "", hits


def _scan_hk(db: Session, ratio: float) -> Tuple[str, List[Dict[str, Any]]]:
    board_sql = _board_filter_sql("h")
    q = text(
        f"""
        WITH mx AS (SELECT MAX(h.date::date) AS md FROM historical_quotes_hk h),
        ordered AS (
            SELECT h.code,
                   COALESCE(h.name, '') AS name,
                   h.date::date AS d,
                   CAST(h.volume AS DOUBLE PRECISION) AS vol,
                   LEAD(CAST(h.volume AS DOUBLE PRECISION)) OVER (
                       PARTITION BY h.code ORDER BY h.date::date DESC
                   ) AS prev_vol,
                   LEAD(h.date::date) OVER (
                       PARTITION BY h.code ORDER BY h.date::date DESC
                   ) AS prev_d
            FROM historical_quotes_hk h
            WHERE EXISTS (
                SELECT 1 FROM stock_basic_info_hk s
                WHERE s.code = h.code
                  AND s.name NOT LIKE '%ST%'
                  AND (s.collect_enabled IS TRUE OR s.collect_enabled IS NULL)
            )
            {board_sql}
        )
        SELECT o.code, o.name, o.d, o.vol, o.prev_vol, o.prev_d
        FROM ordered o, mx
        WHERE o.d = mx.md
          AND o.prev_vol IS NOT NULL AND o.prev_vol > 0
          AND o.vol >= :ratio * o.prev_vol
        """
    )
    rows = db.execute(q, {"ratio": ratio}).fetchall()
    hits: List[Dict[str, Any]] = []
    trade_date: Optional[str] = None
    for r in rows:
        d = r[2]
        ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
        trade_date = trade_date or ds
        prev_d = r[5]
        prev_ds = prev_d.strftime("%Y-%m-%d") if hasattr(prev_d, "strftime") else str(prev_d)[:10] if prev_d else None
        hits.append(
            {
                "code": str(r[0]),
                "name": str(r[1] or ""),
                "observe_trade_date": ds,
                "prev_trade_date": prev_ds,
                "prev_volume": float(r[4]) if r[4] is not None else None,
                "curr_volume": float(r[3]) if r[3] is not None else None,
                "volume_ratio_actual": (float(r[3]) / float(r[4])) if r[4] else None,
            }
        )
    return trade_date or "", hits


def run_triple_volume_scan(db: Session) -> Dict[str, Any]:
    """
    执行爆量扫描并写入 triple_volume_observe_stocks（初始状态 待观察）。
    幂等：同一 (market, code, observe_trade_date) 已存在则跳过插入。
    """
    cfg = load_scan_env()
    if not cfg.enabled:
        return {"skipped": True, "reason": "TRIPLE_VOLUME_OBSERVE_ENABLED=false"}

    inserted = 0
    out: Dict[str, Any] = {
        "skipped": False,
        "markets": cfg.markets,
        "volume_ratio": cfg.volume_ratio,
        "cn_trade_date": None,
        "hk_trade_date": None,
        "inserted_cn": 0,
        "inserted_hk": 0,
    }

    if "CN" in cfg.markets:
        cn_date, hits = _scan_cn(db, cfg.volume_ratio)
        out["cn_trade_date"] = cn_date or None
        for h in hits:
            row = TripleVolumeObserveStock(
                market="CN",
                code=h["code"],
                name=h["name"] or None,
                observe_trade_date=datetime.strptime(h["observe_trade_date"], "%Y-%m-%d").date(),
                prev_trade_date=datetime.strptime(h["prev_trade_date"], "%Y-%m-%d").date() if h.get("prev_trade_date") else None,
                prev_volume=h.get("prev_volume"),
                curr_volume=h.get("curr_volume"),
                volume_ratio_actual=h.get("volume_ratio_actual"),
                status="待观察",
            )
            exists = (
                db.query(TripleVolumeObserveStock)
                .filter(
                    TripleVolumeObserveStock.market == "CN",
                    TripleVolumeObserveStock.code == h["code"],
                    TripleVolumeObserveStock.observe_trade_date == row.observe_trade_date,
                )
                .first()
            )
            if exists:
                continue
            db.add(row)
            inserted += 1
            out["inserted_cn"] += 1

    if "HK" in cfg.markets:
        hk_date, hits = _scan_hk(db, cfg.volume_ratio)
        out["hk_trade_date"] = hk_date or None
        for h in hits:
            row = TripleVolumeObserveStock(
                market="HK",
                code=h["code"],
                name=h["name"] or None,
                observe_trade_date=datetime.strptime(h["observe_trade_date"], "%Y-%m-%d").date(),
                prev_trade_date=datetime.strptime(h["prev_trade_date"], "%Y-%m-%d").date() if h.get("prev_trade_date") else None,
                prev_volume=h.get("prev_volume"),
                curr_volume=h.get("curr_volume"),
                volume_ratio_actual=h.get("volume_ratio_actual"),
                status="待观察",
            )
            exists = (
                db.query(TripleVolumeObserveStock)
                .filter(
                    TripleVolumeObserveStock.market == "HK",
                    TripleVolumeObserveStock.code == h["code"],
                    TripleVolumeObserveStock.observe_trade_date == row.observe_trade_date,
                )
                .first()
            )
            if exists:
                continue
            db.add(row)
            inserted += 1
            out["inserted_hk"] += 1

    db.commit()
    out["inserted_total"] = inserted
    logger.info("triple_volume scan 完成: %s", out)
    return out
