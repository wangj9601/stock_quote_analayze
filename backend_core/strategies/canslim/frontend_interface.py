# -*- coding: utf-8 -*-
"""CAN SLIM 前端选股接口。"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional, Sequence

from sqlalchemy.orm import Session

from backend_core.strategies.canslim.config import get_default_canslim_config, merge_canslim_config
from backend_core.strategies.canslim.engine import CanSlimEngine


class CanSlimFrontendInterface:
    """供 API 调用的选股入口。"""

    def __init__(self, db: Session, config: Optional[Dict[str, Any]] = None):
        self.db = db
        self.config = merge_canslim_config(config)

    def get_default_config(self) -> Dict[str, Any]:
        return get_default_canslim_config()

    def screen(
        self,
        *,
        asof: Optional[str] = None,
        codes: Optional[Sequence[str]] = None,
        market_filter: Optional[bool] = None,
        rs_min: Optional[int] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cfg = merge_canslim_config(overrides) if overrides else copy.deepcopy(self.config)
        if market_filter is not None:
            cfg.setdefault("M", {})
            cfg["M"]["enabled"] = bool(market_filter)
        if rs_min is not None:
            cfg.setdefault("L", {})
            cfg["L"]["rs_rating_min"] = int(rs_min)
        return CanSlimEngine(self.db, cfg).screen(asof=asof, codes=codes)
