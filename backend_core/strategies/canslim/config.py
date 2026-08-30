# -*- coding: utf-8 -*-
"""CAN SLIM 配置（代码默认；阈值均可覆盖）。"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional


def get_default_canslim_config() -> Dict[str, Any]:
    return {
        "C": {
            "q_eps_yoy_min": 25.0,  # 单季 EPS 同比 %
            "require_sales_yoy": False,
            "q_sales_yoy_min": 20.0,
        },
        "A": {
            "annual_eps_yoy_min": 25.0,  # 近 3 年每年同比 %
            "annual_years": 3,
            "roe_min": 17.0,
            "use_cagr_fallback": True,
            "cagr_min": 25.0,
        },
        "N": {
            "near_high_min_ratio": 0.85,  # 收盘 / 52 周高 ≥
            "lookback_bars": 252,
            "allow_cupb": True,
            "cupb_statuses": ["forming", "confirmed"],
            "use_qfq": True,
        },
        "S": {
            "circ_shares_max_yi": 20.0,  # 流通股本上限（亿股）
            "require_up_day_volume": True,
            "volume_vs_mavol": "mavol20",  # mavol20 | mavol50（mavol50 用 mavol60 近似若无 50）
            "volume_ratio_min": 1.0,
        },
        "L": {
            "rs_rating_min": 80,
            "rs_strong_min": 90,
        },
        "M": {
            "enabled": True,
            "index_ts_code": "000300.SH",
            "ma_window": 50,
            "ma_slope_lookback": 10,  # MA50 需高于 N 日前
        },
        "I": {
            "enabled": False,  # 第一期不参与过滤
        },
        "scan": {
            "batch_size": 500,
            "max_results": 0,  # 0=不限
            "exclude_st": True,
        },
    }


def merge_canslim_config(override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = get_default_canslim_config()
    if not override:
        return base
    return _deep_merge(base, override)


def _deep_merge(base: Dict, override: Dict) -> Dict:
    result = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
