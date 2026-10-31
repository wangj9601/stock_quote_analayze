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
    # 最后一次收缩的最大深度
    max_last_depth: float = 0.12
    # 末端紧凑度：最近 N 日振幅上限（无完整收缩时的兜底）
    tight_days: int = 10
    max_tight_range: float = 0.08
    # 突破确认
    breakout_buffer: float = 0.002
    breakout_vol_multiple: float = 1.5
    vol_ma: int = 50
    # 距枢轴点多少以内算"就位待突破"
    ready_distance: float = 0.03
    # 距枢轴点超过多少算追高
    chase_distance: float = 0.06


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
    # 无两融数据时的中性分（避免直接筛掉非两融标的）
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


TIER_LABELS = {
    "A": "可执行",
    "B": "观察",
    "C": "跟踪",
}

VCP_STATUS_LABELS = {
    "breakout": "放量突破",
    "ready": "就位待突破",
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
