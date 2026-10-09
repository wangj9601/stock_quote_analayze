# -*- coding: utf-8 -*-
"""CSB 策略引擎：单票评估 + 全市场扫描。"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import (
    BUY_SIGNAL_TYPES,
    CSB_BREAKOUT,
    CSB_LPS,
    CSBConfigManager,
    CSB_PROBE,
    CSB_SETUP,
)
from .data_loader import CSBDataLoader, _norm_code, history_calendar_days_for_fetch
from .entry_detector import detect_entry

logger = logging.getLogger(__name__)

ProgressCb = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


def _screen_workers() -> int:
    raw = (os.getenv("CSB_SCREEN_WORKERS") or "").strip()
    if raw.isdigit():
        return max(1, min(16, int(raw)))
    n = os.cpu_count() or 4
    return max(1, min(4, n))


def _hits_for_stock_dates(
    code: str,
    name: str,
    hist_asc: List[Dict[str, Any]],
    dates: List[str],
    cfg: Dict[str, Any],
    *,
    require_entry: bool = True,
) -> List[Dict[str, Any]]:
    """对已拉正序行情，按多个交易日截断评点。"""
    if not hist_asc or not dates:
        return []
    wanted = {str(d)[:10] for d in dates}
    date_to_end: Dict[str, int] = {}
    for i, b in enumerate(hist_asc):
        ds = str(b.get("date") or "")[:10]
        if ds in wanted:
            date_to_end[ds] = i
    min_score = float(cfg.get("min_score") or 0)
    out: List[Dict[str, Any]] = []
    for d in dates:
        end_i = date_to_end.get(str(d)[:10])
        if end_i is None:
            continue
        try:
            sub = hist_asc[: end_i + 1]
            row = evaluate_one(sub, code=code, name=name, trade_date=d, config=cfg)
        except Exception as e:
            logger.debug("CSB range-screen skip %s %s: %s", code, d, e)
            continue
        if not row:
            continue
        if require_entry and not row.get("entry_signal"):
            continue
        if require_entry and float(row.get("score") or 0) < min_score:
            continue
        out.append(row)
    return out


def _filter_screen_row(
    row: Optional[Dict[str, Any]],
    *,
    require_entry: bool,
    require_setup: bool,
    min_score: float,
) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    if require_setup and not row.get("setup_ok"):
        return None
    if require_entry and not row.get("entry_signal"):
        return None
    if require_entry and float(row.get("score") or 0) < min_score:
        return None
    return row


def compute_score_detail(result: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    SETUP/入场质量综合分（0～100）及分项明细。
    分项：粘合天数≤25、≥30日加权、粘合带宽≤15、回踩≤15、地量10、换手10、Spring、PROBE+12 / LPS+16 / BREAKOUT+20。
    """
    pcfg = (config or {}).get("premium") or {}
    ch = result.get("channel") or {}
    sq_days = float(ch.get("squeeze_days") or 0)
    squeeze_days_score = min(25.0, sq_days * 1.2)

    prem_days = float(pcfg.get("squeeze_days_min", 30))
    prem_pts = float(pcfg.get("squeeze_bonus", 8.0))
    squeeze_premium = prem_pts if sq_days >= prem_days else 0.0
    spring_pts = float(pcfg.get("spring_bonus", 6.0)) if result.get("spring_ok") else 0.0

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
    elif signal_type == CSB_LPS:
        entry_bonus = 16.0

    raw = (
        squeeze_days_score
        + squeeze_premium
        + squeeze_pct_score
        + touch_score
        + dry_score
        + turnover_score
        + spring_pts
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
            "squeeze_premium": {
                "score": round(squeeze_premium, 2),
                "max": prem_pts,
                "value": sq_days,
                "formula": f"粘合≥{prem_days:.0f}日 +{prem_pts:.0f}",
            },
            "spring": {
                "score": round(spring_pts, 2),
                "max": float(pcfg.get("spring_bonus", 6.0)),
                "ok": bool(result.get("spring_ok")),
                "formula": "近端出现 Spring +6",
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
                "formula": "PROBE +12 / LPS +16 / BREAKOUT +20",
            },
            "vol_expand": {
                "score": round(vol_bonus, 2),
                "max": 10.0,
                "value": float(vm) if vm is not None else None,
                "formula": "仅 BREAKOUT：min(10, 当日换手/20日均换手)",
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
        "spring_ok", "spring_count", "spring_low",
    )
    entry_keys = (
        "entry_kind", "vol_expand_mult", "expand_basis", "vol_ratio_5_20", "break_line",
        "body_pct", "upper_shadow_ratio", "expand_ok", "shrink_ok",
        "pattern_ok", "body_ok", "shadow_ok", "resistance",
        "near_lower_ok", "spring_today", "distribution_trap",
        "lps_breakout_date", "lps_price", "pullback_ok", "hold_ok", "turn_ok",
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
    pos = cfg.get("position") or {}
    if signal_type == CSB_PROBE:
        row["suggested_position"] = pos.get("probe_pct")
    elif signal_type == CSB_BREAKOUT:
        row["suggested_position"] = pos.get("breakout_add_pct")
    elif signal_type == CSB_LPS:
        row["suggested_position"] = pos.get("lps_add_pct")
    return row


class CSBStrategyEngine:
    def __init__(self, loader: Optional[CSBDataLoader] = None, config: Optional[Dict[str, Any]] = None):
        self.loader = loader or CSBDataLoader()
        self.config_manager = CSBConfigManager()
        self.config = config or self.config_manager.get_default_config()

    def _load_hist_map(
        self,
        stock_rows: List[Tuple[str, str]],
        start_s: str,
        end_s: str,
        *,
        chunk_size: Optional[int] = None,
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        codes = [str(c) for c, _n in stock_rows]
        try:
            return self.loader.load_bars_batch(
                codes,
                start_date=start_s,
                end_date=end_s,
                chunk_size=chunk_size,
            )
        except Exception as e:
            try:
                if getattr(self.loader, "_db", None) is not None:
                    self.loader._db.rollback()
            except Exception:
                pass
            logger.warning("CSB 批量拉行情失败，回退逐股: %s", e)
            return None

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
        progress_cb: Optional[ProgressCb] = None,
        cancel_check: Optional[CancelCheck] = None,
    ) -> List[Dict[str, Any]]:
        """全市场/池扫描：分块批量拉 K + 线程池评点（对齐 URT）。"""
        cfg = config or self.config
        scan = cfg.get("scan") or {}
        if max_results is not None:
            max_n = int(max_results)
        else:
            raw_n = scan.get("max_results")
            try:
                max_n = int(raw_n) if raw_n is not None else 0
            except (TypeError, ValueError):
                max_n = 0
        trade_date = self.loader.resolve_effective_trade_date(as_of_end_date)
        min_score = float(cfg.get("min_score") or 0)
        cal_days = history_calendar_days_for_fetch(cfg)
        start_s, end_s = CSBDataLoader.default_date_window(cal_days, trade_date)
        n_chunk = CSBDataLoader.resolve_hist_batch_chunk_size(
            start_date=start_s, end_date=end_s
        )
        workers = _screen_workers()
        total = len(stocks)
        results: List[Dict[str, Any]] = []

        logger.info(
            "CSB 全市场扫描 stocks=%s window=%s~%s batch_codes=%s workers=%s",
            total,
            start_s,
            end_s,
            n_chunk,
            workers,
        )

        for i in range(0, total, n_chunk):
            if cancel_check and cancel_check():
                break
            chunk = stocks[i : i + n_chunk]
            hist_map = self._load_hist_map(chunk, start_s, end_s, chunk_size=n_chunk)
            jobs: List[Tuple[str, str, List[Dict[str, Any]]]] = []
            for code, name in chunk:
                code_n = _norm_code(code)
                if hist_map is not None:
                    hist = list(hist_map.get(code_n) or hist_map.get(code) or [])
                else:
                    hist = self.loader.load_bars_range(
                        code_n, start_date=start_s, end_date=end_s
                    )
                jobs.append((code_n, str(name or ""), hist))

            def _run_job(item: Tuple[str, str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
                code, name, hist = item
                try:
                    sub = CSBDataLoader.truncate_bars_asof(hist, trade_date)
                    row = evaluate_one(
                        sub, code=code, name=name, trade_date=trade_date, config=cfg
                    )
                    return _filter_screen_row(
                        row,
                        require_entry=require_entry,
                        require_setup=require_setup,
                        min_score=min_score,
                    )
                except Exception as e:
                    logger.debug("CSB evaluate %s failed: %s", code, e)
                    return None

            if workers <= 1 or len(jobs) <= 1:
                chunk_rows = [_run_job(j) for j in jobs]
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    chunk_rows = list(pool.map(_run_job, jobs))
            for row in chunk_rows:
                if row:
                    results.append(row)
            if progress_cb:
                done = min(total, i + len(chunk))
                progress_cb(done, total, f"扫描 {done}/{total}")

        results.sort(
            key=lambda r: (
                1 if r.get("signal_type") == CSB_BREAKOUT else 0,
                1 if r.get("signal_type") == CSB_LPS else 0,
                1 if r.get("signal_type") == CSB_PROBE else 0,
                1 if r.get("setup_ok") else 0,
                float(r.get("score") or 0),
            ),
            reverse=True,
        )
        if max_n > 0:
            return results[:max_n]
        return results

    def screen_universe_for_dates(
        self,
        stocks: List[Tuple[str, str]],
        dates: List[str],
        *,
        require_entry: bool = True,
        require_pass: Optional[bool] = None,
        progress_cb: Optional[ProgressCb] = None,
        cancel_check: Optional[CancelCheck] = None,
        chunk_size: Optional[int] = None,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], bool]:
        """一次拉齐 [最早日-回看, 最晚日] 行情，内存中按日评点（对齐 URT）。

        require_pass：历史别名，等同 require_entry。
        """
        if require_pass is not None:
            require_entry = bool(require_pass)

        date_list = [str(d)[:10] for d in dates if str(d).strip()]
        date_list = list(dict.fromkeys(date_list))
        hits_by_date: Dict[str, List[Dict[str, Any]]] = {d: [] for d in date_list}
        if not stocks or not date_list:
            return hits_by_date, True

        cfg = self.config
        cal_days = history_calendar_days_for_fetch(cfg)
        start_s, _ = CSBDataLoader.default_date_window(cal_days, min(date_list))
        end_s = max(date_list)
        n_chunk = CSBDataLoader.resolve_hist_batch_chunk_size(
            start_date=start_s, end_date=end_s, chunk_size=chunk_size
        )
        workers = _screen_workers()
        total = len(stocks)
        done_stocks = 0

        logger.info(
            "CSB 区间扫描 stocks=%s days=%s window=%s~%s batch_codes=%s workers=%s",
            total,
            len(date_list),
            start_s,
            end_s,
            n_chunk,
            workers,
        )
        if progress_cb:
            progress_cb(0, total, f"区间一次扫描 0/{total} 只（{len(date_list)} 个交易日）")

        for i in range(0, total, n_chunk):
            if cancel_check and cancel_check():
                logger.info("CSB 区间扫描已取消 stocks_done=%s/%s", done_stocks, total)
                return hits_by_date, False
            chunk = stocks[i : i + n_chunk]
            hist_map = self._load_hist_map(chunk, start_s, end_s, chunk_size=n_chunk)
            jobs: List[Tuple[str, str, List[Dict[str, Any]]]] = []
            for code, name in chunk:
                code_n = _norm_code(code)
                if hist_map is not None:
                    hist = list(hist_map.get(code_n) or hist_map.get(code) or [])
                else:
                    try:
                        hist = self.loader.load_bars_range(
                            code_n, start_date=start_s, end_date=end_s
                        )
                    except Exception as e:
                        logger.debug("CSB range fetch skip %s: %s", code_n, e)
                        hist = []
                jobs.append((code_n, str(name or ""), hist))

            def _run_job(item: Tuple[str, str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
                code, name, hist = item
                return _hits_for_stock_dates(
                    code, name, hist, date_list, cfg, require_entry=require_entry
                )

            if workers <= 1 or len(jobs) <= 1:
                chunk_hits = [_run_job(j) for j in jobs]
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    chunk_hits = list(pool.map(_run_job, jobs))
            for hits in chunk_hits:
                for h in hits:
                    d = str(h.get("signal_date") or "")[:10]
                    if d in hits_by_date:
                        hits_by_date[d].append(h)
            done_stocks += len(chunk)
            if progress_cb:
                progress_cb(
                    done_stocks,
                    total,
                    f"区间一次扫描 {done_stocks}/{total} 只（{len(date_list)} 个交易日）",
                )

        for d in date_list:
            hits_by_date[d].sort(key=lambda x: float(x.get("score") or 0), reverse=True)
        return hits_by_date, True
