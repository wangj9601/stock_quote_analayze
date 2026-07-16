"""SBBR 策略引擎：单票评估 + 全市场扫描。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .bottom_detector import detect_bottom
from .config import SBBRConfigManager
from .data_loader import SBBRDataLoader, _norm_code
from .defense_exit import calc_defense_band, check_defense_breach, evaluate_exit_factors
from .entry_detector import detect_entry
from .position_advisor import advise_position
from .size_filter import evaluate_size

logger = logging.getLogger(__name__)


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
        bars = self.loader.load_bars(code_n, end_date=date, limit=int(scan_cfg.get("history_bars", 120)))
        if len(bars) < 30:
            return None

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

        pos = advise_position(
            current_stage=None,
            allocated_pct=0,
            open_positions=0,
            total_capital=None,
            has_new_support=bool(bottom.get("matched")),
            config=cfg,
        )

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
                "support": bottom.get("support"),
                "resistance": bottom.get("resistance"),
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
        bars = self.loader.load_bars(code, end_date=date, limit=120)
        if not bars:
            return {"ok": False, "reason": "no_bars"}

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

        breach = check_defense_breach(bars, float(band["defense_low"]))
        exit_info = evaluate_exit_factors(bars, entry_price=float(entry_price), config=cfg)
        pos = advise_position(
            current_stage=stage,
            allocated_pct=allocated_pct,
            open_positions=open_positions,
            total_capital=None,
            has_new_support=not breach.get("breached"),
            config=cfg,
        )
        return {
            "ok": True,
            "code": _norm_code(code),
            "date": bars[-1]["date"],
            "close": bars[-1]["close"],
            "defense": band,
            "defense_breach": breach,
            "exit_flags": exit_info,
            "position_advice": pos,
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
