"""从四策略 signal_trace 采集当日买点候选。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend_api.models import (
    GMSSignalTrace,
    GMSStrategyConfig,
    RPESignalTrace,
    RPEStrategyConfig,
    SBBRSignalTrace,
    SBBRStrategyConfig,
    URTSignalTrace,
    URTStrategyConfig,
)

logger = logging.getLogger(__name__)


def _as_date_str(v: Any) -> str:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v.isoformat()
    s = str(v or "").strip()[:10]
    return s


def _default_config_id(db: Session, model) -> Optional[int]:
    row = (
        db.query(model)
        .filter(model.is_default.is_(True))
        .order_by(model.id.asc())
        .first()
    )
    if row is not None:
        return int(row.id)
    row = (
        db.query(model)
        .filter(getattr(model, "precompute_enabled", model.is_default).is_(True))
        .order_by(model.id.asc())
        .first()
    )
    if row is not None:
        return int(row.id)
    row = db.query(model).order_by(model.id.asc()).first()
    return int(row.id) if row is not None else None


def _norm_code(code: Any) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def _row_to_dict_gms(r: GMSSignalTrace) -> Dict[str, Any]:
    return {
        "code": _norm_code(r.code),
        "strategy": "gms",
        "date": _as_date_str(r.date),
        "name": None,
        "score": float(r.score_total) if r.score_total is not None else None,
        "left_buy_signal": bool(r.left_buy_signal),
        "right_buy_signal": bool(r.right_buy_signal),
        "buy_type": r.buy_type,
        "sell_signal": bool(r.sell_signal) if r.sell_signal is not None else False,
        "score_detail": r.score_detail if isinstance(r.score_detail, dict) else {},
        "risk_tags": r.risk_tags,
        "config_id": int(r.config_id) if r.config_id is not None else None,
    }


def _row_to_dict_urt(r: URTSignalTrace) -> Dict[str, Any]:
    return {
        "code": _norm_code(r.code),
        "strategy": "urt",
        "date": _as_date_str(r.date),
        "name": r.name,
        "score": float(r.score) if r.score is not None else None,
        "buy_signal": bool(r.buy_signal),
        "close": float(r.close) if r.close is not None else None,
        "ma20": float(r.ma20) if r.ma20 is not None else None,
        "score_detail": r.score_detail if isinstance(r.score_detail, dict) else {},
        "config_id": int(r.config_id) if r.config_id is not None else None,
    }


def _row_to_dict_sbbr(r: SBBRSignalTrace) -> Dict[str, Any]:
    return {
        "code": _norm_code(r.code),
        "strategy": "sbbr",
        "date": _as_date_str(r.trade_date),
        "name": r.name,
        "score": None,
        "entry_signal": bool(r.entry_signal),
        "close": float(r.close_price) if r.close_price is not None else None,
        "close_price": float(r.close_price) if r.close_price is not None else None,
        "ma20": float(r.ma20) if r.ma20 is not None else None,
        "entry_low": float(r.entry_low) if r.entry_low is not None else None,
        "defense_low": float(r.defense_low) if r.defense_low is not None else None,
        "defense_high": float(r.defense_high) if r.defense_high is not None else None,
        "position_advice": r.position_advice if isinstance(r.position_advice, dict) else {},
        "detail": r.detail if isinstance(r.detail, dict) else {},
        "config_id": int(r.config_id) if r.config_id is not None else None,
    }


def _row_to_dict_rpe(r: RPESignalTrace) -> Dict[str, Any]:
    return {
        "code": _norm_code(r.code),
        "strategy": "rpe",
        "date": _as_date_str(r.trade_date),
        "name": r.name,
        "score": float(r.z_score) if r.z_score is not None else None,
        "entry_signal": bool(r.entry_signal),
        "signal_type": r.signal_type,
        "trend_veto": bool(r.trend_veto) if r.trend_veto is not None else False,
        "watch_only": bool(r.watch_only) if r.watch_only is not None else False,
        "close": float(r.close_price) if r.close_price is not None else None,
        "close_price": float(r.close_price) if r.close_price is not None else None,
        "sector_id": r.sector_id,
        "sector_name": r.sector_name,
        "sector_slope": float(r.sector_slope) if r.sector_slope is not None else None,
        "nearest_support": float(r.nearest_support) if r.nearest_support is not None else None,
        "nearest_resistance": float(r.nearest_resistance)
        if r.nearest_resistance is not None
        else None,
        "support_levels": r.support_levels,
        "resistance_levels": r.resistance_levels,
        "detail": r.detail if isinstance(r.detail, dict) else {},
        "config_id": int(r.config_id) if r.config_id is not None else None,
    }


def collect_strategy_buy_candidates(
    db: Session,
    asof_date: str,
    *,
    gms_config_id: Optional[int] = None,
    urt_config_id: Optional[int] = None,
    sbbr_config_id: Optional[int] = None,
    rpe_config_id: Optional[int] = None,
    limit_per_strategy: int = 500,
) -> Dict[str, List[Dict[str, Any]]]:
    """返回 {strategy: [row_dict, ...]}，仅含买点/入场信号。"""
    d = _as_date_str(asof_date)
    out: Dict[str, List[Dict[str, Any]]] = {
        "urt": [],
        "gms": [],
        "sbbr": [],
        "rpe": [],
    }

    gms_cid = gms_config_id or _default_config_id(db, GMSStrategyConfig)
    urt_cid = urt_config_id or _default_config_id(db, URTStrategyConfig)
    sbbr_cid = sbbr_config_id or _default_config_id(db, SBBRStrategyConfig)
    rpe_cid = rpe_config_id or _default_config_id(db, RPEStrategyConfig)

    if urt_cid is not None:
        try:
            from backend_core.strategies.urt.trace_store import URT_TRACE_SCANNED_MARKER

            marker = URT_TRACE_SCANNED_MARKER
        except Exception:
            marker = "__URT_SCANNED__"
        rows = (
            db.query(URTSignalTrace)
            .filter(
                URTSignalTrace.date == d,
                URTSignalTrace.config_id == int(urt_cid),
                URTSignalTrace.buy_signal.is_(True),
                URTSignalTrace.code != marker,
            )
            .order_by(URTSignalTrace.score.desc().nullslast())
            .limit(limit_per_strategy)
            .all()
        )
        out["urt"] = [_row_to_dict_urt(r) for r in rows]

    if gms_cid is not None:
        rows = (
            db.query(GMSSignalTrace)
            .filter(
                GMSSignalTrace.date == d,
                GMSSignalTrace.config_id == int(gms_cid),
                GMSSignalTrace.market_type == "CN",
                or_(
                    GMSSignalTrace.left_buy_signal.is_(True),
                    GMSSignalTrace.right_buy_signal.is_(True),
                ),
            )
            .order_by(GMSSignalTrace.score_total.desc().nullslast())
            .limit(limit_per_strategy)
            .all()
        )
        out["gms"] = [_row_to_dict_gms(r) for r in rows]

    if sbbr_cid is not None:
        try:
            from datetime import date as _date

            td = _date.fromisoformat(d)
        except ValueError:
            td = None
        if td is not None:
            rows = (
                db.query(SBBRSignalTrace)
                .filter(
                    SBBRSignalTrace.trade_date == td,
                    SBBRSignalTrace.config_id == int(sbbr_cid),
                    SBBRSignalTrace.entry_signal.is_(True),
                )
                .limit(limit_per_strategy)
                .all()
            )
            out["sbbr"] = [_row_to_dict_sbbr(r) for r in rows]

    if rpe_cid is not None:
        try:
            from datetime import date as _date

            td = _date.fromisoformat(d)
        except ValueError:
            td = None
        if td is not None:
            rows = (
                db.query(RPESignalTrace)
                .filter(
                    RPESignalTrace.trade_date == td,
                    RPESignalTrace.config_id == int(rpe_cid),
                    RPESignalTrace.entry_signal.is_(True),
                )
                .limit(limit_per_strategy)
                .all()
            )
            out["rpe"] = [_row_to_dict_rpe(r) for r in rows]

    logger.info(
        "recommend candidates asof=%s urt=%s gms=%s sbbr=%s rpe=%s",
        d,
        len(out["urt"]),
        len(out["gms"]),
        len(out["sbbr"]),
        len(out["rpe"]),
    )
    return out


def merge_candidates_by_code(
    by_strategy: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    """按 code 合并多策略命中。"""
    from backend_core.recommend.config import STRATEGY_PRIORITY

    merged: Dict[str, Dict[str, Any]] = {}
    for strat in STRATEGY_PRIORITY:
        for row in by_strategy.get(strat) or []:
            code = _norm_code(row.get("code"))
            if not code:
                continue
            bucket = merged.setdefault(
                code,
                {
                    "code": code,
                    "name": row.get("name"),
                    "strategies": [],
                    "strategy_rows": {},
                    "primary_strategy": None,
                    "best_score": None,
                },
            )
            if row.get("name") and not bucket.get("name"):
                bucket["name"] = row.get("name")
            if strat not in bucket["strategies"]:
                bucket["strategies"].append(strat)
            bucket["strategy_rows"][strat] = row
            sc = row.get("score")
            if sc is not None:
                try:
                    f = float(sc)
                    if bucket["best_score"] is None or f > float(bucket["best_score"]):
                        bucket["best_score"] = f
                except (TypeError, ValueError):
                    pass

    for bucket in merged.values():
        for strat in STRATEGY_PRIORITY:
            if strat in bucket["strategies"]:
                bucket["primary_strategy"] = strat
                break
    return merged
