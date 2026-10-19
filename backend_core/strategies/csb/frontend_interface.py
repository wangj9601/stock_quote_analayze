# -*- coding: utf-8 -*-
"""CSB 对外选股入口（优先读 csb_signal_trace；全市场现算默认关闭，需显式开启）。"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .config import CSB_STOCK_DAY_SCANNED, CSBConfigManager
from .data_loader import CSBDataLoader
from .strategy_engine import CSBStrategyEngine
from .trace_store import (
    codes_present_on_date,
    dates_present_for_code,
    dates_ready_for_universe_backtest,
    mark_date_scanned,
    query_buy_signals_for_date,
    query_trace_by_code,
    upsert_trace_rows,
)

# 小范围（个股/自选）同步补算上限；更大的池子仍走原有全池现算或预计算。
_FILL_MISSING_MAX_CODES = 40
_HISTORY_MAX_CALENDAR_DAYS = 180
_HISTORY_MAX_TRADE_DAYS = 120

logger = logging.getLogger(__name__)


def _env_allow_full_market_realtime() -> bool:
    """
    全市场现算默认关闭，避免生产网关超时、前端「刷新筛选」长时间无响应。
    需要显式开启时设 CSB_ALLOW_FULL_MARKET_REALTIME=1。
    """
    raw = (os.getenv("CSB_ALLOW_FULL_MARKET_REALTIME") or "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _norm_codes(codes: Optional[List[str]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in codes or []:
        s = str(raw or "").strip()
        if s.isdigit() and len(s) <= 6:
            s = s.zfill(6)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _stock_day_marker(code: str, trade_date: str, name: str = "") -> Dict[str, Any]:
    return {
        "code": code,
        "name": name or "",
        "signal_date": str(trade_date)[:10],
        "signal_type": CSB_STOCK_DAY_SCANNED,
        "setup_ok": False,
        "entry_signal": False,
        "score": 0,
        "detail": {"marker": "stock_day_scanned"},
    }


def fill_codes_on_date(
    db: Session,
    *,
    codes: List[str],
    trade_date: str,
    config: Dict[str, Any],
    config_id: int,
    loader: Optional[CSBDataLoader] = None,
) -> int:
    """对缺少 trace 行的代码按 asof 现算并落库。无信号也写入占位，避免重复现算。"""
    loader = loader or CSBDataLoader(db)
    engine = CSBStrategyEngine(loader, config)
    rows: List[Dict[str, Any]] = []
    for code in codes:
        row = engine.evaluate_code(code, date=trade_date, config=config)
        if row:
            rows.append(row)
        else:
            rows.append(_stock_day_marker(code, trade_date))
    if rows:
        upsert_trace_rows(db, config_id=int(config_id), rows=rows)
    return len(rows)


def list_quote_dates(db: Session, code: str, start_date: str, end_date: str) -> List[str]:
    from sqlalchemy import cast, String

    from backend_api.models import HistoricalQuotes

    q = db.query(HistoricalQuotes.date).filter(HistoricalQuotes.code == code)
    q = q.filter(cast(HistoricalQuotes.date, String) >= str(start_date)[:10])
    q = q.filter(cast(HistoricalQuotes.date, String) <= str(end_date)[:10])
    return sorted(str(r[0])[:10] for r in q.distinct().order_by(HistoricalQuotes.date).all() if r[0])


class CSBFrontendInterface:
    @staticmethod
    def _resolve_config_id(db: Session, config_id: Optional[int], cm: CSBConfigManager) -> Optional[int]:
        if config_id is not None:
            return int(config_id)
        try:
            from backend_api.models import CSBStrategyConfig

            row = (
                db.query(CSBStrategyConfig)
                .filter(CSBStrategyConfig.is_default.is_(True), CSBStrategyConfig.is_active.is_(True))
                .order_by(CSBStrategyConfig.id.asc())
                .first()
            )
            return int(row.id) if row else None
        except Exception:
            return None

    @staticmethod
    def backfill_signal_history(
        db: Session,
        *,
        code: str,
        config: Dict[str, Any],
        config_id: int,
        start_date: str,
        end_date: str,
        entry_only: bool = False,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """区间内优先读预计算；没有该日 trace 行则 asof 补算并落库。"""
        code_n = _norm_codes([code])
        if not code_n:
            raise ValueError("股票代码不能为空")
        code_s = code_n[0]
        start_s = str(start_date)[:10]
        end_s = str(end_date)[:10]
        start_d = datetime.strptime(start_s, "%Y-%m-%d").date()
        end_d = datetime.strptime(end_s, "%Y-%m-%d").date()
        if start_d > end_d:
            raise ValueError("开始日期不能晚于结束日期")
        if (end_d - start_d).days > _HISTORY_MAX_CALENDAR_DAYS:
            raise ValueError(f"日期跨度不能超过 {_HISTORY_MAX_CALENDAR_DAYS} 天")

        dates = list_quote_dates(db, code_s, start_s, end_s)
        if len(dates) > _HISTORY_MAX_TRADE_DAYS:
            raise ValueError(f"区间交易日不能超过 {_HISTORY_MAX_TRADE_DAYS} 天，请缩短日期")

        present = dates_present_for_code(
            db, config_id=int(config_id), code=code_s, start_date=start_s, end_date=end_s
        )
        missing = [d for d in dates if d not in present]
        recomputed = 0
        if missing:
            loader = CSBDataLoader(db)
            for d in missing:
                fill_codes_on_date(
                    db,
                    codes=[code_s],
                    trade_date=d,
                    config=config,
                    config_id=int(config_id),
                    loader=loader,
                )
                recomputed += 1

        rows = query_trace_by_code(
            db,
            code=code_s,
            config_id=int(config_id),
            start_date=start_s,
            end_date=end_s,
            limit=limit,
        )
        if entry_only:
            rows = [r for r in rows if r.get("entry_signal")]
        missing_set = set(missing)
        for r in rows:
            day = str(r.get("signal_date") or r.get("trade_date") or r.get("date") or "")[:10]
            r["row_source"] = "recompute" if day in missing_set else "trace"
        cached_days = len(present)
        return {
            "code": code_s,
            "start_date": start_s,
            "end_date": end_s,
            "trade_days": len(dates),
            "cached_days": cached_days,
            "recomputed_days": recomputed,
            "source": "trace+recompute" if recomputed else "trace",
            "source_label": "预计算并补算缺口" if recomputed else "预计算",
            "data": rows,
            "total": len(rows),
        }

    @staticmethod
    def screen(
        db: Session,
        *,
        scope: str = "all",
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
        screening_date: Optional[str] = None,
        config_id: Optional[int] = None,
        min_score: Optional[float] = None,
        prefer_cache: bool = True,
        force_realtime: bool = False,
        require_entry: bool = True,
        trace_only: bool = False,
        persist_realtime: bool = True,
    ) -> Dict[str, Any]:
        cm = CSBConfigManager()
        try:
            cm.ensure_default_row(db)
        except Exception:
            pass

        resolved_id = CSBFrontendInterface._resolve_config_id(db, config_id, cm)
        base = cm.get_config(resolved_id, db=db)
        cfg = cm.merge_overrides(base, min_score=min_score) if min_score is not None else base

        loader = CSBDataLoader(db)
        requested = (screening_date or "").strip()[:10]
        if requested:
            try:
                datetime.strptime(requested, "%Y-%m-%d")
            except ValueError:
                requested = ""
        # 显式选择的日期若无行情（节假日/周末等）：不回退上一交易日
        if requested and not loader.is_trading_day(requested):
            return {
                "success": True,
                "data": [],
                "total": 0,
                "strategy_name": "CSB通道突破",
                "scope": scope,
                "message": "非交易日、无数据",
                "need_precompute": False,
                "non_trading_day": True,
                "search_date": requested,
                "config_id": resolved_id,
                "source": "non_trading_day",
                "data_source": "non_trading_day",
                "parameters": {
                    "config_id": resolved_id,
                    "min_score": cfg.get("min_score"),
                    "screening_date_effective": requested,
                    "data_source": "non_trading_day",
                    "non_trading_day": True,
                },
            }

        effective = loader.resolve_effective_trade_date(screening_date)
        data: List[Dict[str, Any]] = []
        data_source = "realtime"
        date_ready = False
        hint: Optional[str] = None

        if prefer_cache and not force_realtime and resolved_id is not None:
            try:
                cached = query_buy_signals_for_date(
                    db,
                    trade_date=effective,
                    config_id=int(resolved_id),
                    min_score=float(cfg.get("min_score") or 0) if require_entry else None,
                    limit=limit,
                    entry_only=bool(require_entry),
                ) or []
                if stock_codes is not None:
                    allow = {
                        str(c).strip().zfill(6) if str(c).strip().isdigit() else str(c).strip()
                        for c in stock_codes
                    }
                    cached = [r for r in cached if str(r.get("code") or "").zfill(6) in allow]
                date_ready = effective in dates_ready_for_universe_backtest(
                    db, config_id=int(resolved_id), dates=[effective], stock_pool=stock_codes
                )
                if cached or date_ready:
                    data = cached
                    data_source = "csb_signal_trace"
                    if not cached and date_ready:
                        hint = (
                            f"基准日 {effective} 已有预计算，当日无符合条件的买点。"
                            if require_entry
                            else f"基准日 {effective} 已有预计算，当日无信号。"
                        )
            except Exception as e:
                logger.debug("CSB cache read failed: %s", e)

        pool = _norm_codes(stock_codes)
        # 个股/小池：全市场已扫标记不能代替「该股当天有行」。缺行则只补算这些代码。
        if (
            pool
            and len(pool) <= _FILL_MISSING_MAX_CODES
            and prefer_cache
            and not force_realtime
            and not trace_only
            and resolved_id is not None
            and effective
        ):
            try:
                present = codes_present_on_date(
                    db, config_id=int(resolved_id), trade_date=effective, codes=pool
                )
                missing = [c for c in pool if c not in present]
                if missing:
                    fill_codes_on_date(
                        db,
                        codes=missing,
                        trade_date=effective,
                        config=cfg,
                        config_id=int(resolved_id),
                        loader=loader,
                    )
                    cached = query_buy_signals_for_date(
                        db,
                        trade_date=effective,
                        config_id=int(resolved_id),
                        min_score=float(cfg.get("min_score") or 0) if require_entry else None,
                        limit=limit,
                        entry_only=bool(require_entry),
                    ) or []
                    allow = set(pool)
                    cached = [r for r in cached if str(r.get("code") or "").zfill(6) in allow or str(r.get("code") or "") in allow]
                    data = cached
                    data_source = "realtime+trace"
                    date_ready = True
                    if not cached:
                        hint = (
                            f"基准日 {effective} 已补算，当日无符合条件的买点。"
                            if require_entry
                            else f"基准日 {effective} 已补算，当日无信号。"
                        )
                    else:
                        hint = None
            except Exception as e:
                logger.warning("CSB 小范围缺行补算失败: %s", e)

        # 仅读预计算：有覆盖（含 0 买点）即返回；无覆盖则提示需预计算/现算
        if trace_only and not force_realtime:
            if data_source == "csb_signal_trace":
                return {
                    "success": True,
                    "data": data,
                    "total": len(data),
                    "strategy_name": "CSB通道突破",
                    "scope": scope,
                    "message": hint,
                    "need_precompute": False,
                    "search_date": effective,
                    "config_id": resolved_id,
                    "source": data_source,
                    "data_source": data_source,
                    "parameters": {
                        "config_id": resolved_id,
                        "min_score": cfg.get("min_score"),
                        "screening_date_effective": effective,
                        "data_source": data_source,
                        "trace_only": True,
                    },
                }
            return {
                "success": True,
                "data": [],
                "total": 0,
                "strategy_name": "CSB通道突破",
                "scope": scope,
                "message": (
                    f"全市场暂无预计算（{effective}）。"
                    "请先在管理端/工作流执行 CSB 信号预计算，或将范围缩小为自选/板块/个股后再刷新。"
                ),
                "need_precompute": True,
                "search_date": effective,
                "config_id": resolved_id,
                "source": "empty_trace",
                "data_source": "empty_trace",
                "parameters": {
                    "config_id": resolved_id,
                    "min_score": cfg.get("min_score"),
                    "screening_date_effective": effective,
                    "data_source": "empty_trace",
                    "trace_only": True,
                    "need_precompute": True,
                },
            }

        if data_source in ("csb_signal_trace", "realtime+trace"):
            return {
                "success": True,
                "data": data,
                "total": len(data),
                "strategy_name": "CSB通道突破",
                "scope": scope,
                "message": hint,
                "need_precompute": False,
                "search_date": effective,
                "config_id": resolved_id,
                "source": data_source,
                "data_source": data_source,
                "parameters": {
                    "config_id": resolved_id,
                    "min_score": cfg.get("min_score"),
                    "screening_date_effective": effective,
                    "data_source": data_source,
                },
            }

        full_market = stock_codes is None
        if full_market and not _env_allow_full_market_realtime():
            return {
                "success": True,
                "data": [],
                "total": 0,
                "strategy_name": "CSB通道突破",
                "scope": scope,
                "message": (
                    f"全市场暂无预计算（{effective}）。"
                    "请先在管理端/工作流执行 CSB 信号预计算，或将范围缩小为自选/板块/个股后再刷新。"
                    "（全市场现算已关闭，避免网关超时；如需开启请设 CSB_ALLOW_FULL_MARKET_REALTIME=1）"
                ),
                "need_precompute": True,
                "search_date": effective,
                "config_id": resolved_id,
                "source": "empty_trace",
                "data_source": "empty_trace",
            }

        stocks = loader.list_a_share_candidates(stock_codes=stock_codes)
        engine = CSBStrategyEngine(loader, cfg)
        data = engine.screen(
            stocks,
            as_of_end_date=effective,
            config=cfg,
            require_entry=require_entry,
            max_results=limit,
        )
        data_source = "realtime"

        # 全市场现算结果回写 trace，便于下次「优先读预计算」命中（含 0 买点日）
        if (
            persist_realtime
            and full_market
            and resolved_id is not None
            and require_entry
        ):
            try:
                if data:
                    upsert_trace_rows(db, config_id=int(resolved_id), rows=data)
                mark_date_scanned(
                    db,
                    config_id=int(resolved_id),
                    trade_date=effective,
                    extra={
                        "hits": len(data),
                        "candidates": len(stocks),
                        "scope": "full_market",
                        "source": "frontend_screen",
                    },
                )
                data_source = "realtime+trace"
            except Exception as e:
                logger.warning("CSB 选股现算回写 trace 失败: %s", e)

        return {
            "success": True,
            "data": data,
            "total": len(data),
            "strategy_name": "CSB通道突破",
            "scope": scope,
            "message": (
                f"全市场现算完成（{effective}），命中 {len(data)} 只"
                + ("，已写入预计算缓存。" if data_source == "realtime+trace" else "。")
            )
            if full_market
            else None,
            "need_precompute": False,
            "search_date": effective,
            "config_id": resolved_id,
            "source": data_source,
            "data_source": data_source,
            "parameters": {
                "config_id": resolved_id,
                "min_score": cfg.get("min_score"),
                "screening_date_effective": effective,
                "data_source": data_source,
            },
        }
