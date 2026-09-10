# -*- coding: utf-8 -*-
"""CSB 策略引擎：单票评估 + 全市场扫描。"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import (
    BUY_SIGNAL_TYPES,
    CSB_BREAKOUT,
    CSBConfigManager,
    CSB_PROBE,
    CSB_SETUP,
)
from .data_loader import CSBDataLoader, _norm_code
from .entry_detector import detect_entry

logger = logging.getLogger(__name__)


def compute_score_detail(result: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    SETUP/入场质量综合分（0～100）及分项明细。
    分项：粘合天数≤25、粘合带宽≤15、回踩≤15、地量10、换手10、PROBE+12 / BREAKOUT+20(+量能≤10)。
    """
    _ = config  # 预留：分项权重将来可配置
    ch = result.get("channel") or {}
    sq_days = float(ch.get("squeeze_days") or 0)
    squeeze_days_score = min(25.0, sq_days * 1.2)

    sq_pct = ch.get("squeeze_pct")
    if sq_pct is not None:
        squeeze_pct_score = max(0.0, 15.0 * (1.0 - float(sq_pct) / 0.06))
    else:
        squeeze_pct_score = 0.0

    touches = float(result.get("touch_count") or 0)
    touch_score = min(15.0, touches * 4.0)

    dry_ok = bool((result.get("dry_vol") or {}).get("dry_ok"))
    dry_score = 10.0 if dry_ok else 0.0

    turnover_ok = bool(result.get("turnover_ok"))
    turnover_score = 10.0 if turnover_ok else 0.0

    signal_type = result.get("signal_type")
    entry_bonus = 0.0
    vol_bonus = 0.0
    vm = result.get("vol_expand_mult")
    if signal_type == CSB_PROBE:
        entry_bonus = 12.0
    elif signal_type == CSB_BREAKOUT:
        entry_bonus = 20.0
        if vm is not None:
            vol_bonus = min(10.0, float(vm))

    raw = (
        squeeze_days_score
        + squeeze_pct_score
        + touch_score
        + dry_score
        + turnover_score
        + entry_bonus
        + vol_bonus
    )
    total = round(min(100.0, raw), 2)

    return {
        "total": total,
        "parts": {
            "squeeze_days": {
                "score": round(squeeze_days_score, 2),
                "max": 25.0,
                "value": sq_days,
                "formula": "min(25, squeeze_days × 1.2)",
            },
            "squeeze_pct": {
                "score": round(squeeze_pct_score, 2),
                "max": 15.0,
                "value": float(sq_pct) if sq_pct is not None else None,
                "formula": "max(0, 15 × (1 − squeeze_pct / 0.06))",
            },
            "touches": {
                "score": round(touch_score, 2),
                "max": 15.0,
                "value": touches,
                "formula": "min(15, touch_count × 4)",
            },
            "dry_vol": {
                "score": round(dry_score, 2),
                "max": 10.0,
                "ok": dry_ok,
                "formula": "地量成立 +10",
            },
            "turnover": {
                "score": round(turnover_score, 2),
                "max": 10.0,
                "ok": turnover_ok,
                "formula": "20日均换手达标 +10",
            },
            "entry_type": {
                "score": round(entry_bonus, 2),
                "max": 20.0,
                "signal_type": signal_type,
                "formula": "PROBE +12 / BREAKOUT +20",
            },
            "vol_expand": {
                "score": round(vol_bonus, 2),
                "max": 10.0,
                "value": float(vm) if vm is not None else None,
                "formula": "仅 BREAKOUT：min(10, vol_expand_mult)",
            },
        },
    }


def compute_score(result: Dict[str, Any], config: Dict[str, Any]) -> float:
    """SETUP/入场质量综合分（0～100）。"""
    return float(compute_score_detail(result, config).get("total") or 0.0)


