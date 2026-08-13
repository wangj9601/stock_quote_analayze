# -*- coding: utf-8 -*-
"""形态识别统一阈值（突破确认 / 失效 / 重叠过滤）。

文档见 docs/features/形态识别工具.md；算法总览见 docs/features/支撑阻力与形态识别_算法说明.md。
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

# 巩固形态（楔/旗/三角）突破确认：收盘相对边界缓冲
BREAKOUT_UP_MULT = 1.005  # last_close > upper * 1.005 → 上破已确认
BREAKOUT_DOWN_MULT = 0.995  # last_close < lower * 0.995 → 下破已确认

# 反转形态失效：跌破头部/低点或升破头部/高点
INVALIDATE_BOTTOM_MULT = 0.99  # price < head/low * 0.99 → invalidated
INVALIDATE_TOP_MULT = 1.01  # price > head/high * 1.01 → invalidated

# 已确认反转形态生命周期：过期归档（不参与主形态竞争）
LIFECYCLE_MIN_BARS = 45  # 确认后至少经历的交易日（回吐归档兜底）
LIFECYCLE_MIN_EXCURSION_PCT = 0.25  # 有利方向至少走出 25%
LIFECYCLE_GIVEBACK_RATIO = 0.5  # 相对极值回吐至少一半 → 视为周期走完
# 测幅目标兑现：触及颈线±形态高度×该比例即归档（不依赖 45 根 / 回吐）
LIFECYCLE_TARGET_RATIO = 0.9

# 头肩失败破位归档（顶/底对称；默认保守，避免误杀仍在构筑者）
# 顶：确认后最低 < 颈线×DEPTH，且现价已回到颈线×RECOVER 上方 → 失败破位归档
# 底：确认后最高 > 颈线/DEPTH，且现价已回到颈线/RECOVER 下方 → 对称
HS_FAIL_DEPTH_MULT = 0.95
HS_FAIL_RECOVER_MULT = 1.02
# 辅：confirmed 破颈后反抽失败——现价回颈线另一侧，且（逼近/超过右肩 或 反抽幅度≥约 N·ATR）
# 不因「任意回到颈线上方」推翻 confirmed→forming；仅归档/降权
HS_FAIL_PULLBACK_ATR_MULT = 2.0
HS_FAIL_RS_NEAR_PCT = 0.02  # 相对右肩 ±2% 视为逼近
# 辅：右肩完成后 N 根交易日仍未收盘破颈 → forming 超时归档（0=关闭）
HS_FORMING_TIMEOUT_BARS = 90

# 楔形端点方向：末高/末低相对首枢轴的相对容差（抗噪声，非严格逐点单调）
WEDGE_ENDPOINT_REL_EPS = 0.002

# 楔形斜率收敛：下降要求 |上沿| > |下沿|；上升对称。相对/绝对容差抗数值噪声
WEDGE_SLOPE_CONV_REL_EPS = 0.05
WEDGE_SLOPE_CONV_ABS_EPS = 1e-9

# 巩固形态 NMS：上下沿相对差 ≤ 该阈值视为同界；枢轴价序列亦用此容差判同源
NMS_BOUND_REL_TOL = 0.01

# 斜率单位说明（linreg 自变量为枢轴的 K 线 index）
SLOPE_UNIT_NOTE = "元/K线索引(约交易日)"


def breakout_up(last_close: float, upper: float) -> bool:
    return upper > 0 and last_close > upper * BREAKOUT_UP_MULT


def breakout_down(last_close: float, lower: float) -> bool:
    return lower > 0 and last_close < lower * BREAKOUT_DOWN_MULT


def consolidation_status(
    last_close: float,
    upper: float,
    lower: float,
    *,
    expect_up: bool = False,
    expect_down: bool = False,
) -> tuple[str, str]:
    """巩固形态状态：预期方向突破→confirmed；反向脱离通道→invalidated；否则 forming。

    返回 (status, note)；note 非空时可拼进 reason。
    """
    up = breakout_up(last_close, upper)
    down = breakout_down(last_close, lower)
    if expect_up and up:
        return "confirmed", ""
    if expect_down and down:
        return "confirmed", ""
    if expect_up and expect_down:
        # 对称三角：任一方向突破均确认
        if up or down:
            return "confirmed", ""
        return "forming", ""
    # 单边预期：反向有效突破 → 形态假设失效
    if expect_up and down:
        return "invalidated", "失效:收盘已向下脱离通道"
    if expect_down and up:
        return "invalidated", "失效:收盘已向上脱离通道"
    return "forming", ""


def invalidate_bottom(last_close: float, low_ref: float) -> bool:
    """底部形态：价位跌破参考低点 × 0.99（可用于 close 或 low）。"""
    return low_ref > 0 and last_close < low_ref * INVALIDATE_BOTTOM_MULT


def invalidate_top(last_close: float, high_ref: float) -> bool:
    """顶部形态：价位升破参考高点 × 1.01（可用于 close 或 high）。"""
    return high_ref > 0 and last_close > high_ref * INVALIDATE_TOP_MULT


def post_pivot_invalidate_top(
    bars: Sequence[Dict[str, Any]],
    pivot_index: int,
    high_ref: float,
) -> bool:
    """枢轴日之后：任一 high 或 close > high_ref × INVALIDATE_TOP_MULT。"""
    if high_ref <= 0 or pivot_index < 0:
        return False
    start = int(pivot_index) + 1
    for i in range(start, len(bars)):
        b = bars[i]
        try:
            h = float(b.get("high"))
            c = float(b.get("close"))
        except (TypeError, ValueError):
            continue
        if (h == h and invalidate_top(h, high_ref)) or (
            c == c and invalidate_top(c, high_ref)
        ):
            return True
    return False


def post_pivot_invalidate_bottom(
    bars: Sequence[Dict[str, Any]],
    pivot_index: int,
    low_ref: float,
) -> bool:
    """枢轴日之后：任一 low 或 close < low_ref × INVALIDATE_BOTTOM_MULT。"""
    if low_ref <= 0 or pivot_index < 0:
        return False
    start = int(pivot_index) + 1
    for i in range(start, len(bars)):
        b = bars[i]
        try:
            lo = float(b.get("low"))
            c = float(b.get("close"))
        except (TypeError, ValueError):
            continue
        if (lo == lo and invalidate_bottom(lo, low_ref)) or (
            c == c and invalidate_bottom(c, low_ref)
        ):
            return True
    return False
