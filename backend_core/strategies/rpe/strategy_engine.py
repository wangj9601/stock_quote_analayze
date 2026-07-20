"""RPE 策略引擎。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .config import RPEConfigManager
from .data_loader import RPEDataLoader, _norm_code
from .filters import liquidity_ok, structure_break, structure_filter, trend_veto
from .kde_levels import extract_kde_levels, nearest_levels
from .sector_benchmark import compute_vwap_benchmark, sector_slope
from .signal_detector import detect_signal
from .trade_structure_plan import build_structure_plan
from .zscore import latest_zscore

logger = logging.getLogger(__name__)


class RPEStrategyEngine:
    def __init__(self, db_session=None, config: Optional[Dict] = None):
        self.loader = RPEDataLoader(db_session)
        self.config_manager = RPEConfigManager()
        self.config = config or self.config_manager.get_config()

    def evaluate_in_sector(
        self,
        code: str,
        *,
        sector_id: str,
        sector_name: str,
        panel: Dict[str, List[Dict[str, Any]]],
        benchmark: List[Dict[str, float]],
        slope: Optional[float],
        trade_date: str,
        config: Optional[Dict] = None,
        name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        cfg = config or self.config
        code_n = _norm_code(code)
        bars = panel.get(code_n)
        if not bars or len(bars) < int(cfg.get("z_window", 40)) + 5:
            return None

        closes_map = {b["date"]: b["close"] for b in bars}
        zinfo = latest_zscore(closes_map, benchmark, int(cfg.get("z_window", 40)))
        if not zinfo:
            return None

        # 若评估日不是最新 bar，截断
        if trade_date and bars[-1]["date"] > trade_date:
            bars = [b for b in bars if b["date"] <= trade_date]
            if not bars:
                return None
            closes_map = {b["date"]: b["close"] for b in bars}
            zinfo = latest_zscore(closes_map, benchmark, int(cfg.get("z_window", 40)))
            if not zinfo:
                return None

        kde = extract_kde_levels(
            [b["close"] for b in bars],
            [b["volume"] for b in bars],
            base_factor=float(cfg.get("kde_base_factor", 1.0)),
            grid_points=int(cfg.get("kde_grid_points", 200)),
        )
        price = float(zinfo["price"])
        near = nearest_levels(price, kde.get("support_levels") or [], kde.get("resistance_levels") or [])
        struct = structure_filter(
            price,
            near.get("nearest_support"),
            near.get("nearest_resistance"),
            min_rr=float(cfg.get("min_rr_to_resistance", 1.5)),
        )
        liq_cfg = cfg.get("liquidity") or {}
        liq = liquidity_ok(
            bars,
            lookback=int(liq_cfg.get("lookback_days", 20)),
            min_avg_amount=float(liq_cfg.get("min_avg_amount", 5_000_000)),
            min_avg_turnover_rate=float(liq_cfg.get("min_avg_turnover_rate", 0.5)),
        )
        sig = detect_signal(
            z_score=zinfo.get("z_score"),
            sector_slope=slope,
            structure_valid=bool(struct.get("structure_valid")),
            liquidity_ok=bool(liq.get("liquidity_ok")),
            config=cfg,
        )
        plan = build_structure_plan(
            entry_price=price,
            nearest_support=near.get("nearest_support"),
            nearest_resistance=near.get("nearest_resistance"),
        )
        return {
            "code": code_n,
            "symbol": code_n,
            "name": name,
            "date": zinfo.get("date") or trade_date,
            "market_type": "CN",
            "sector_id": sector_id,
            "sector_name": sector_name,
            "z_score": zinfo.get("z_score"),
            "ratio": zinfo.get("ratio"),
            "close": price,
            "sector_slope": slope,
            "signal_type": sig.get("signal_type"),
            "entry_signal": bool(sig.get("entry_signal")),
            "watch_only": bool(sig.get("watch_only")),
            "trend_veto": bool(sig.get("trend_veto")),
            "support_levels": kde.get("support_levels") or [],
            "resistance_levels": kde.get("resistance_levels") or [],
            "nearest_support": near.get("nearest_support"),
            "nearest_resistance": near.get("nearest_resistance"),
            "structure_valid": bool(struct.get("structure_valid")),
            "liquidity_ok": bool(liq.get("liquidity_ok")),
            "structure_plan": plan,
            "detail": {
                "signal_reason": sig.get("reason"),
                "structure": struct,
                "liquidity": liq,
                "kde_reason": kde.get("reason"),
                "bw": kde.get("bw"),
                "i_t": zinfo.get("i_t"),
            },
        }

    def evaluate_position(
        self,
        code: str,
        *,
        structure_support: Optional[float],
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        bars = self.loader.load_bars(code, end_date=date, limit=30)
        if not bars:
            return {"ok": False, "reason": "no_bars"}
        close = bars[-1]["close"]
        breached = structure_break(close, structure_support)
        return {
            "ok": True,
            "code": _norm_code(code),
            "date": bars[-1]["date"],
            "close": close,
            "structure_support": structure_support,
            "structure_break": breached,
        }

    def screen_board(
        self,
        board_code: str,
        board_name: str,
        *,
        date: Optional[str] = None,
        config: Optional[Dict] = None,
        entry_only: bool = False,
    ) -> List[Dict[str, Any]]:
        cfg = config or self.config
        lookback = int(cfg.get("lookback_days", 250))
        min_members = int((cfg.get("scan") or {}).get("min_sector_members", 5))
        members = self.loader.load_board_members(board_code)
        if len(members) < min_members:
            return []
        codes = [m["code"] for m in members]
        name_map = {m["code"]: m.get("name") for m in members}
        panel = self.loader.load_sector_panel(codes, end_date=date, lookback=lookback)
        if len(panel) < min_members:
            return []
        date_members = self.loader.build_date_members(panel)
        benchmark = compute_vwap_benchmark(date_members)
        if len(benchmark) < int(cfg.get("z_window", 40)) + 5:
            return []
        slope = sector_slope(benchmark, int(cfg.get("sector_slope_window", 60)))
        trade_date = date or (benchmark[-1]["date"] if benchmark else self.loader.resolve_trade_date())

        results = []
        for code in panel.keys():
            try:
                row = self.evaluate_in_sector(
                    code,
                    sector_id=board_code,
                    sector_name=board_name,
                    panel=panel,
                    benchmark=benchmark,
                    slope=slope,
                    trade_date=trade_date,
                    config=cfg,
                    name=name_map.get(code),
                )
                if not row:
                    continue
                if entry_only and not row.get("entry_signal"):
                    continue
                # 至少有信号类型或观察价值
                if not row.get("signal_type") and not row.get("entry_signal"):
                    continue
                results.append(row)
            except Exception as e:
                logger.debug("RPE evaluate %s in %s failed: %s", code, board_code, e)
        return results

    def screen(
        self,
        *,
        date: Optional[str] = None,
        config: Optional[Dict] = None,
        board_codes: Optional[List[str]] = None,
        codes: Optional[List[str]] = None,
        entry_only: bool = False,
        signal_type: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        cfg = config or self.config
        scan = cfg.get("scan") or {}
        max_n = max_results if max_results is not None else int(scan.get("max_results", 200))
        trade_date = date or self.loader.resolve_trade_date()

        boards: List[Dict[str, str]]
        if board_codes:
            all_boards = {b["board_code"]: b for b in self.loader.list_industry_boards()}
            boards = []
            for bc in board_codes:
                b = all_boards.get(bc) or {"board_code": bc, "board_name": bc}
                boards.append(b)
        elif codes:
            # 自选/单股：收集涉及板块
            seen = {}
            for c in codes:
                for b in self.loader.find_boards_for_code(c):
                    seen[b["board_code"]] = b
            boards = list(seen.values())
        else:
            boards = self.loader.list_industry_boards(limit=scan.get("max_boards"))

        code_filter = {_norm_code(c) for c in codes} if codes else None
        results: List[Dict[str, Any]] = []
        for b in boards:
            rows = self.screen_board(
                b["board_code"],
                b.get("board_name") or b["board_code"],
                date=trade_date,
                config=cfg,
                entry_only=False,
            )
            for r in rows:
                if code_filter is not None and r["code"] not in code_filter:
                    continue
                if entry_only and not r.get("entry_signal"):
                    continue
                if signal_type and r.get("signal_type") != signal_type:
                    continue
                results.append(r)

        results.sort(
            key=lambda r: (
                1 if r.get("entry_signal") else 0,
                1 if r.get("signal_type") == "catch_up" else 0,
                -(abs(r.get("z_score") or 0)),
            ),
            reverse=True,
        )
        # 同股多板块去重：保留 |z| 最大
        dedup: Dict[str, Dict] = {}
        for r in results:
            prev = dedup.get(r["code"])
            if prev is None or abs(r.get("z_score") or 0) > abs(prev.get("z_score") or 0):
                dedup[r["code"]] = r
        out = list(dedup.values())
        out.sort(
            key=lambda r: (
                1 if r.get("entry_signal") else 0,
                1 if r.get("signal_type") == "catch_up" else 0,
                -(abs(r.get("z_score") or 0)),
            ),
            reverse=True,
        )
        return out[:max_n]
