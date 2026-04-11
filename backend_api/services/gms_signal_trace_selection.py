"""
GMS 选股列表：从 gms_signal_trace 表读取（管理端与 PVFRS 前端选股接口共用）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import String as SAString, bindparam, desc, func, text
from sqlalchemy.orm import Session

from backend_api.models import GMSSignalTrace

logger = logging.getLogger(__name__)


def _txt_name_cn():
    return text("SELECT name FROM stock_basic_info WHERE code = :code LIMIT 1").bindparams(
        bindparam("code", type_=SAString())
    )


def _txt_name_hk():
    return text("SELECT name FROM stock_basic_info_hk WHERE code = :code LIMIT 1").bindparams(
        bindparam("code", type_=SAString())
    )


def _stock_name_for_code(db: Session, code: str) -> str:
    """与 pvfrs 选股接口一致：按代码形态查 A 股 / 港股名称。"""
    c = str(code).strip()
    if not c:
        return f"股票{c}"
    is_cn = len(c) >= 6 and c.isdigit() and c[0] in "6039"
    if is_cn:
        row = db.execute(_txt_name_cn(), {"code": c}).fetchone()
    else:
        row = db.execute(_txt_name_hk(), {"code": c}).fetchone()
    if row and row[0]:
        return str(row[0]).strip()
    return f"股票{c}"


def _normalize_buy_type_label(
    raw_buy_type: Optional[str],
    left_signal: Optional[bool],
    right_signal: Optional[bool],
) -> str:
    if left_signal:
        return "左侧"
    if right_signal:
        return "右侧"
    s = str(raw_buy_type or "").strip().lower()
    if s in ("左侧", "left", "left_buy", "leftbuy"):
        return "左侧"
    if s in ("右侧", "right", "right_buy", "rightbuy"):
        return "右侧"
    if "左侧" in s or "left" in s:
        return "左侧"
    if "右侧" in s or "right" in s:
        return "右侧"
    return "--"


def query_gms_signal_trace_selection(
    db: Session,
    date: Optional[str],
    min_strength: float,
    limit: Optional[int],
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    从 gms_signal_trace 查询选股列表，按 score_total 降序。

    Returns:
        (payload_dict, fallback_message)
    """
    requested_date = date
    target_date: Optional[str] = None
    if not requested_date:
        max_row = db.query(func.max(GMSSignalTrace.date)).scalar()
        target_date = str(max_row).strip()[:10] if max_row else None
    else:
        target_date = str(requested_date).strip()[:10]

    if not target_date:
        return (
            {
                "success": True,
                "data": [],
                "total": 0,
                "search_date": None,
                "strategy_name": "GMS均值引力动量策略",
                "data_source": "gms_signal_trace",
                "timestamp": datetime.now().isoformat(),
                "message": "策略结果表中无数据",
            },
            None,
        )

    min_score = float(min_strength) * 100.0
    query = db.query(GMSSignalTrace).filter(GMSSignalTrace.date == target_date)
    if min_strength > 0:
        query = query.filter(GMSSignalTrace.score_total >= min_score)
    query = query.order_by(desc(GMSSignalTrace.score_total))
    if limit:
        query = query.limit(limit * 3)
    selection_results: List[GMSSignalTrace] = query.all()

    fallback_message: Optional[str] = None
    if not selection_results and requested_date:
        latest_date = db.query(func.max(GMSSignalTrace.date)).scalar()
        if latest_date and str(latest_date).strip()[:10] != target_date:
            target_date = str(latest_date).strip()[:10]
            query = db.query(GMSSignalTrace).filter(GMSSignalTrace.date == target_date)
            if min_strength > 0:
                query = query.filter(GMSSignalTrace.score_total >= min_score)
            query = query.order_by(desc(GMSSignalTrace.score_total))
            if limit:
                query = query.limit(limit * 3)
            selection_results = query.all()
            fallback_message = f"请求日期 {requested_date} 暂无数据，已展示最近日期 {target_date} 的选股结果"

    seen_codes: set = set()
    deduped: List[GMSSignalTrace] = []
    for r in selection_results:
        c = r.code
        if c in seen_codes:
            continue
        seen_codes.add(c)
        deduped.append(r)
        if limit and len(deduped) >= limit:
            break

    results_data: List[Dict[str, Any]] = []
    for r in deduped:
        code = r.code
        st = float(r.score_total or 0)
        name = _stock_name_for_code(db, code)

        if st >= 90:
            advice = "强烈推荐"
        elif st >= 75:
            advice = "推荐"
        elif st >= 60:
            advice = "关注"
        else:
            advice = "观望"

        left_sig = bool(getattr(r, "left_buy_signal", None))
        right_sig = bool(getattr(r, "right_buy_signal", None))
        buy_label = _normalize_buy_type_label(getattr(r, "buy_type", None), left_sig, right_sig)

        results_data.append(
            {
                "symbol": code,
                "name": name,
                "signal_strength": st / 100.0,
                "score_total": st,
                "score_accumulation": r.score_accumulation,
                "score_momentum": r.score_momentum,
                "accumulation_grade": r.accumulation_grade or "",
                "momentum_grade": r.momentum_grade or "",
                "buy_type": buy_label,
                "left_buy_signal": left_sig,
                "right_buy_signal": right_sig,
                "sell_signal": bool(getattr(r, "sell_signal", None)),
                "delta": r.delta,
                "d": r.d,
                "ratio_d20": r.ratio_d20,
                "ratio_d1": r.ratio_d1,
                "fz_ratio": r.fz_ratio,
                "volume_ratio": r.volume_ratio,
                "rising_days": r.rising_days,
                "falling_days": r.falling_days,
                "instant_deviation": r.instant_deviation,
                "investment_advice": advice,
                "price": r.d or 0,
                "market_type": getattr(r, "market_type", None),
                "indicators": {
                    "price_dimension": {
                        "macro_displacement": r.score_accumulation or 0,
                        "accumulation_grade": r.accumulation_grade or "",
                    },
                    "frequency_dimension": {
                        "rising_days": r.rising_days,
                        "falling_days": r.falling_days,
                        "score_momentum": r.score_momentum or 0,
                    },
                    "volume_dimension": {
                        "efficiency_ratio": getattr(r, "score_acc_balance", None) or 0,
                        "fz_ratio": r.fz_ratio,
                    },
                    "gms": {
                        "buy_type": buy_label,
                        "momentum_grade": r.momentum_grade or "",
                    },
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    payload = {
        "success": True,
        "data": results_data,
        "total": len(results_data),
        "search_date": target_date,
        "strategy_name": "GMS均值引力动量策略",
        "data_source": "gms_signal_trace",
        "timestamp": datetime.now().isoformat(),
    }
    return payload, fallback_message
