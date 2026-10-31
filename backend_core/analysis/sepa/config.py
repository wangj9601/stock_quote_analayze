# -*- coding: utf-8 -*-
"""SEPA 参数集中管理：趋势模板 / VCP 形态 / 两融旁证。

阈值不散落在业务代码里，便于用真实行情做实证校准（改这里即可，不用动逻辑）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrendConfig:
    """趋势模板八条（Minervini, Trade Like a Stock Market Wizard）。"""

    ma_short: int = 50
    ma_mid: int = 150
    ma_long: int = 200
    # 条件 3：200 日线至少上行 N 个交易日（原文 1 个月，理想 4~5 个月）
    ma_long_rise_days: int = 20
    # 条件 6：距 52 周低点至少 +30%
    min_low_gain: float = 0.30
    # 条件 7：距 52 周高点回撤不超过 25%
    max_high_drawdown: float = 0.25
    # 条件 8：相对强度百分位下限（0~100）
    min_rs_rank: float = 70.0
    min_bars: int = 260
    # True：八条必须全满足；False：允许 7/8 进入观察池
    require_all: bool = True


@dataclass(frozen=True)
class VCPConfig:
    """VCP 波动收缩与枢轴点突破。摆动点复用 analysis.swing_zigzag。"""

    lookback: int = 130
    fractal_left: int = 2
    fractal_right: int = 2
    # 摆动幅度门槛：max(收盘价 * min_depth_pct, ATR * atr_mult)
    min_depth_pct: float = 0.025
    atr_mult: float = 1.5
    # 至少几次收缩
    min_contractions: int = 2
    # 后一次收缩允许比前一次略大的容差
    depth_tolerance: float = 0.05
    # 每次收缩量能至少比上次低多少
    min_vol_decay: float = 0.05
    # 最后一次收缩的最大深度。校准结论（800 只 × 97 个评估日，2024-10~2026-09）：
    # 0.10 最优（10 日超额 +0.43%），0.12 接近，0.15 转负，0.08 样本不足且为负。
    max_last_depth: float = 0.10
    # True：末次收缩过深时不再给突破/就位状态（降为"收缩中"观察位）。
    # 校准前该参数只影响评分不影响准入，导致"深度 20% 的假收缩"照样进 A 级。
    enforce_last_depth: bool = True
    # 末端紧凑度：最近 N 日振幅上限。实测这是全部条件里区分度最高的一条——
    # 同样的"距枢轴 3% 内"，不限振幅 10 日胜率 47.9%（中位 -0.45%），
    # 收紧到 8% 后升到 62.3%（中位 +2.28%）。
    tight_days: int = 10
    max_tight_range: float = 0.08
    # 突破确认。实测量能倍数 1.0/1.2/1.5 的 10 日超额在 ±0.3% 内无差异，
    # 3.0 倍量在 2024-10~2025-06 段 10 日均值 -3.64%（胜率 30%），属于追高，不予采用。
    # 量比低于该倍数、但价格已在枢轴上方时，单独标为 quiet（未放量越过），不并入收缩中。
    breakout_buffer: float = 0.002
    breakout_vol_multiple: float = 1.5
    vol_ma: int = 50
    # 距枢轴点多少以内算"就位待突破"。实测 -3% 窗口优于 -2%/-5%/-8%。
    ready_distance: float = 0.03
    # 可执行突破的距离上限。超过后标为 extended（远离枢轴），默认不进名单。
    # 校准：0~2% 略正，4~6% 已转负，故不再把 6% 以上当成买点。
    chase_distance: float = 0.06
    # 突破的有效距离上限。超过此值说明突破早就发生、股价已在枢轴上方很远，
    # 属于"看着像突破其实是追高"。实测按中位数：
    #   0~2% +0.16% / 2~4% -0.29% / 4~6% -1.28% / 6~10% -0.05% / 10~20% -2.83% / >20% -4.18%
    # 加此上限前，样例日 2026-06-30 的 5 个"突破"标的距枢轴 14%~53%，全部是追高。
    max_breakout_distance: float = 0.10


@dataclass(frozen=True)
class MarginConfig:
    """两融旁证：杠杆资金是否已完成出清、是否开始回流。"""

    lookback: int = 60
    reflow_days: int = 5
    min_reflow_pct: float = 0.0
    # 余额距窗口高点回落多少算出清充分
    clear_drawdown: float = 0.15
    crowd_max: float = 0.05
    net_buy_days: int = 3
    # 无两融数据时的中性分。分级上不降级（见 screener._tier），只在排序里略低于有数据的票。
    neutral_score: float = 40.0


@dataclass(frozen=True)
class SEPAConfig:
    trend: TrendConfig = field(default_factory=TrendConfig)
    vcp: VCPConfig = field(default_factory=VCPConfig)
    margin: MarginConfig = field(default_factory=MarginConfig)
    weight_vcp: float = 0.45
    weight_margin: float = 0.30
    weight_trend: float = 0.25
    top: int = 30
    # 排序时把"就位待突破"排在"放量突破"之前。
    # 依据：三期一致的实证（2024-10~2025-06 / 2025-07~12 / 2026-01~09）
    #   就位待突破 10 日胜率 62.7% / 62.7% / 60.0%，中位 +2.44% / +2.19% / +1.72%
    #   放量突破   10 日胜率 39.6% / 46.7% / 49.0%，中位 -2.22% / -1.12% / -0.29%
    # 突破日买进等于接最后一波浮筹，回吐概率高；买在收缩末端更符合 VCP 的原意。
    prefer_ready: bool = True


TIER_LABELS = {
    "A": "可执行",
    "B": "观察",
    "C": "跟踪",
}

VCP_STATUS_LABELS = {
    "breakout": "放量突破",
    "quiet": "未放量越过",
    "ready": "就位待突破",
    "extended": "远离枢轴",
    "forming": "收缩中",
    "none": "无形态",
}

MARGIN_STATUS_LABELS = {
    "reflow": "回流确认",
    "steady": "企稳",
    "clearing": "出清中",
    "crowded": "高位拥挤",
    "no_data": "无两融数据",
}

DISCLAIMER = (
    "价量形态 + 杠杆资金代理，非机构账户归属；"
    "突破信号为技术面提示，不构成投资建议"
)
