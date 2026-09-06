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
        filter_c: Optional[bool] = None,
        filter_a: Optional[bool] = None,
        filter_n: Optional[bool] = None,
        filter_s: Optional[bool] = None,
        filter_l: Optional[bool] = None,
        rs_min: Optional[int] = None,
        q_eps_yoy_min: Optional[float] = None,
        roe_min: Optional[float] = None,
        near_high_min_pct: Optional[float] = None,
        circ_shares_max_yi: Optional[float] = None,
        a_require_growth: Optional[bool] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cfg = merge_canslim_config(overrides) if overrides else copy.deepcopy(self.config)
        letter_flags = {
            "C": filter_c,
            "A": filter_a,
            "N": filter_n,
            "S": filter_s,
            "L": filter_l,
            "M": market_filter,
        }
        for letter, flag in letter_flags.items():
            if flag is not None:
                cfg.setdefault(letter, {})
                cfg[letter]["enabled"] = bool(flag)
        if rs_min is not None:
            cfg.setdefault("L", {})
            cfg["L"]["rs_rating_min"] = int(rs_min)
        if q_eps_yoy_min is not None:
            cfg.setdefault("C", {})
            cfg["C"]["q_eps_yoy_min"] = float(q_eps_yoy_min)
        if roe_min is not None:
            cfg.setdefault("A", {})
            cfg["A"]["roe_min"] = float(roe_min)
        if a_require_growth is not None:
            cfg.setdefault("A", {})
            cfg["A"]["require_annual_growth"] = bool(a_require_growth)
        if near_high_min_pct is not None:
            cfg.setdefault("N", {})
            # 前端传百分比 85 → 内部 ratio 0.85
            pct = float(near_high_min_pct)
            cfg["N"]["near_high_min_ratio"] = pct / 100.0 if pct > 1.0 else pct
        if circ_shares_max_yi is not None:
            cfg.setdefault("S", {})
            cfg["S"]["circ_shares_max_yi"] = float(circ_shares_max_yi)
        return CanSlimEngine(self.db, cfg).screen(asof=asof, codes=codes)
