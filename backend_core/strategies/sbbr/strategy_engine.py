"""SBBR 策略引擎：单票评估 + 全市场扫描。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend_core.strategies.gms.structure_levels import (
    compute_structure_levels,
    empty_structure,
    kde_bars_limit,
)

from .bottom_detector import detect_bottom
from .config import SBBRConfigManager
from .data_loader import SBBRDataLoader, _norm_code
from .defense_exit import calc_defense_band, check_defense_breach, evaluate_exit_factors
from .entry_detector import detect_entry
from .position_advisor import advise_position
from .size_filter import evaluate_size
from .support_confirm import evaluate_support_confirm

logger = logging.getLogger(__name__)


def _find_entry_idx(bars: List[Dict[str, Any]], entry_date: Optional[str]) -> Optional[int]:
    if not entry_date or not bars:
        return None
    ed = str(entry_date)[:10]
    for i, b in enumerate(bars):
        if str(b.get("date") or "")[:10] == ed:
            return i
    # 找不到精确日：取首个 >= entry_date 的 bar
    for i, b in enumerate(bars):
        if str(b.get("date") or "")[:10] >= ed:
            return i
    return None


def _bars_for_strategy(bars: List[Dict[str, Any]], history_bars: int) -> List[Dict[str, Any]]:
    """筑底/入场仍用较短窗口，避免过长历史改变横盘振幅语义。"""
    n = max(int(history_bars or 120), 30)
    if len(bars) <= n:
        return bars
    return bars[-n:]


class SBBRStrategyEngine:
    def __init__(self, db_session=None, config: Optional[Dict] = None):
        self.loader = SBBRDataLoader(db_session)
        self.config_manager = SBBRConfigManager()
        self.config = config or self.config_manager.get_config()

    def evaluate_code(
        self,
        code: str,
        *,
        date: Optional[str] = None,
        config: Optional[Dict] = None,
        share_info: Optional[Dict] = None,
        market_returns: Optional[List[float]] = None,
        bars: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        cfg = config or self.config
        scan_cfg = cfg.get("scan") or {}
        code_n = _norm_code(code)
        hist_n = int(scan_cfg.get("history_bars", 120))
        load_n = max(hist_n, kde_bars_limit(cfg))
        # date 由调用方（screen/API）对齐为有效交易日；此处仅按 asof 截断 K 线
        asof = (str(date)[:10] if date else None)
        if bars is not None:
            bars_full = SBBRDataLoader.truncate_bars_asof(list(bars), asof)
        else:
            bars_full = self.loader.load_bars(code_n, end_date=asof, limit=load_n)
            bars_full = SBBRDataLoader.truncate_bars_asof(bars_full, asof)
        if len(bars_full) < 30:
            return None
        bars_win = _bars_for_strategy(bars_full, hist_n)

        close = bars_win[-1]["close"]
        info = share_info or self.loader.load_share_map([code_n], as_of_date=asof).get(code_n) or {}
        size = evaluate_size(
            total_shares=info.get("total_shares"),
            free_float_shares=info.get("free_float_shares"),
            close=close,
            config=cfg,
        )

        mrets = market_returns
        if mrets is None:
            mrets = self.loader.load_market_returns(end_date=asof or bars_win[-1]["date"])

        bottom = detect_bottom(bars_win, mrets, cfg)
        entry = detect_entry(bars_win, mrets, bottom_matched=bool(bottom.get("matched")), config=cfg)

        defense = None
        if entry.get("entry_signal") and entry.get("entry_low"):
            defense = calc_defense_band(float(entry["entry_low"]), cfg)

        # 选股日仅试探建议，不因筑底命中误触发加仓
        pos = advise_position(
            current_stage=None,
            allocated_pct=0,
            open_positions=0,
            total_capital=None,
            has_new_support=False,
            config=cfg,
        )

        bars_desc = list(reversed(bars_full))
        structure = compute_structure_levels(bars_desc, cfg, price=close) or empty_structure()
        box_support = bottom.get("support")
        box_resistance = bottom.get("resistance")

        trade_date = asof or bars_win[-1]["date"]
        detail = {
            "bottom": bottom.get("detail"),
            "entry": {
                k: entry.get(k)
                for k in (
                    "reason",
                    "cross_up",
                    "shrink_ok",
                    "expand_ok",
                    "market_ok",
                    "volume_ratio",
                )
            },
            "support": box_support,
            "resistance": box_resistance,
            "circ_shares_yi": size.get("circ_shares_yi"),
            "structure": {
                "nearest_support": structure.get("nearest_support"),
                "nearest_resistance": structure.get("nearest_resistance"),
                "kde_ok": structure.get("kde_ok"),
                "kde_reason": structure.get("kde_reason"),
                "kde_lookback_used": structure.get("kde_lookback_used"),
            },
            "asof_date": trade_date,
            "bar_end_date": bars_win[-1]["date"],
        }
        return {
            "code": code_n,
            "symbol": code_n,
            "name": info.get("name"),
            "date": trade_date,
            "market_type": "CN",
            "close": close,
            "total_mv": size.get("total_mv"),
            "circ_mv": size.get("circ_mv"),
            "circ_shares_yi": size.get("circ_shares_yi"),
            "size_ok": size.get("size_ok"),
            "size_reason": size.get("size_reason"),
            "bottom_mode": bottom.get("mode"),
            "bottom_matched": bool(bottom.get("matched")),
            "entry_signal": bool(entry.get("entry_signal")),
            "entry_low": entry.get("entry_low"),
            "defense_low": (defense or {}).get("defense_low"),
            "defense_high": (defense or {}).get("defense_high"),
            "defense_buffer_pct": (defense or {}).get("buffer_pct"),
            "ma20": entry.get("ma20"),
            "volume_ratio": entry.get("volume_ratio"),
            "box_support": box_support,
            "box_resistance": box_resistance,
            "nearest_support": structure.get("nearest_support"),
            "nearest_resistance": structure.get("nearest_resistance"),
            "kde_ok": structure.get("kde_ok"),
            "kde_reason": structure.get("kde_reason"),
            "kde_lookback_used": structure.get("kde_lookback_used"),
            "position_advice": pos,
            "exit_flags": {},
            "detail": detail,
        }

    @staticmethod
    def _calendar_days_span(start_s: str, end_s: str) -> int:
        from datetime import datetime as _dt

        a = _dt.strptime(start_s[:10], "%Y-%m-%d").date()
        b = _dt.strptime(end_s[:10], "%Y-%m-%d").date()
        return abs((b - a).days)

    def evaluate_history(
        self,
        code: str,
        *,
        start_date: str,
        end_date: str,
        config: Optional[Dict] = None,
        entry_only: bool = False,
        require_bottom: bool = False,
        require_size: bool = False,
        max_calendar_days: int = 180,
        max_trade_days: int = 120,
    ) -> Dict[str, Any]:
        """
        单股按交易日序列做 asof 回溯（仅用 ≤ 当日 K 线）。

        一次拉齐窗口内行情与大盘收益，按日截断计算，控制跨度上限以保护性能。
        """
        cfg = config or self.config
        scan_cfg = cfg.get("scan") or {}
        code_n = _norm_code(code)
        start_s = str(start_date)[:10]
        end_s = str(end_date)[:10]
        if start_s > end_s:
            raise ValueError("开始日期不能晚于结束日期")
        span = self._calendar_days_span(start_s, end_s)
        if span > int(max_calendar_days):
            raise ValueError(f"日期跨度不得超过 {int(max_calendar_days)} 个自然日（当前 {span}）")

        hist_n = int(scan_cfg.get("history_bars", 120))
        load_n = max(hist_n, kde_bars_limit(cfg)) + int(max_trade_days) + 5
        end_eff = self.loader.resolve_effective_trade_date(end_s)
        bars_all = self.loader.load_bars(code_n, end_date=end_eff, limit=load_n)
        bars_all = SBBRDataLoader.truncate_bars_asof(bars_all, end_eff)
        trade_dates = [b["date"] for b in bars_all if start_s <= b["date"] <= end_eff]
        if len(trade_dates) > int(max_trade_days):
            trade_dates = trade_dates[-int(max_trade_days) :]

        # 大盘收益：带日期，按 asof 切片，避免按日重复查库
        mkt_lookback = max(80, int(((cfg.get("entry") or {}).get("market_lookback_days") or 5)) + 20)
        idx_bars = self.loader.load_bars(
            "000001",
            end_date=end_eff,
            limit=load_n + mkt_lookback,
        )
        idx_bars = SBBRDataLoader.truncate_bars_asof(idx_bars, end_eff)
        dated_mrets: List[tuple] = []
        for i in range(1, len(idx_bars)):
            p0 = float(idx_bars[i - 1].get("close") or 0)
            p1 = float(idx_bars[i].get("close") or 0)
            ret = (p1 - p0) / p0 if p0 > 0 else 0.0
            dated_mrets.append((idx_bars[i]["date"], ret))

        share_info = self.loader.load_share_map([code_n], as_of_date=end_eff).get(code_n) or {}

        rows: List[Dict[str, Any]] = []
        for d in trade_dates:
            mrets = [r for dd, r in dated_mrets if dd <= d][-mkt_lookback:]
            row = self.evaluate_code(
                code_n,
                date=d,
                config=cfg,
                share_info=share_info,
                market_returns=mrets,
                bars=bars_all,
            )
            if not row:
                continue
            # 结果日期以实际 bar 末日为准（与选股 asof 对齐一致）
            row["date"] = d
            if row.get("detail") and isinstance(row["detail"], dict):
                row["detail"] = dict(row["detail"])
                row["detail"]["asof_date"] = d
            if require_size and not row.get("size_ok"):
                continue
            if require_bottom and not row.get("bottom_matched"):
                continue
            if entry_only and not row.get("entry_signal"):
                continue
            rows.append(row)

        rows.sort(key=lambda r: r.get("date") or "", reverse=True)
        return {
            "code": code_n,
            "start_date": start_s,
            "end_date": end_s,
            "end_date_effective": end_eff,
            "trade_days": len(trade_dates),
            "calendar_span_days": span,
            "data": rows,
            "total": len(rows),
            "source": "live",
            "source_label": "实时回溯",
        }

    def evaluate_position(
        self,
        code: str,
        *,
        entry_price: float,
        entry_date: Optional[str],
        defense_anchor_low: Optional[float],
        defense_buffer_pct: Optional[float],
        stage: Optional[str],
        allocated_pct: float,
        open_positions: int,
        date: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        cfg = config or self.config
        scan_cfg = cfg.get("scan") or {}
        hist_n = int(scan_cfg.get("history_bars", 120))
        load_n = max(hist_n, kde_bars_limit(cfg))
        code_n = _norm_code(code)
        asof = (str(date)[:10] if date else None)
        if asof:
            asof = self.loader.resolve_effective_trade_date(asof)
        bars_full = self.loader.load_bars(code_n, end_date=asof, limit=load_n)
        bars_full = SBBRDataLoader.truncate_bars_asof(bars_full, asof)
        if not bars_full:
            return {"ok": False, "reason": "no_bars"}
        bars = _bars_for_strategy(bars_full, hist_n)

        info = self.loader.load_share_map([code_n], as_of_date=asof or bars_full[-1]["date"]).get(code_n) or {}
        free_float = info.get("free_float_shares")

        if defense_anchor_low:
            band = calc_defense_band(float(defense_anchor_low), cfg)
            if defense_buffer_pct is not None:
                buf = float(defense_buffer_pct)
                band = {
                    "defense_low": float(defense_anchor_low) * (1.0 - buf),
                    "defense_high": float(defense_anchor_low),
                    "buffer_pct": buf,
                }
        else:
            band = {"defense_low": 0.0, "defense_high": 0.0, "buffer_pct": 0.03}

        breach = check_defense_breach(bars_full, float(band["defense_low"]))
        entry_idx = _find_entry_idx(bars_full, entry_date)
        exit_info = evaluate_exit_factors(
            bars_full,
            entry_price=float(entry_price),
            entry_idx=entry_idx,
            free_float_shares=free_float,
            config=cfg,
        )

        mrets = self.loader.load_market_returns(end_date=asof or bars_full[-1]["date"])
        bottom = detect_bottom(bars, mrets, cfg)
        box_support = bottom.get("support")
        box_resistance = bottom.get("resistance")

        close = float(bars_full[-1]["close"])
        bars_desc = list(reversed(bars_full))
        structure = compute_structure_levels(bars_desc, cfg, price=close) or empty_structure()

        support_confirm = evaluate_support_confirm(
            close=close,
            defense_low=float(band["defense_low"]),
            defense_breached=bool(breach.get("breached")),
            nearest_support=structure.get("nearest_support"),
            kde_ok=bool(structure.get("kde_ok")),
            box_resistance=box_resistance,
            bars=bars_full,
            config=cfg,
        )

        pos = advise_position(
            current_stage=stage,
            allocated_pct=allocated_pct,
            open_positions=open_positions,
            total_capital=None,
            has_new_support=bool(support_confirm.get("confirmed")),
            config=cfg,
        )
        return {
            "ok": True,
            "code": code_n,
            "date": asof or bars_full[-1]["date"],
            "close": close,
            "defense": band,
            "defense_breach": breach,
            "exit_flags": exit_info,
            "position_advice": pos,
            "box_support": box_support,
            "box_resistance": box_resistance,
            "nearest_support": structure.get("nearest_support"),
            "nearest_resistance": structure.get("nearest_resistance"),
            "kde_ok": structure.get("kde_ok"),
            "kde_reason": structure.get("kde_reason"),
            "kde_lookback_used": structure.get("kde_lookback_used"),
            "support_confirm": support_confirm,
        }

    def screen(
        self,
        codes: Optional[List[str]] = None,
        *,
        date: Optional[str] = None,
        config: Optional[Dict] = None,
        require_entry: bool = False,
        require_size: bool = True,
        require_bottom: bool = False,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        cfg = config or self.config
        scan_cfg = cfg.get("scan") or {}
        max_n = max_results if max_results is not None else int(scan_cfg.get("max_results", 200))

        requested = (str(date)[:10] if date else None)
        trade_date = self.loader.resolve_effective_trade_date(requested)
        market_returns = self.loader.load_market_returns(end_date=trade_date)

        if codes:
            universe_infos = self.loader.load_share_map(codes, as_of_date=trade_date)
            code_list = [_norm_code(c) for c in codes]
        else:
            universe = self.loader.build_size_universe(cfg, trade_date=trade_date)
            universe_infos = {u["code"]: u for u in universe}
            code_list = list(universe_infos.keys())

        results: List[Dict[str, Any]] = []
        for code in code_list:
            try:
                info = universe_infos.get(_norm_code(code))
                row = self.evaluate_code(
                    code,
                    date=trade_date,
                    config=cfg,
                    share_info=info,
                    market_returns=market_returns,
                )
                if not row:
                    continue
                if require_size and not row.get("size_ok"):
                    continue
                if require_bottom and not row.get("bottom_matched"):
                    continue
                if require_entry and not row.get("entry_signal"):
                    continue
                results.append(row)
            except Exception as e:
                logger.debug("SBBR evaluate %s failed: %s", code, e)
                continue

        # 优先入场信号，其次筑底
        results.sort(
            key=lambda r: (
                1 if r.get("entry_signal") else 0,
                1 if r.get("bottom_matched") else 0,
                -(r.get("volume_ratio") or 0),
            ),
            reverse=True,
        )
        return results[:max_n]
