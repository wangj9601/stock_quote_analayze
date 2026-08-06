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
    ) -> Optional[Dict[str, Any]]:
        cfg = config or self.config
        scan_cfg = cfg.get("scan") or {}
        code_n = _norm_code(code)
        hist_n = int(scan_cfg.get("history_bars", 120))
        load_n = max(hist_n, kde_bars_limit(cfg))
        bars_full = self.loader.load_bars(code_n, end_date=date, limit=load_n)
        if len(bars_full) < 30:
            return None
        bars = _bars_for_strategy(bars_full, hist_n)

        close = bars[-1]["close"]
        info = share_info or self.loader.load_share_map([code_n], as_of_date=date).get(code_n) or {}
        size = evaluate_size(
            total_shares=info.get("total_shares"),
            free_float_shares=info.get("free_float_shares"),
            close=close,
            config=cfg,
        )

        mrets = market_returns
        if mrets is None:
            mrets = self.loader.load_market_returns(end_date=date or bars[-1]["date"])

        bottom = detect_bottom(bars, mrets, cfg)
        entry = detect_entry(bars, mrets, bottom_matched=bool(bottom.get("matched")), config=cfg)

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

        trade_date = date or bars[-1]["date"]
        return {
            "code": code_n,
            "symbol": code_n,
            "name": info.get("name"),
            "date": trade_date,
            "market_type": "CN",
            "close": close,
            "total_mv": size.get("total_mv"),
            "circ_mv": size.get("circ_mv"),
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
            "detail": {
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
                "structure": {
                    "nearest_support": structure.get("nearest_support"),
                    "nearest_resistance": structure.get("nearest_resistance"),
                    "kde_ok": structure.get("kde_ok"),
                    "kde_reason": structure.get("kde_reason"),
                    "kde_lookback_used": structure.get("kde_lookback_used"),
                },
            },
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
        bars_full = self.loader.load_bars(code_n, end_date=date, limit=load_n)
        if not bars_full:
            return {"ok": False, "reason": "no_bars"}
        bars = _bars_for_strategy(bars_full, hist_n)

        info = self.loader.load_share_map([code_n], as_of_date=date or bars_full[-1]["date"]).get(code_n) or {}
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

        mrets = self.loader.load_market_returns(end_date=date or bars_full[-1]["date"])
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
            "date": bars_full[-1]["date"],
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

        trade_date = date or self.loader.resolve_trade_date()
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
