# -*- coding: utf-8 -*-
"""URT 选股引擎。"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from .data_loader import URTDataLoader
from .signal_detector import evaluate_buy_signal, history_calendar_days_for_fetch

logger = logging.getLogger(__name__)

ProgressCb = Callable[[int, int, str], None]
CancelCheck = Callable[[], bool]


def _screen_workers() -> int:
    raw = (os.getenv("URT_SCREEN_WORKERS") or "").strip()
    if raw.isdigit():
        return max(1, min(16, int(raw)))
    n = os.cpu_count() or 4
    return max(1, min(4, n))


def _hits_for_stock_dates(
    code: str,
    name: str,
    hist: List[Dict[str, Any]],
    dates: List[str],
    cfg: Dict[str, Any],
    require_pass: bool,
) -> List[Dict[str, Any]]:
    """对同一只股票的已拉行情，按多个交易日切片评买点（hist 为日期 DESC）。"""
    if not hist or not dates:
        return []
    wanted = {str(d)[:10] for d in dates}
    date_to_i: Dict[str, int] = {}
    for i, b in enumerate(hist):
        ds = str(b.get("date") or "")[:10]
        if ds in wanted and ds not in date_to_i:
            date_to_i[ds] = i
    out: List[Dict[str, Any]] = []
    for d in dates:
        i = date_to_i.get(d)
        if i is None:
            continue
        try:
            detail = evaluate_buy_signal(hist[i:], cfg, require_pass=require_pass)
        except Exception as e:
            logger.debug("URT range-screen skip %s %s: %s", code, d, e)
            continue
        if not detail:
            continue
        if str(detail.get("signal_date") or "")[:10] != d:
            continue
        out.append({"code": code, "name": name, **detail})
    return out


class URTStrategyEngine:
    def __init__(self, loader: URTDataLoader, config: Dict[str, Any]):
        self.loader = loader
        self.config = config

    def _load_hist_map(
        self,
        stock_rows: List[Tuple[str, str]],
        start_s: str,
        end_s: str,
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        codes = [str(c) for c, _n in stock_rows]
        try:
            return self.loader.fetch_historical_desc_batch(
                codes, start_date=start_s, end_date=end_s
            )
        except Exception as e:
            logger.warning("URT 批量拉行情失败，回退逐股: %s", e)
            return None

    def screen_universe(
        self,
        stock_rows: List[Tuple[str, str]],
        *,
        as_of_end_date: Optional[str] = None,
        require_pass: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        require_pass=True：仅返回硬筛+得分通过的买点（全部A股/港股全量选股）。
        require_pass=False：始终返回可计算的信号明细（自选/板块/单股，对齐 GMS 列表不过滤）。
        """
        cal_days = history_calendar_days_for_fetch(self.config)
        start_s, end_s = URTDataLoader.default_date_window(cal_days, as_of_end_date)
        results: List[Dict[str, Any]] = []
        if not stock_rows:
            return results
        hist_map = self._load_hist_map(stock_rows, start_s, end_s)
        for code, name in stock_rows:
            try:
                if hist_map is not None:
                    hist = list(hist_map.get(code) or [])
                else:
                    hist = self.loader.fetch_historical_desc(code, start_date=start_s, end_date=end_s)
                if not hist:
                    continue
                # 若指定基准日，截到该日及之前
                if as_of_end_date:
                    anchor = str(as_of_end_date)[:10]
                    hist = [b for b in hist if str(b.get("date") or "")[:10] <= anchor]
                detail = evaluate_buy_signal(hist, self.config, require_pass=require_pass)
                if not detail:
                    continue
                results.append({"code": code, "name": name, **detail})
            except Exception as e:
                logger.debug("URT screen skip %s: %s", code, e)
                continue
        results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
        return results

    def screen_universe_for_dates(
        self,
        stock_rows: List[Tuple[str, str]],
        dates: List[str],
        *,
        require_pass: bool = True,
        progress_cb: Optional[ProgressCb] = None,
        cancel_check: Optional[CancelCheck] = None,
        chunk_size: int = 400,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], bool]:
        """
        一次拉齐 [最早日-回看, 最晚日] 行情，在内存中对多个交易日评买点。

        避免回测/补预计算按日重复拉取约 1200 个自然日的全市场 K 线。
        返回 (按日命中, 是否完整跑完)。取消或中断时不要把未完成日标成已扫描。
        """
        date_list = [str(d)[:10] for d in dates if str(d).strip()]
        date_list = list(dict.fromkeys(date_list))
        hits_by_date: Dict[str, List[Dict[str, Any]]] = {d: [] for d in date_list}
        if not stock_rows or not date_list:
            return hits_by_date, True

        cal_days = history_calendar_days_for_fetch(self.config)
        # 回看相对最早扫描日，结束日取区间最晚，整段只拉一次行情
        start_s, _ = URTDataLoader.default_date_window(cal_days, min(date_list))
        end_s = max(date_list)
        n_chunk = max(50, int(chunk_size or 400))
        workers = _screen_workers()
        total = len(stock_rows)
        done_stocks = 0
        cfg = self.config

        logger.info(
            "URT 区间扫描 stocks=%s days=%s window=%s~%s workers=%s",
            total,
            len(date_list),
            start_s,
            end_s,
            workers,
        )
        if progress_cb:
            progress_cb(0, total, f"区间一次扫描 0/{total} 只（{len(date_list)} 个交易日）")

        for i in range(0, total, n_chunk):
            if cancel_check and cancel_check():
                logger.info("URT 区间扫描已取消 stocks_done=%s/%s", done_stocks, total)
                return hits_by_date, False
            chunk = stock_rows[i : i + n_chunk]
            hist_map = self._load_hist_map(chunk, start_s, end_s)
            jobs: List[Tuple[str, str, List[Dict[str, Any]]]] = []
            for code, name in chunk:
                if hist_map is not None:
                    hist = list(hist_map.get(code) or [])
                else:
                    try:
                        hist = self.loader.fetch_historical_desc(
                            code, start_date=start_s, end_date=end_s
                        )
                    except Exception as e:
                        logger.debug("URT range fetch skip %s: %s", code, e)
                        hist = []
                jobs.append((str(code), str(name), hist))

            def _run_job(item: Tuple[str, str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
                code, name, hist = item
                return _hits_for_stock_dates(code, name, hist, date_list, cfg, require_pass)

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
