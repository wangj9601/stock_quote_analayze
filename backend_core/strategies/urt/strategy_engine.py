# -*- coding: utf-8 -*-
"""URT 选股引擎。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .data_loader import URTDataLoader
from .signal_detector import evaluate_buy_signal

logger = logging.getLogger(__name__)


class URTStrategyEngine:
    def __init__(self, loader: URTDataLoader, config: Dict[str, Any]):
        self.loader = loader
        self.config = config

    def screen_universe(
        self,
        stock_rows: List[Tuple[str, str]],
        *,
        as_of_end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cal_days = int(self.config.get("history_calendar_days") or 120)
        start_s, end_s = URTDataLoader.default_date_window(cal_days, as_of_end_date)
        results: List[Dict[str, Any]] = []
        for code, name in stock_rows:
            try:
                hist = self.loader.fetch_historical_desc(code, start_date=start_s, end_date=end_s)
                if not hist:
                    continue
                # 若指定基准日，截到该日及之前
                if as_of_end_date:
                    anchor = str(as_of_end_date)[:10]
                    hist = [b for b in hist if str(b.get("date") or "")[:10] <= anchor]
                detail = evaluate_buy_signal(hist, self.config)
                if not detail:
                    continue
                results.append({"code": code, "name": name, **detail})
            except Exception as e:
                logger.debug("URT screen skip %s: %s", code, e)
                continue
        results.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
        return results
