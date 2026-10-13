# -*- coding: utf-8 -*-
"""CSB 回测优化预设（管理端一键应用）。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from .config import CSB_BREAKOUT, CSB_LPS, CSB_PROBE

_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "optimized_probe",
        "label": "PROBE 优化（结构+5%+分≥80+回踩≥3）",
        "description": "针对全市场 PROBE 过严问题：结构出场、目标 5%、PROBE 最低 80 分、回踩≥3、单日最多 30 只",
        "fields": {
            "exit_mode": "structure_exit",
            "target_pct": 0.05,
            "target_pct_max": 0.05,
            "min_score": 80,
            "horizon_days": 10,
            "compare_hit_rate": True,
            "min_touch_count": 3,
            "probe_min_score": 80,
            "max_signals_per_day": 30,
            "allowed_signal_types": [CSB_PROBE, CSB_BREAKOUT, CSB_LPS],
        },
    },
    {
        "id": "breakout_lps_only",
        "label": "仅 BREAKOUT/LPS（结构+10%）",
        "description": "排除试探仓 PROBE，用突破/LPS 评估结构出场",
        "fields": {
            "exit_mode": "structure_exit",
            "target_pct": 0.10,
            "target_pct_max": 0.10,
            "min_score": 60,
            "horizon_days": 10,
            "compare_hit_rate": True,
            "min_touch_count": 0,
            "probe_min_score": None,
            "max_signals_per_day": 50,
            "allowed_signal_types": [CSB_BREAKOUT, CSB_LPS],
        },
    },
    {
        "id": "hit_rate_probe",
        "label": "PROBE 命中率（不止损+5%）",
        "description": "拆开信号空间与纪律出场：命中率模式、目标 5%、分≥80、回踩≥3",
        "fields": {
            "exit_mode": "hit_rate",
            "target_pct": 0.05,
            "target_pct_max": 0.05,
            "min_score": 80,
            "horizon_days": 10,
            "compare_hit_rate": False,
            "min_touch_count": 3,
            "probe_min_score": 80,
            "max_signals_per_day": 30,
            "allowed_signal_types": [CSB_PROBE],
        },
    },
    {
        "id": "structure_v2",
        "label": "结构 v2（PROBE 优化+通道失效放宽）",
        "description": (
            "在 PROBE 优化过滤上，任务级覆盖通道失效：下轨缓冲 1.5%、连续 3 日确认"
            "（对照 d8595daa 通道失效占比过高）"
        ),
        "fields": {
            "exit_mode": "structure_exit",
            "target_pct": 0.05,
            "target_pct_max": 0.05,
            "min_score": 80,
            "horizon_days": 10,
            "compare_hit_rate": True,
            "min_touch_count": 3,
            "probe_min_score": 80,
            "max_signals_per_day": 30,
            "allowed_signal_types": [CSB_PROBE, CSB_BREAKOUT, CSB_LPS],
            "defense_overrides": {
                "channel_fail_buffer_pct": 0.015,
                "channel_fail_confirm_days": 3,
            },
        },
    },
]


def list_backtest_presets() -> List[Dict[str, Any]]:
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "description": p.get("description") or "",
        }
        for p in _PRESETS
    ]


def get_backtest_preset(preset_id: str) -> Dict[str, Any]:
    pid = str(preset_id or "").strip()
    for p in _PRESETS:
        if p["id"] == pid:
            return deepcopy(p)
    raise KeyError(pid)


def apply_backtest_preset(preset_id: str, body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """将预设字段合并进创建体（不覆盖日期/股票池等）。"""
    preset = get_backtest_preset(preset_id)
    out = dict(body or {})
    fields = preset.get("fields") or {}
    for k, v in fields.items():
        out[k] = deepcopy(v)
    out["preset_id"] = preset["id"]
    return out
