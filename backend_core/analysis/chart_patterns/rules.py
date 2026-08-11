# -*- coding: utf-8 -*-
"""形态识别统一阈值（突破确认 / 失效 / 重叠过滤）。

文档见 docs/features/形态识别工具.md。
"""

from __future__ import annotations

# 巩固形态（楔/旗/三角）突破确认：收盘相对边界缓冲
BREAKOUT_UP_MULT = 1.005  # last_close > upper * 1.005 → 上破已确认
BREAKOUT_DOWN_MULT = 0.995  # last_close < lower * 0.995 → 下破已确认

# 形成中反转形态失效：跌破头部/低点或升破头部/高点
INVALIDATE_BOTTOM_MULT = 0.99  # close < head/low * 0.99 → invalidated
INVALIDATE_TOP_MULT = 1.01  # close > head/high * 1.01 → invalidated

# 楔形/旗形 NMS：上下沿相对差 ≤ 该阈值视为同界
NMS_BOUND_REL_TOL = 0.01

# 斜率单位说明（linreg 自变量为枢轴的 K 线 index）
SLOPE_UNIT_NOTE = "元/K线索引(约交易日)"


def breakout_up(last_close: float, upper: float) -> bool:
    return upper > 0 and last_close > upper * BREAKOUT_UP_MULT


def breakout_down(last_close: float, lower: float) -> bool:
    return lower > 0 and last_close < lower * BREAKOUT_DOWN_MULT


def invalidate_bottom(last_close: float, low_ref: float) -> bool:
    """底部形态：收盘跌破参考低点 × 0.99。"""
    return low_ref > 0 and last_close < low_ref * INVALIDATE_BOTTOM_MULT


def invalidate_top(last_close: float, high_ref: float) -> bool:
    """顶部形态：收盘升破参考高点 × 1.01。"""
    return high_ref > 0 and last_close > high_ref * INVALIDATE_TOP_MULT
