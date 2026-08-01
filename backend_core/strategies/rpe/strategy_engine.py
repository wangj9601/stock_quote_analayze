"""RPE 策略引擎。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .config import RPEConfigManager
from .data_loader import RPEDataLoader, _norm_code
from .filters import liquidity_ok, structure_break, structure_filter, trend_veto
from .kde_levels import (
    KDE_LOOKBACK_MAX,
    extract_kde_levels_expand_support,
    nearest_levels,
)
from .sector_benchmark import compute_vwap_benchmark, sector_slope
from .signal_detector import detect_signal
from .trade_structure_plan import build_structure_plan
from .zscore import latest_zscore

logger = logging.getLogger(__name__)


def _bars_for_lookback(bars: List[Dict[str, Any]], lookback: int) -> List[Dict[str, Any]]:
    """评估用 K 线截断到 lookback（与日终选股一致，避免全历史 KDE 带宽过大）。"""
    n = max(1, int(lookback))
    if not bars or len(bars) <= n:
        return bars
    return bars[-n:]


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
        min_need = int(cfg.get("z_window", 40)) + 5
        if not bars or len(bars) < min_need:
            return None

        # 若评估日不是最新 bar，先按日截断
        if trade_date and bars[-1]["date"] > trade_date:
            bars = [b for b in bars if b["date"] <= trade_date]
            if not bars:
                return None

        # Z/流动性用 lookback_days；KDE 可额外扩到 kde_lookback_max（支撑缺失时递推）
        lookback = max(int(cfg.get("lookback_days", 250)), min_need)
        kde_max = max(
            lookback,
            int(cfg.get("kde_lookback_max", KDE_LOOKBACK_MAX)),
        )
        # panel 可能已拉到 kde_max；Z 仍只用近 lookback 日，保证信号口径稳定
        bars_full = _bars_for_lookback(bars, kde_max)
        bars = _bars_for_lookback(bars_full, lookback)
        if len(bars) < min_need:
            return None

        closes_map = {b["date"]: b["close"] for b in bars}
        zinfo = latest_zscore(closes_map, benchmark, int(cfg.get("z_window", 40)))
        if not zinfo:
            return None

        price = float(zinfo["price"])
        kde = extract_kde_levels_expand_support(
            [b["close"] for b in bars_full],
            [b["volume"] for b in bars_full],
            price=price,
            initial_lookback=lookback,
            step=int(cfg.get("kde_lookback_step", 250)),
            max_lookback=kde_max,
            base_factor=float(cfg.get("kde_base_factor", 1.0)),
            grid_points=int(cfg.get("kde_grid_points", 200)),
        )
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
            min_avg_turnover_rate=float(liq_cfg.get("min_avg_turnover_rate", 0.8)),
            stock_code=code_n,
            liq_cfg=liq_cfg,
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
        z_lead = float(cfg.get("z_lead", 2.0))
        z_catch = float(cfg.get("z_catch_up", -1.5))
        min_rr = float(cfg.get("min_rr_to_resistance", 1.5))
        enable_veto = bool(cfg.get("enable_trend_veto", True))
        enable_lead_trade = bool(cfg.get("enable_lead_trade", False))
        z_val = zinfo.get("z_score")
        catch_hit = z_val is not None and float(z_val) <= z_catch
        lead_hit = z_val is not None and float(z_val) >= z_lead
        veto = bool(sig.get("trend_veto"))
        struct_ok = bool(struct.get("structure_valid"))
        liq_ok = bool(liq.get("liquidity_ok"))
        liq_lookback = int(liq_cfg.get("lookback_days", 20))
        liq_amt_gate = liq.get("min_avg_amount_applied")
        if liq_amt_gate is None:
            liq_amt_gate = float(liq_cfg.get("min_avg_amount", 5_000_000))
        liq_tr_gate = liq.get("min_avg_turnover_rate_applied")
        if liq_tr_gate is None:
            liq_tr_gate = float(liq_cfg.get("min_avg_turnover_rate", 0.8))
        liq_seg_label = liq.get("board_segment_label") or "默认"
        judgment_steps = [
            {
                "name": "补涨 Z 阈值",
                "rule": f"Z ≤ {z_catch}",
                "actual": z_val,
                "pass": catch_hit,
            },
            {
                "name": "领涨 Z 阈值",
                "rule": f"Z ≥ {z_lead}",
                "actual": z_val,
                "pass": lead_hit,
            },
            {
                "name": "板块趋势否决",
                "rule": "斜率≥0（enable_trend_veto 时）" if enable_veto else "已关闭",
                "actual": slope,
                "pass": (not veto) if enable_veto else True,
            },
            {
                "name": "结构过滤",
                "rule": f"站上支撑且盈亏比≥{min_rr}",
                "actual": struct.get("rr"),
                "pass": struct_ok,
                "note": struct.get("reason"),
            },
            {
                "name": "流动性",
                "rule": (
                    f"{liq_seg_label}近{liq_lookback}日均额≥{liq_amt_gate}"
                    f"（人民币元）且换手≥{liq_tr_gate}%"
                ),
                "actual": liq.get("avg_amount"),
                "pass": liq_ok,
                "note": (
                    f"{liq.get('reason')}; "
                    f"换手={liq.get('avg_turnover_rate')}; "
                    f"分档={liq.get('board_segment')}"
                ),
            },
            {
                "name": "入场信号",
                "rule": (
                    "catch_up：未否决+结构+流动性；"
                    f"lead：enable_lead_trade={enable_lead_trade} 时同理"
                ),
                "actual": sig.get("signal_type"),
                "pass": bool(sig.get("entry_signal")),
                "note": sig.get("reason"),
            },
        ]
        price_adjust = "qfq" if any(b.get("price_adjust") == "qfq" for b in bars_full) else "none"
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
            "price_adjust": price_adjust,
            "detail": {
                "signal_reason": sig.get("reason"),
                "structure": struct,
                "liquidity": liq,
                "kde_reason": kde.get("reason"),
                "bw": kde.get("bw"),
                "i_t": zinfo.get("i_t"),
                "price_adjust": price_adjust,
                "z_window": int(cfg.get("z_window", 40)),
                "lookback_days_applied": lookback,
                "kde_lookback_used": kde.get("lookback_used"),
                "kde_lookback_expanded": bool(kde.get("lookback_expanded")),
                "bars_used": len(bars),
                "bars_full_for_kde": len(bars_full),
                "thresholds": {
                    "z_lead": z_lead,
                    "z_catch_up": z_catch,
                    "min_rr_to_resistance": min_rr,
                    "enable_trend_veto": enable_veto,
                    "enable_lead_trade": enable_lead_trade,
                    "kde_base_factor": float(cfg.get("kde_base_factor", 1.0)),
                    "kde_lookback_step": int(cfg.get("kde_lookback_step", 250)),
                    "kde_lookback_max": kde_max,
                    "sector_slope_window": int(cfg.get("sector_slope_window", 60)),
                    "liquidity_board_segment": liq.get("board_segment"),
                    "liquidity_min_avg_amount": liq_amt_gate,
                    "liquidity_min_avg_turnover_rate": liq_tr_gate,
                },
                "judgment": {
                    "formula": "入场 = (catch_up 或 允许交易的 lead) AND 未趋势否决 AND 结构有效 AND 流动性通过",
                    "formula_detail": (
                        "比价 R=P/I（分子=个股收盘，分母=板块量权基准）；"
                        "补涨主路径：Z≤z_catch_up；领涨默认仅观察；"
                        "流动性按上市板别分层均额（人民币元）+ 换手；"
                        "离场仅认收盘跌破结构支撑，不用固定百分比止损。"
                    ),
                    "steps": judgment_steps,
                },
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
        board_kind: str = "industry",
        include_no_signal: bool = False,
        codes_filter: Optional[set] = None,
        price_adjust: str = "none",
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> List[Dict[str, Any]]:
        cfg = config or self.config
        lookback = int(cfg.get("lookback_days", 250))
        kde_max = max(lookback, int(cfg.get("kde_lookback_max", KDE_LOOKBACK_MAX)))
        min_members = int((cfg.get("scan") or {}).get("min_sector_members", 5))
        members = self.loader.load_board_members(board_code, board_kind=board_kind)
        if len(members) < min_members:
            return []
        codes = [m["code"] for m in members]
        name_map = {m["code"]: m.get("name") for m in members}
        # 单股/自选目标股若不在成分列表（编码差异等），仍并入面板以便评估
        if codes_filter:
            for c in codes_filter:
                cn = _norm_code(c)
                if cn and cn not in name_map:
                    codes.append(cn)
                    name_map[cn] = None
        adjust_n = str(price_adjust or "none").strip().lower() or "none"
        # 拉足 KDE 最大回看；Z/斜率仍在 evaluate 内截断到 lookback_days
        panel = self.loader.load_sector_panel(
            codes,
            end_date=date,
            lookback=kde_max,
            adjust=adjust_n,
            factor_source=factor_source,
            refresh_factor=refresh_factor,
        )
        if len(panel) < min_members:
            return []
        date_members = self.loader.build_date_members(panel)
        benchmark = compute_vwap_benchmark(date_members)
        if len(benchmark) < int(cfg.get("z_window", 40)) + 5:
            return []
        slope = sector_slope(benchmark, int(cfg.get("sector_slope_window", 60)))
        trade_date = date or (benchmark[-1]["date"] if benchmark else self.loader.resolve_trade_date())

        # 全成分建基准；仅对目标代码评估（单股/自选过滤时）
        eval_codes = list(panel.keys())
        if codes_filter is not None:
            filt = {_norm_code(c) for c in codes_filter}
            eval_codes = [c for c in eval_codes if c in filt]
            # 目标股有日线但未进 panel 键名时再补一次
            for c in filt:
                if c not in panel:
                    bars = self.loader.load_bars(
                        c,
                        end_date=date,
                        limit=kde_max,
                        adjust=adjust_n,
                        factor_source=factor_source,
                        refresh_factor=refresh_factor,
                    )
                    if bars:
                        panel[c] = bars
                        eval_codes.append(c)

        results = []
        for code in eval_codes:
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
                # 选股默认只要有信号类型；单股明细可返回区间内（in_band）结果
                if (
                    not include_no_signal
                    and not row.get("signal_type")
                    and not row.get("entry_signal")
                ):
                    continue
                results.append(row)
            except Exception as e:
                logger.debug("RPE evaluate %s in %s failed: %s", code, board_code, e)
        return results

    def _resolve_boards_for_codes(
        self,
        codes: List[str],
        board_kind: str,
    ) -> List[Dict[str, str]]:
        """
        为代码列表解析**固定主板块**（每只股票只对应一个板块）。
        优先指定 kind（默认行业）；无归属则回退概念；同 kind 多板块取成分最多者。
        返回项含 board_code / board_name / board_kind（按板块去重）。
        """
        kind = "concept" if board_kind == "concept" else "industry"
        jobs: List[Dict[str, str]] = []
        seen = set()
        for c in codes:
            picked = self.loader.resolve_primary_board(c, board_kind=kind, allow_fallback=True)
            if not picked:
                continue
            use_kind = str(picked.get("board_kind") or kind)
            key = (str(picked["board_code"]), use_kind)
            if key in seen:
                continue
            seen.add(key)
            jobs.append(
                {
                    "board_code": str(picked["board_code"]),
                    "board_name": str(picked.get("board_name") or picked["board_code"]),
                    "board_kind": use_kind,
                }
            )
        return jobs

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
        board_kind: str = "industry",
        include_no_signal: bool = False,
        price_adjust: str = "none",
        factor_source: str = "auto",
        refresh_factor: bool = False,
    ) -> List[Dict[str, Any]]:
        cfg = config or self.config
        scan = cfg.get("scan") or {}
        max_n = max_results if max_results is not None else int(scan.get("max_results", 200))
        trade_date = date or self.loader.resolve_trade_date()
        kind = "concept" if board_kind == "concept" else "industry"
        code_filter = {_norm_code(c) for c in codes} if codes else None
        adjust_n = str(price_adjust or "none").strip().lower() or "none"

        board_jobs: List[Dict[str, str]]
        if board_codes:
            all_boards = {b["board_code"]: b for b in self.loader.list_boards(kind)}
            board_jobs = []
            for bc in board_codes:
                b = all_boards.get(bc) or {"board_code": bc, "board_name": bc}
                board_jobs.append(
                    {
                        "board_code": b["board_code"],
                        "board_name": b.get("board_name") or b["board_code"],
                        "board_kind": kind,
                    }
                )
        elif codes:
            # 自选/单股：按个股归属板块建簇（行业优先，无则概念）
            board_jobs = self._resolve_boards_for_codes(list(codes), kind)
        else:
            board_jobs = [
                {
                    "board_code": b["board_code"],
                    "board_name": b.get("board_name") or b["board_code"],
                    "board_kind": kind,
                }
                for b in self.loader.list_boards(kind, limit=scan.get("max_boards"))
            ]

        results: List[Dict[str, Any]] = []
        for b in board_jobs:
            rows = self.screen_board(
                b["board_code"],
                b.get("board_name") or b["board_code"],
                date=trade_date,
                config=cfg,
                entry_only=False,
                board_kind=b.get("board_kind") or kind,
                include_no_signal=include_no_signal,
                codes_filter=code_filter,
                price_adjust=adjust_n,
                factor_source=factor_source,
                refresh_factor=refresh_factor,
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
        # 同股多板块去重（显式多选板块时仍可能撞车）：保留 |z| 最大
        # 单股/自选路径已固定主板块，通常不会产生同股多行
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