def evaluate_one(
    bars: List[Dict[str, Any]],
    *,
    code: str = "",
    name: str = "",
    trade_date: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    纯函数友好：给定正序 bars 评估 CSB 信号。
    """
    cfg = config or CSBConfigManager().get_default_config()
    min_bars = int(cfg.get("min_listing_bars") or 250)
    if len(bars) < min_bars:
        return None

    entry = detect_entry(bars, cfg)
    td = trade_date or (str(bars[-1].get("date") or "")[:10] if bars else "")
    signal_type = entry.get("signal_type")
    if not signal_type and entry.get("setup_ok"):
        signal_type = CSB_SETUP

    # 入场评估时 entry.signal_type 可能尚未落到 SETUP；评分按最终展示类型一致
    score_entry = dict(entry)
    score_entry["signal_type"] = signal_type
    score_detail = compute_score_detail(score_entry, cfg)

    setup_keys = (
        "reason", "turnover_avg_20", "turnover_ok", "touch_count",
        "touch_ok", "ma250", "dry_vol", "channel", "setup_ok",
    )
    entry_keys = (
        "entry_kind", "vol_expand_mult", "vol_ratio_5_20", "break_line",
        "body_pct", "upper_shadow_ratio", "expand_ok", "shrink_ok",
        "pattern_ok", "body_ok", "shadow_ok", "resistance",
        "probe_price", "breakout_price",
    )
    row: Dict[str, Any] = {
        "code": _norm_code(code),
        "name": name,
        "trade_date": td,
        "signal_date": td,
        "date": td,
        "signal_type": signal_type,
        "setup_ok": bool(entry.get("setup_ok")),
        "entry_signal": bool(entry.get("entry_signal")),
        "entry_kind": entry.get("entry_kind"),
        "close": entry.get("channel", {}).get("close"),
        "channel_lower": entry.get("channel", {}).get("lower"),
        "channel_upper": entry.get("channel", {}).get("upper"),
        "squeeze_days": entry.get("channel", {}).get("squeeze_days"),
        "squeeze_pct": entry.get("channel", {}).get("squeeze_pct"),
        "hh20": entry.get("channel", {}).get("hh20"),
        "resistance": entry.get("channel", {}).get("resistance") or entry.get("resistance"),
        "touch_count": entry.get("touch_count"),
        "entry_low": entry.get("entry_low"),
        "vol_expand_mult": entry.get("vol_expand_mult"),
        "vol_ratio_5_20": entry.get("vol_ratio_5_20"),
        "score_detail": score_detail,
        "detail": {
            "setup": {k: entry.get(k) for k in setup_keys if entry.get(k) is not None},
            "entry": {k: entry.get(k) for k in entry_keys if entry.get(k) is not None},
            "score": score_detail,
        },
    }
    row["score"] = float(score_detail.get("total") or 0.0)
    row["buy_signal"] = signal_type in BUY_SIGNAL_TYPES
    return row


class CSBStrategyEngine:
    def __init__(self, loader: Optional[CSBDataLoader] = None, config: Optional[Dict[str, Any]] = None):
        self.loader = loader or CSBDataLoader()
        self.config_manager = CSBConfigManager()
        self.config = config or self.config_manager.get_default_config()

    def evaluate_code(
        self,
        code: str,
        *,
        name: str = "",
        date: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        bars: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        cfg = config or self.config
        scan = cfg.get("scan") or {}
        hist_n = int(scan.get("history_bars", 280))
        code_n = _norm_code(code)
        asof = str(date)[:10] if date else None
        if asof:
            asof = self.loader.resolve_effective_trade_date(asof)

        if bars is not None:
            bars_full = CSBDataLoader.truncate_bars_asof(list(bars), asof)
        else:
            bars_full = self.loader.load_bars(code_n, end_date=asof, limit=hist_n)
            bars_full = CSBDataLoader.truncate_bars_asof(bars_full, asof)

        if len(bars_full) < int(cfg.get("min_listing_bars") or 250):
            return None

        if not name:
            candidates = self.loader.list_a_share_candidates(stock_codes=[code_n])
            name = candidates[0][1] if candidates else ""

        return evaluate_one(
            bars_full,
            code=code_n,
            name=name,
            trade_date=asof or bars_full[-1]["date"],
            config=cfg,
        )

    def screen(
        self,
        stocks: List[Tuple[str, str]],
        *,
        as_of_end_date: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        require_entry: bool = False,
        require_setup: bool = False,
        max_results: Optional[int] = None,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[Dict[str, Any]]:
        cfg = config or self.config
        scan = cfg.get("scan") or {}
        max_n = max_results if max_results is not None else int(scan.get("max_results", 200))
        trade_date = self.loader.resolve_effective_trade_date(as_of_end_date)

        results: List[Dict[str, Any]] = []
        total = len(stocks)
        for i, (code, name) in enumerate(stocks):
            if cancel_check and cancel_check():
                break
            if progress_cb and (i % 20 == 0 or i == total - 1):
                progress_cb(i + 1, total, f"扫描 {code}")
            try:
                row = self.evaluate_code(code, name=name, date=trade_date, config=cfg)
                if not row:
                    continue
                if require_setup and not row.get("setup_ok"):
                    continue
                if require_entry and not row.get("entry_signal"):
                    continue
                min_score = float(cfg.get("min_score") or 0)
                if require_entry and float(row.get("score") or 0) < min_score:
                    continue
                results.append(row)
            except Exception as e:
                logger.debug("CSB evaluate %s failed: %s", code, e)
        results.sort(
            key=lambda r: (
                1 if r.get("signal_type") == CSB_BREAKOUT else 0,
                1 if r.get("signal_type") == CSB_PROBE else 0,
                1 if r.get("setup_ok") else 0,
                float(r.get("score") or 0),
            ),
            reverse=True,
        )
        return results[:max_n]

    def screen_universe_for_dates(
        self,
        stocks: List[Tuple[str, str]],
        dates: List[str],
        *,
        require_entry: bool = True,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], bool]:
        """按多个交易日扫描（每只股票拉一次 K 线，按日截断）。"""
        hits_by_date: Dict[str, List[Dict[str, Any]]] = {d: [] for d in dates}
        scan = self.config.get("scan") or {}
        hist_n = int(scan.get("history_bars", 280))
        total = len(stocks)
        completed = True

        for si, (code, name) in enumerate(stocks):
            if cancel_check and cancel_check():
                completed = False
                break
            if progress_cb and (si % 10 == 0 or si == total - 1):
                progress_cb(si + 1, total, f"加载 {code}")
            bars_all = self.loader.load_bars(code, limit=hist_n + len(dates) + 5)
            for d in dates:
                sub = CSBDataLoader.truncate_bars_asof(bars_all, d)
                row = evaluate_one(sub, code=code, name=name, trade_date=d, config=self.config)
                if not row:
                    continue
                if require_entry and not row.get("entry_signal"):
                    continue
                if float(row.get("score") or 0) < float(self.config.get("min_score") or 0):
                    continue
                hits_by_date.setdefault(d, []).append(row)
        return hits_by_date, completed
