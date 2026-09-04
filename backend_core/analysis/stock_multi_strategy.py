# -*- coding: utf-8 -*-
"""个股 × 四策略（GMS/URT/SBBR/RPE）命中与得分聚合。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend_core.analysis.board_signals import (
    STRATEGY_KEYS,
    _filter_gms,
    _filter_rpe,
    _filter_sbbr,
    _filter_urt,
    _norm_code,
    _strategy_hit_cell,
)

logger = logging.getLogger(__name__)

_STRATEGY_DISPLAY = {
    "gms": "GMS 均值引力动量",
    "urt": "URT 上升趋势",
    "sbbr": "SBBR 做小做底",
    "rpe": "RPE 比价效应",
}

_TRACE_PAGES = {
    "gms": "stock_gms_trace.html",
    "urt": "stock_urt_trace.html",
    "sbbr": "stock_sbbr_trace.html",
    "rpe": "stock_rpe_trace.html",
}

_SCREENING_HASH = {
    "gms": "gms",
    "urt": "urt",
    "sbbr": "sbbr",
    "rpe": "rpe",
}


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pick_score(strategy: str, row: Optional[Dict[str, Any]]) -> Optional[float]:
    """从策略结果行提取展示用得分；无得分字段则返回 None。"""
    if not row:
        return None
    kind = (strategy or "").strip().lower()
    if kind == "gms":
        return _as_float(row.get("score_total"))
    if kind == "urt":
        for k in ("score_total", "total_score", "score"):
            sc = _as_float(row.get(k))
            if sc is not None:
                return sc
        return None
    if kind == "sbbr":
        # SBBR 无统一总分：优先 volume_ratio，否则不展示数值分
        return _as_float(row.get("volume_ratio"))
    if kind == "rpe":
        for k in ("z_score", "zscore", "score", "relative_z"):
            sc = _as_float(row.get(k))
            if sc is not None:
                return sc
        return None
    return None


def _score_display(strategy: str, score: Optional[float], row: Optional[Dict[str, Any]]) -> str:
    """得分展示文案；无得分时给出策略相关标签。"""
    kind = (strategy or "").strip().lower()
    if kind == "gms":
        if score is not None:
            return f"总分 {score:.1f}"
        return "--"
    if kind == "urt":
        if score is not None:
            return f"得分 {score:.1f}"
        return "--"
    if kind == "sbbr":
        tags = []
        if row:
            if row.get("size_ok"):
                tags.append("做小✓")
            elif row.get("size_ok") is False:
                tags.append("做小✗")
            if row.get("bottom_matched"):
                tags.append("筑底✓")
            if row.get("entry_signal"):
                tags.append("入场✓")
            if score is not None:
                tags.append(f"量比 {score:.2f}")
        return " · ".join(tags) if tags else "--"
    if kind == "rpe":
        if score is not None:
            return f"Z={score:.2f}"
        if row and row.get("signal_type"):
            return str(row.get("signal_type"))
        return "--"
    return f"{score:.2f}" if score is not None else "--"


def _build_reason(strategy: str, hit: bool, row: Optional[Dict[str, Any]], label: str) -> str:
    kind = (strategy or "").strip().lower()
    if not row:
        return "无策略计算结果" if not hit else (label or "命中")
    if kind == "gms":
        parts = []
        bt = row.get("buy_type") or label
        if hit:
            parts.append(f"买点：{bt}")
        else:
            parts.append("未触发左/右侧买点")
        sc = _as_float(row.get("score_total"))
        if sc is not None:
            parts.append(f"总分 {sc:.1f}")
        return "；".join(parts)
    if kind == "urt":
        if hit:
            return "满足上升趋势买点条件"
        reason = row.get("fail_reason") or row.get("reject_reason") or row.get("reason")
        if reason:
            return str(reason)
        return "未通过买点（已跳过选股硬筛，见明细）"
    if kind == "sbbr":
        parts = []
        if row.get("entry_signal"):
            parts.append("入场信号")
        elif row.get("bottom_matched"):
            parts.append("筑底关注（未入场）")
        else:
            parts.append("未触发入场/筑底")
        if row.get("size_ok") is False:
            parts.append("未过做小过滤")
        elif row.get("size_ok"):
            parts.append("做小通过")
        return "；".join(parts)
    if kind == "rpe":
        if hit:
            return f"信号：{label}"
        return "相对板块基准未触发补涨/领涨观察"
    return label or ("命中" if hit else "未命中")


def _slim_row(row: Optional[Dict[str, Any]], keys: Sequence[str]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    out: Dict[str, Any] = {}
    for k in keys:
        if k in row and row[k] is not None:
            out[k] = row[k]
    return out or None


_SLIM_KEYS = {
    "gms": (
        "symbol",
        "code",
        "score_total",
        "buy_type",
        "left_buy_signal",
        "right_buy_signal",
        "market_type",
    ),
    "urt": (
        "code",
        "symbol",
        "buy_signal",
        "score_total",
        "total_score",
        "score",
        "fail_reason",
        "reject_reason",
    ),
    "sbbr": (
        "code",
        "entry_signal",
        "bottom_matched",
        "size_ok",
        "volume_ratio",
        "entry_low",
        "defense_low",
        "box_resistance",
    ),
    "rpe": (
        "code",
        "signal_type",
        "entry_signal",
        "watch_only",
        "z_score",
        "zscore",
        "board_code",
        "board_name",
    ),
}


def summarize_strategy_check(
    strategy: str,
    row: Optional[Dict[str, Any]] = None,
    *,
    watch_row: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    message: Optional[str] = None,
    stock_code: str = "",
) -> Dict[str, Any]:
    """将引擎原始行汇总为前端卡片字段（可单测、无 DB）。"""
    kind = (strategy or "").strip().lower()
    code = _norm_code(stock_code) or _norm_code(
        (row or {}).get("code")
        or (row or {}).get("symbol")
        or (row or {}).get("stock_code")
    )
    display = _STRATEGY_DISPLAY.get(kind, kind.upper())
    base = {
        "strategy": kind,
        "name": display,
        "hit": False,
        "label": "--",
        "kind": None,
        "score": None,
        "score_display": "--",
        "reason": message or (f"计算失败：{error}" if error else "无结果"),
        "error": error,
        "message": message,
        "detail": None,
        "trace_url": f"{_TRACE_PAGES.get(kind, 'screening.html')}?code={code}" if code else None,
        "screening_url": f"screening.html#{_SCREENING_HASH.get(kind, '')}" if kind in _SCREENING_HASH else "screening.html",
    }
    if error:
        return base
    if kind not in STRATEGY_KEYS:
        base["reason"] = f"未知策略：{strategy}"
        return base

    hit_row: Optional[Dict[str, Any]] = None
    wrow: Optional[Dict[str, Any]] = None
    if kind == "gms":
        hits = _filter_gms([row] if row else [])
        hit_row = hits[0] if hits else None
    elif kind == "urt":
        hits = _filter_urt([row] if row else [])
        hit_row = hits[0] if hits else None
    elif kind == "sbbr":
        # 优先用显式 entry/watch；否则从完整行拆分
        if row and row.get("entry_signal"):
            hit_row = row
        elif watch_row or (row and row.get("bottom_matched")):
            wrow = watch_row or row
        elif row:
            entry, watch = _filter_sbbr([row])
            hit_row = entry[0] if entry else None
            wrow = watch[0] if watch else None
    elif kind == "rpe":
        hits = _filter_rpe([row] if row else [])
        hit_row = hits[0] if hits else None

    cell = _strategy_hit_cell(kind, hit_row, watch_row=wrow)
    src = hit_row or wrow or row
    score = _pick_score(kind, src)
    base.update(
        {
            "hit": bool(cell.get("hit")),
            "label": cell.get("label") or "--",
            "kind": cell.get("kind"),
            "score": score,
            "score_display": _score_display(kind, score, src),
            "reason": message
            or _build_reason(kind, bool(cell.get("hit")), src, str(cell.get("label") or "")),
            "detail": _slim_row(src, _SLIM_KEYS.get(kind, ())),
        }
    )
    return base


def _resolve_trade_date(db: Session, raw: Optional[str]) -> str:
    s = (str(raw).strip()[:10] if raw else "") or None
    if s:
        return s
    try:
        from sqlalchemy import func

        from backend_api.models import HistoricalQuotes

        latest = db.query(func.max(HistoricalQuotes.date)).scalar()
        if latest:
            if hasattr(latest, "strftime"):
                return latest.strftime("%Y-%m-%d")
            return str(latest).strip()[:10]
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def _fetch_gms_raw(db: Session, code: str, trade_date: str) -> Optional[Dict[str, Any]]:
    from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface

    iface = GMSFrontendInterface(db)
    iface.set_selection_config(min_score=0, max_results=10)
    rows = iface.get_selection_results(
        date=trade_date, stock_pool=[code], market="all", trace_only=False
    )
    if isinstance(rows, tuple):
        rows = rows[0]
    for r in rows or []:
        sym = _norm_code(r.get("symbol") or r.get("code"))
        if sym == code or sym.lstrip("0") == code.lstrip("0"):
            return dict(r)
    if rows:
        return dict(rows[0])
    return None


def _fetch_urt_raw(db: Session, code: str, trade_date: str) -> Optional[Dict[str, Any]]:
    from backend_core.strategies.urt.frontend_interface import URTFrontendInterface

    market = "HK" if (code.isdigit() and len(code) <= 5) else "CN"
    result = URTFrontendInterface.screen(
        db,
        scope="watchlist",
        stock_codes=[code],
        screening_date=trade_date,
        limit=5,
        prefer_cache=False,
        force_realtime=True,
        skip_screening_filters=True,
        market=market,
    )
    rows = (result or {}).get("data") if isinstance(result, dict) else result
    for r in rows or []:
        if _norm_code(r.get("code") or r.get("symbol")) == code:
            return dict(r)
    if rows:
        return dict(list(rows)[0])
    return None


def _fetch_sbbr_raw(db: Session, code: str, trade_date: str) -> Optional[Dict[str, Any]]:
    if not (code.isdigit() and len(code) == 6):
        return None
    from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

    engine = SBBRStrategyEngine(db_session=db)
    rows = engine.screen(
        codes=[code],
        date=trade_date,
        require_entry=False,
        require_size=False,
        require_bottom=False,
        max_results=5,
    )
    return dict(rows[0]) if rows else None


def _fetch_rpe_raw(db: Session, code: str, trade_date: str) -> Optional[Dict[str, Any]]:
    if not (code.isdigit() and len(code) == 6):
        return None
    from backend_core.strategies.rpe.frontend_interface import RPEFrontendInterface

    result = RPEFrontendInterface.get_selection_results(
        db=db,
        date=trade_date,
        scope="cn",
        codes=[code],
        entry_only=False,
        include_no_signal=True,
        max_results=20,
        adjust="none",
    )
    rows = (result or {}).get("data") if isinstance(result, dict) else result
    for r in rows or []:
        if _norm_code(r.get("code") or r.get("symbol")) == code:
            return dict(r)
    if rows:
        return dict(list(rows)[0])
    return None


def _eval_gms(db: Session, code: str, trade_date: str) -> Dict[str, Any]:
    row = _fetch_gms_raw(db, code, trade_date)
    return summarize_strategy_check("gms", row, stock_code=code)


def _eval_urt(db: Session, code: str, trade_date: str) -> Dict[str, Any]:
    row = _fetch_urt_raw(db, code, trade_date)
    return summarize_strategy_check("urt", row, stock_code=code)


def _eval_sbbr(db: Session, code: str, trade_date: str) -> Dict[str, Any]:
    if not (code.isdigit() and len(code) == 6):
        return summarize_strategy_check(
            "sbbr",
            None,
            stock_code=code,
            message="SBBR 暂仅支持 A 股（6 位代码）",
        )
    row = _fetch_sbbr_raw(db, code, trade_date)
    return summarize_strategy_check("sbbr", row, stock_code=code)


def _eval_rpe(db: Session, code: str, trade_date: str) -> Dict[str, Any]:
    if not (code.isdigit() and len(code) == 6):
        return summarize_strategy_check(
            "rpe",
            None,
            stock_code=code,
            message="RPE 暂仅支持 A 股（6 位代码）",
        )
    row = _fetch_rpe_raw(db, code, trade_date)
    return summarize_strategy_check("rpe", row, stock_code=code)


def collect_strategy_raw_rows(
    db: Session,
    *,
    code: str,
    date: Optional[str] = None,
    strategies: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """返回四策略完整原始行（供 trade_advice / 综合交易策略合成）。"""
    code_n = _norm_code(code)
    if code_n.isdigit():
        if len(code_n) <= 5:
            code_n = code_n.zfill(5)
        elif len(code_n) == 6:
            code_n = code_n.zfill(6)

    wanted = [
        s.strip().lower()
        for s in (strategies or STRATEGY_KEYS)
        if s and s.strip().lower() in STRATEGY_KEYS
    ]
    if not wanted:
        wanted = list(STRATEGY_KEYS)

    trade_date = _resolve_trade_date(db, date)
    fetchers = {
        "gms": _fetch_gms_raw,
        "urt": _fetch_urt_raw,
        "sbbr": _fetch_sbbr_raw,
        "rpe": _fetch_rpe_raw,
    }
    rows: Dict[str, Optional[Dict[str, Any]]] = {}
    summaries: Dict[str, Dict[str, Any]] = {}
    errors: Dict[str, str] = {}
    for key in wanted:
        fn = fetchers[key]
        try:
            raw = fn(db, code_n, trade_date)
            rows[key] = raw
            summaries[key] = summarize_strategy_check(key, raw, stock_code=code_n)
        except Exception as e:
            logger.exception("raw strategy %s failed for %s", key, code_n)
            try:
                db.rollback()
            except Exception:
                pass
            err = str(e)
            errors[key] = err
            rows[key] = None
            summaries[key] = summarize_strategy_check(key, None, stock_code=code_n, error=err)

    return {
        "code": code_n,
        "trade_date": trade_date,
        "strategies": list(wanted),
        "rows": rows,
        "summaries": summaries,
        "errors": errors,
    }


def _lookup_stock_name(db: Session, code: str) -> str:
    try:
        from backend_api.models import StockBasicInfo, StockBasicInfoHK
    except Exception:
        from backend_api.models import StockBasicInfo, StockBasicInfoHK  # type: ignore

    try:
        if code.isdigit() and len(code) == 6:
            row = db.query(StockBasicInfo).filter(StockBasicInfo.code == code).first()
            if row and row.name:
                return str(row.name)
        row = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == code).first()
        if row and row.name:
            return str(row.name)
        if code.isdigit() and len(code) < 5:
            padded = code.zfill(5)
            row = db.query(StockBasicInfoHK).filter(StockBasicInfoHK.code == padded).first()
            if row and row.name:
                return str(row.name)
    except Exception as e:
        logger.debug("lookup name skip: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    return ""


def collect_stock_multi_strategy_check(
    db: Session,
    *,
    code: str,
    name: Optional[str] = None,
    date: Optional[str] = None,
    strategies: Optional[Sequence[str]] = None,
    use_realtime: bool = False,
) -> Dict[str, Any]:
    """并行语义：顺序评估四策略（单股，耗时短），返回统一卡片列表。"""
    code_n = _norm_code(code)
    if code_n.isdigit():
        if len(code_n) <= 5:
            code_n = code_n.zfill(5)
        elif len(code_n) == 6:
            code_n = code_n.zfill(6)

    wanted = [
        s.strip().lower()
        for s in (strategies or STRATEGY_KEYS)
        if s and s.strip().lower() in STRATEGY_KEYS
    ]
    if not wanted:
        wanted = list(STRATEGY_KEYS)

    realtime_meta: Optional[Dict[str, Any]] = None
    date_for_strategy = date
    if use_realtime:
        try:
            from backend_core.analysis.realtime_bars import fetch_live_realtime_quote

            quote = fetch_live_realtime_quote(db, code_n)
            if quote:
                realtime_meta = {
                    "trade_date": quote.get("trade_date"),
                    "current_price": quote.get("current_price"),
                    "change_percent": quote.get("change_percent"),
                    "source": quote.get("source"),
                    "update_time": quote.get("update_time"),
                    "open": quote.get("open"),
                    "high": quote.get("high"),
                    "low": quote.get("low"),
                }
                # 未指定基准日时，策略尽量按实时交易日评估（无当日 K 则各引擎自行回退）
                if not date_for_strategy and quote.get("trade_date"):
                    date_for_strategy = str(quote["trade_date"])[:10]
        except Exception as e:
            logger.warning("multi-strategy realtime quote skip: %s", e)

    trade_date = _resolve_trade_date(db, date_for_strategy)
    stock_name = (name or "").strip() or _lookup_stock_name(db, code_n)

    evaluators = {
        "gms": _eval_gms,
        "urt": _eval_urt,
        "sbbr": _eval_sbbr,
        "rpe": _eval_rpe,
    }
    results: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}
    for key in wanted:
        fn = evaluators[key]
        try:
            results.append(fn(db, code_n, trade_date))
        except Exception as e:
            logger.exception("multi-strategy %s failed for %s", key, code_n)
            try:
                db.rollback()
            except Exception:
                pass
            err = str(e)
            errors[key] = err
            results.append(
                summarize_strategy_check(key, None, stock_code=code_n, error=err)
            )

    hit_count = sum(1 for r in results if r.get("hit"))
    out: Dict[str, Any] = {
        "stock": {"code": code_n, "name": stock_name},
        "trade_date": trade_date,
        "requested_date": (str(date).strip()[:10] if date else None),
        "strategies": list(wanted),
        "results": results,
        "hit_count": hit_count,
        "any_hit": hit_count > 0,
        "errors": errors,
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "use_realtime": bool(use_realtime),
    }
    if realtime_meta:
        out["realtime"] = realtime_meta
        # 展示用：实时分析时基准日优先显示实时交易日
        if realtime_meta.get("trade_date"):
            out["realtime_trade_date"] = str(realtime_meta["trade_date"])[:10]
    return out
