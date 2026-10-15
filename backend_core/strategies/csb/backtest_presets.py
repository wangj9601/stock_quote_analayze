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
        "id": "breakout_lps_v3",
        "label": "仅 BREAKOUT/LPS + 出场 v3",
        "description": (
            "排除 PROBE，仅 BREAKOUT/LPS、结构出场、目标 10%、分≥60；"
            "出场沿用 v3：基准止损 2%/3 日、通道失效 1.5%/3 日"
        ),
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
            "defense_overrides": {
                "probe_stop_buffer_pct": 0.02,
                "probe_stop_confirm_days": 3,
                "channel_fail_buffer_pct": 0.015,
                "channel_fail_confirm_days": 3,
            },
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
    {
        "id": "structure_v3",
        "label": "结构 v3（PROBE 优化+基准止损放宽）",
        "description": (
            "在 PROBE 优化过滤上，任务级覆盖：基准止损缓冲 2%、连续 3 日确认；"
            "通道失效保持 1.5%/3 日（对照 2bd159df 基准止损占比过高）"
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
                "probe_stop_buffer_pct": 0.02,
                "probe_stop_confirm_days": 3,
                "channel_fail_buffer_pct": 0.015,
                "channel_fail_confirm_days": 3,
            },
        },
    },
    {
        "id": "structure_v4",
        "label": "结构 v4（入场收紧+出场沿用 v3）",
        "description": (
            "对照 e7b3cbe0：出场保持基准止损 2%/3 日与通道失效 1.5%/3 日；"
            "入场收紧为分≥85、PROBE 分≥85、回踩≥4、单日最多 30 只"
        ),
        "fields": {
            "exit_mode": "structure_exit",
            "target_pct": 0.05,
            "target_pct_max": 0.05,
            "min_score": 85,
            "horizon_days": 10,
            "compare_hit_rate": True,
            "min_touch_count": 4,
            "probe_min_score": 85,
            "max_signals_per_day": 30,
            "allowed_signal_types": [CSB_PROBE, CSB_BREAKOUT, CSB_LPS],
            "defense_overrides": {
                "probe_stop_buffer_pct": 0.02,
                "probe_stop_confirm_days": 3,
                "channel_fail_buffer_pct": 0.015,
                "channel_fail_confirm_days": 3,
            },
        },
    },
    {
        "id": "structure_v5",
        "label": "结构 v5（通道宽>2%+回踩4～5+出场 v3）",
        "description": (
            "对照因子分桶：排除极窄通道（宽<2%）、PROBE 回踩限制在 4～5 次、分≥80；"
            "出场沿用 v3（基准止损 2%/3 日、通道失效 1.5%/3 日）"
        ),
        "fields": {
            "exit_mode": "structure_exit",
            "target_pct": 0.05,
            "target_pct_max": 0.05,
            "min_score": 80,
            "horizon_days": 10,
            "compare_hit_rate": True,
            "min_touch_count": 4,
            "max_touch_count": 5,
            "min_channel_width_pct": 0.02,
            "probe_min_score": 80,
            "max_signals_per_day": 30,
            "allowed_signal_types": [CSB_PROBE, CSB_BREAKOUT, CSB_LPS],
            "defense_overrides": {
                "probe_stop_buffer_pct": 0.02,
                "probe_stop_confirm_days": 3,
                "channel_fail_buffer_pct": 0.015,
                "channel_fail_confirm_days": 3,
            },
        },
    },
    {
        "id": "structure_v6",
        "label": "结构 v6（v5+入场不低于下轨）",
        "description": (
            "在 v5（通道宽≥2%、回踩 4～5、分≥80、出场 v3）上，"
            "增加入场位置 entry_pos≥0（信号价不低于通道下轨）"
        ),
        "fields": {
            "exit_mode": "structure_exit",
            "target_pct": 0.05,
            "target_pct_max": 0.05,
            "min_score": 80,
            "horizon_days": 10,
            "compare_hit_rate": True,
            "min_touch_count": 4,
            "max_touch_count": 5,
            "min_channel_width_pct": 0.02,
            "min_entry_pos_in_channel": 0.0,
            "probe_min_score": 80,
            "max_signals_per_day": 30,
            "allowed_signal_types": [CSB_PROBE, CSB_BREAKOUT, CSB_LPS],
            "defense_overrides": {
                "probe_stop_buffer_pct": 0.02,
                "probe_stop_confirm_days": 3,
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
