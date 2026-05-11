"""
3倍量缩量突破 — 对外选股入口（供 API 薄封装调用）。
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from .config import VolumeShrinkBreakoutConfigManager
from .data_loader import VolumeShrinkBreakoutDataLoader, normalize_vsb_board_keys
from .signal_storage import save_screen_hits
from .strategy_engine import VolumeShrinkBreakoutStrategyEngine, evaluate_stock

logger = logging.getLogger(__name__)

# 逐日回放：区间内实际有 K 线的交易日数量上限（防单次请求过大）
MAX_VSB_REPLAY_TRADING_DAYS = 500


def _vsb_bar_date_key(bar: Dict[str, Any]) -> Optional[str]:
    d = bar.get("date")
    if d is None:
        return None
    s = str(d).strip()[:10]
    return s if len(s) == 10 else None


def _parse_iso_date(s: str) -> Optional[date]:
    s = (s or "").strip()[:10]
    if len(s) != 10:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _min_bars_for_vsb_eval(cfg: Dict[str, Any]) -> int:
    kmax = int(cfg["boom_lookback_max"])
    mode = str(cfg.get("evaluation_mode") or "three_phase").strip().lower()
    if mode == "legacy":
        return kmax + 20
    trend_lb = max(1, int(cfg.get("trend_ma_lookback") or 5))
    tail_need = max(25, trend_lb + 22, 28)
    return kmax + tail_need


def _bar_sort_date(bar: Dict[str, Any]) -> Optional[date]:
    return _parse_iso_date(_vsb_bar_date_key(bar) or "")


def _replay_fetch_window(replay_start: date, replay_end: date, cfg: Dict[str, Any]) -> Tuple[str, str]:
    """向前多取自然日，保证首段 pivot 日仍有足够 lookback K 线。"""
    span = (replay_end - replay_start).days + 1
    base_cal = int(cfg.get("history_calendar_days", 180))
    back_days = min(2000, max(500, base_cal + span + 150))
    fetch_start = replay_end - timedelta(days=back_days)
    return fetch_start.strftime("%Y-%m-%d"), replay_end.strftime("%Y-%m-%d")


class VolumeShrinkBreakoutFrontendInterface:
    """与 GMS 命名风格一致。"""

    @staticmethod
    def screen(
        db: Session,
        *,
        scope: str = "all",
        limit: Optional[int] = None,
        stock_codes: Optional[List[str]] = None,
        volume_ratio: Optional[float] = None,
        boom_lookback_min: Optional[int] = None,
        boom_lookback_max: Optional[int] = None,
        boards: Optional[List[str]] = None,
        persist_signals: bool = True,
        screening_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        scope:
          - all: 全 A（受 limit 截断）
          - watchlist: 调用方传入 stock_codes（已解析好的自选股代码列表）

        screening_date: 筛选基准日 YYYY-MM-DD（可选）。若 historical_quotes 无该日或晚于表内最新日，
        则自动改用表内全局最新交易日作为 K 线窗口止日，并作为落库 run_search_date。
        """
        cm = VolumeShrinkBreakoutConfigManager()
        cfg = cm.merge_overrides(
            cm.load_config(),
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
        )

        loader = VolumeShrinkBreakoutDataLoader(db)
        effective = VolumeShrinkBreakoutDataLoader.resolve_effective_history_end_date(db, screening_date)
        today_s = datetime.now().strftime("%Y-%m-%d")
        req_norm = (screening_date or "").strip()[:10] or None
        hint: Optional[str] = None
        if effective != (req_norm or today_s):
            if req_norm:
                hint = (
                    f"基准日 {req_norm} 在历史行情表中无数据或尚未入库，"
                    f"已改用表内最新交易日 {effective} 作为 K 线窗口止日与落库检索日。"
                )
            else:
                hint = (
                    f"当前自然日 {today_s} 无行情数据，"
                    f"已改用表内最新交易日 {effective} 作为 K 线窗口止日与落库检索日。"
                )

        if scope == "watchlist":
            pool_codes = stock_codes
        else:
            pool_codes = None

        board_keys = normalize_vsb_board_keys(boards)
        stocks = loader.list_a_share_candidates(
            limit=limit,
            stock_codes=pool_codes,
            boards=board_keys or None,
        )
        engine = VolumeShrinkBreakoutStrategyEngine(loader, cfg)
        data = engine.screen_universe(stocks, as_of_end_date=effective)

        parameters_out = {
            "volume_ratio": cfg["volume_ratio"],
            "boom_lookback_min": cfg["boom_lookback_min"],
            "boom_lookback_max": cfg["boom_lookback_max"],
            "history_calendar_days": cfg.get("history_calendar_days", 180),
            "evaluation_mode": cfg.get("evaluation_mode", "three_phase"),
            "trend_ma_lookback": cfg.get("trend_ma_lookback", 5),
            "retracement_break_eps": cfg.get("retracement_break_eps", 0.005),
            "ma_flat_tol": cfg.get("ma_flat_tol", 0.008),
            "retracement_volume_half_ratio": cfg.get("retracement_volume_half_ratio", 0.5),
            "limit": limit,
            "boards": board_keys,
            "screening_date_requested": req_norm,
            "screening_date_effective": effective,
        }
        run_sd = effective
        if persist_signals and data and run_sd:
            n_saved = save_screen_hits(db, data, parameters=parameters_out, search_date=run_sd)
            logger.info("VSB 信号已落库 %s 条 search_date=%s", n_saved, run_sd)

        out: Dict[str, Any] = {
            "success": True,
            "data": data,
            "total": len(data),
            "strategy_name": "3倍量缩量突破",
            "scope": scope,
            "parameters": parameters_out,
            "search_date": effective,
        }
        if hint:
            out["message"] = hint
        return out

    @staticmethod
    def recalculate_single_and_persist(
        db: Session,
        *,
        code: str,
        name: Optional[str] = None,
        search_date: Optional[str] = None,
        volume_ratio: Optional[float] = None,
        boom_lookback_min: Optional[int] = None,
        boom_lookback_max: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        对单只股票按当前配置重跑 VSB 引擎；若命中则写入 volume_shrink_breakout_signals（与选股 persist 一致）。
        用于信号历史页「无记录时重算」：仅反映**最新 K 线**是否满足策略，不会在历史区间内逐日回放。
        """
        from backend_api.models import StockBasicInfo

        code_n = str(code or "").strip()
        if len(code_n) == 5 and code_n.isdigit():
            code_n = code_n.zfill(6)
        if not code_n or len(code_n) != 6 or not code_n.isdigit():
            return {
                "success": False,
                "message": "股票代码须为 6 位数字",
                "saved": 0,
                "hit": False,
                "data": [],
            }

        display_name = (name or "").strip()
        if not display_name:
            row = db.query(StockBasicInfo).filter(StockBasicInfo.code == code_n).first()
            if row is not None and getattr(row, "name", None):
                display_name = str(row.name).strip()[:100]
        if not display_name:
            display_name = code_n

        cm = VolumeShrinkBreakoutConfigManager()
        cfg = cm.merge_overrides(
            cm.load_config(),
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
        )

        loader = VolumeShrinkBreakoutDataLoader(db)
        stocks = loader.list_a_share_candidates(limit=1, stock_codes=[code_n], boards=None)
        if not stocks:
            return {
                "success": False,
                "message": "未找到该股票基础信息，或该股为 ST / 不可采集，无法参与扫描",
                "saved": 0,
                "hit": False,
                "data": [],
            }

        engine = VolumeShrinkBreakoutStrategyEngine(loader, cfg)
        data = engine.screen_universe(stocks)

        run_sd = (search_date or "").strip()[:10] if search_date else None
        if not run_sd:
            run_sd = datetime.now().strftime("%Y-%m-%d")

        parameters_out: Dict[str, Any] = {
            "volume_ratio": cfg["volume_ratio"],
            "boom_lookback_min": cfg["boom_lookback_min"],
            "boom_lookback_max": cfg["boom_lookback_max"],
            "history_calendar_days": cfg.get("history_calendar_days", 180),
            "evaluation_mode": cfg.get("evaluation_mode", "three_phase"),
            "trend_ma_lookback": cfg.get("trend_ma_lookback", 5),
            "retracement_break_eps": cfg.get("retracement_break_eps", 0.005),
            "ma_flat_tol": cfg.get("ma_flat_tol", 0.008),
            "retracement_volume_half_ratio": cfg.get("retracement_volume_half_ratio", 0.5),
            "limit": 1,
            "boards": [],
        }

        if data:
            n_saved = save_screen_hits(db, data, parameters=parameters_out, search_date=run_sd)
            logger.info("VSB 单股重算落库 code=%s saved=%s search_date=%s", code_n, n_saved, run_sd)
            return {
                "success": True,
                "message": f"当前最新 K 线满足策略，已写入或更新 {n_saved} 条记录（signal_date=突破日）。",
                "saved": int(n_saved),
                "hit": True,
                "data": data,
                "search_date": run_sd,
            }

        return {
            "success": True,
            "message": "已按最新日线重算：当前未满足策略条件，未写入新记录（历史区间无数据仍属正常）。",
            "saved": 0,
            "hit": False,
            "data": [],
            "search_date": run_sd,
        }

    @staticmethod
    def recalculate_range_replay_and_persist(
        db: Session,
        *,
        code: str,
        name: Optional[str] = None,
        search_date: Optional[str] = None,
        replay_start: str,
        replay_end: str,
        volume_ratio: Optional[float] = None,
        boom_lookback_min: Optional[int] = None,
        boom_lookback_max: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        在 [replay_start, replay_end] 内，对每个**有 K 线的交易日** D，将「截至 D 的 DESC 子序列」视为当时最新状态，
        调用 evaluate_stock；命中则收集后一次性 save_screen_hits（与选股落库一致）。
        """
        from backend_api.models import StockBasicInfo

        d0 = _parse_iso_date(replay_start)
        d1 = _parse_iso_date(replay_end)
        if d0 is None or d1 is None:
            return {
                "success": False,
                "message": "replay 需提供合法 replay_start / replay_end（YYYY-MM-DD）",
                "saved": 0,
                "hit": False,
                "data": [],
            }
        if d0 > d1:
            return {
                "success": False,
                "message": "replay 起始日不能晚于结束日",
                "saved": 0,
                "hit": False,
                "data": [],
            }

        code_n = str(code or "").strip()
        if len(code_n) == 5 and code_n.isdigit():
            code_n = code_n.zfill(6)
        if not code_n or len(code_n) != 6 or not code_n.isdigit():
            return {
                "success": False,
                "message": "股票代码须为 6 位数字",
                "saved": 0,
                "hit": False,
                "data": [],
            }

        display_name = (name or "").strip()
        if not display_name:
            row = db.query(StockBasicInfo).filter(StockBasicInfo.code == code_n).first()
            if row is not None and getattr(row, "name", None):
                display_name = str(row.name).strip()[:100]
        if not display_name:
            display_name = code_n

        cm = VolumeShrinkBreakoutConfigManager()
        cfg = cm.merge_overrides(
            cm.load_config(),
            volume_ratio=volume_ratio,
            boom_lookback_min=boom_lookback_min,
            boom_lookback_max=boom_lookback_max,
        )

        loader = VolumeShrinkBreakoutDataLoader(db)
        stocks = loader.list_a_share_candidates(limit=1, stock_codes=[code_n], boards=None)
        if not stocks:
            return {
                "success": False,
                "message": "未找到该股票基础信息，或该股为 ST / 不可采集，无法参与扫描",
                "saved": 0,
                "hit": False,
                "data": [],
            }

        min_b = _min_bars_for_vsb_eval(cfg)
        fetch_start_str, fetch_end_str = _replay_fetch_window(d0, d1, cfg)
        full_hist = loader.fetch_historical_desc(code_n, start_date=fetch_start_str, end_date=fetch_end_str)
        if not full_hist:
            return {
                "success": False,
                "message": f"在 {fetch_start_str}～{fetch_end_str} 无历史 K 线，无法回放",
                "saved": 0,
                "hit": False,
                "data": [],
            }

        pivot_dates: List[date] = []
        seen = set()
        for b in full_hist:
            bd = _bar_sort_date(b)
            if bd is None or bd < d0 or bd > d1:
                continue
            if bd not in seen:
                seen.add(bd)
                pivot_dates.append(bd)
        pivot_dates.sort()

        if len(pivot_dates) > MAX_VSB_REPLAY_TRADING_DAYS:
            return {
                "success": False,
                "message": f"区间内交易日过多（{len(pivot_dates)}），超过上限 {MAX_VSB_REPLAY_TRADING_DAYS}，请缩小日期范围后重试",
                "saved": 0,
                "hit": False,
                "data": [],
            }

        vr = float(cfg["volume_ratio"])
        kmin = int(cfg["boom_lookback_min"])
        kmax = int(cfg["boom_lookback_max"])

        hits: List[Dict[str, Any]] = []
        for bd in pivot_dates:
            slice_: List[Dict[str, Any]] = []
            for bar in full_hist:
                bdt = _bar_sort_date(bar)
                if bdt is not None and bdt <= bd:
                    slice_.append(bar)
            if len(slice_) < min_b:
                continue
            detail = evaluate_stock(
                slice_,
                volume_ratio=vr,
                boom_lookback_min=kmin,
                boom_lookback_max=kmax,
                config=cfg,
            )
            if not detail:
                continue
            hits.append({"code": code_n, "name": display_name, **detail})

        run_sd = (search_date or "").strip()[:10] if search_date else None
        if not run_sd:
            run_sd = datetime.now().strftime("%Y-%m-%d")

        parameters_out: Dict[str, Any] = {
            "volume_ratio": cfg["volume_ratio"],
            "boom_lookback_min": cfg["boom_lookback_min"],
            "boom_lookback_max": cfg["boom_lookback_max"],
            "history_calendar_days": cfg.get("history_calendar_days", 180),
            "evaluation_mode": cfg.get("evaluation_mode", "three_phase"),
            "trend_ma_lookback": cfg.get("trend_ma_lookback", 5),
            "retracement_break_eps": cfg.get("retracement_break_eps", 0.005),
            "ma_flat_tol": cfg.get("ma_flat_tol", 0.008),
            "retracement_volume_half_ratio": cfg.get("retracement_volume_half_ratio", 0.5),
            "limit": 1,
            "boards": [],
            "replay_range": True,
            "replay_start": d0.isoformat(),
            "replay_end": d1.isoformat(),
            "replay_trading_days": len(pivot_dates),
        }

        n_saved = 0
        if hits:
            n_saved = int(save_screen_hits(db, hits, parameters=parameters_out, search_date=run_sd))
            logger.info(
                "VSB 区间逐日回放落库 code=%s days=%s hits=%s saved=%s search_date=%s",
                code_n,
                len(pivot_dates),
                len(hits),
                n_saved,
                run_sd,
            )

        if hits and n_saved == 0:
            return {
                "success": True,
                "message": f"逐日回放命中 {len(hits)} 条，但落库写入为 0（请检查表 volume_shrink_breakout_signals 是否存在及 DB 权限）。",
                "saved": 0,
                "hit": True,
                "data": hits,
                "search_date": run_sd,
                "replay_trading_days": len(pivot_dates),
                "replay_hits": len(hits),
            }

        if not hits:
            return {
                "success": True,
                "message": f"逐日回放完成：共扫描区间内 {len(pivot_dates)} 个交易日，未命中策略（无新写入）。",
                "saved": 0,
                "hit": False,
                "data": [],
                "search_date": run_sd,
                "replay_trading_days": len(pivot_dates),
                "replay_hits": 0,
            }

        return {
            "success": True,
            "message": f"逐日回放完成：扫描 {len(pivot_dates)} 个交易日，命中 {len(hits)} 条，已落库 {n_saved} 条（run_search_date={run_sd}）。",
            "saved": n_saved,
            "hit": True,
            "data": hits,
            "search_date": run_sd,
            "replay_trading_days": len(pivot_dates),
            "replay_hits": len(hits),
        }
