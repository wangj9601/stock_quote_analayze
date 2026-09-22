"""推荐简报可配置常量。"""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple


def _env_int(key: str, default: int) -> int:
    raw = (os.getenv(key) or "").strip()
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return int(raw)
    return default


def _env_float(key: str, default: float) -> float:
    raw = (os.getenv(key) or "").strip()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# 角色小加分
ROLE_BONUS_LEADER = _env_float("RECOMMEND_ROLE_BONUS_LEADER", 3.0)
ROLE_BONUS_MID = _env_float("RECOMMEND_ROLE_BONUS_MID", 2.0)

# 默认主策略优先级（regime 可覆盖）
STRATEGY_PRIORITY = ("csb", "urt", "gms", "sbbr", "rpe", "zhab")
STRATEGY_PRIORITY_RANGE = ("csb", "urt", "gms", "zhab", "sbbr", "rpe")
STRATEGY_PRIORITY_TREND = ("gms", "urt", "csb", "zhab", "sbbr", "rpe")

# 清单规模
DAILY_TOP_EXECUTABLE = _env_int("RECOMMEND_DAILY_TOP_EXEC", 15)
DAILY_TOP_WATCH = _env_int("RECOMMEND_DAILY_TOP_WATCH", 25)
DAILY_TOP_EXEC_DEFENSE = _env_int("RECOMMEND_DAILY_TOP_EXEC_DEFENSE", 5)

# 分散约束
MAX_PER_BOARD_EXECUTABLE = _env_int("RECOMMEND_MAX_PER_BOARD", 2)
MAX_THEME_BOARDS_EXECUTABLE = _env_int("RECOMMEND_MAX_THEME_BOARDS", 3)

# 防追高
ANTI_CHASE_ABOVE_ZONE_PCT = _env_float("RECOMMEND_ANTI_CHASE_ABOVE_ZONE_PCT", 0.05)
ANTI_CHASE_N_DAY_GAIN_PCT = _env_float("RECOMMEND_ANTI_CHASE_N_DAY_GAIN", 18.0)
ANTI_CHASE_LOOKBACK_DAYS = _env_int("RECOMMEND_ANTI_CHASE_LOOKBACK", 5)

# 板环境否决（极弱辅助；主路径用 E_slope）
BOARD_SLOPE_VETO_5 = _env_float("RECOMMEND_BOARD_SLOPE_VETO_5", -0.002)
BOARD_SLOPE_VETO_10 = _env_float("RECOMMEND_BOARD_SLOPE_VETO_10", -0.0015)

# E_slope：负斜率映射到 [NEG_MIN, NEG_MAX]；低于 FLOOR 强制 watch
E_SLOPE_NEG_MIN = _env_float("RECOMMEND_E_SLOPE_NEG_MIN", 0.2)
E_SLOPE_NEG_MAX = _env_float("RECOMMEND_E_SLOPE_NEG_MAX", 0.4)
E_SLOPE_FLOOR = _env_float("RECOMMEND_E_SLOPE_FLOOR", 0.15)
E_SLOPE_POS_CAP = _env_float("RECOMMEND_E_SLOPE_POS_CAP", 1.0)
E_SLOPE_DEFENSE_THRESHOLD = _env_float("RECOMMEND_E_SLOPE_DEFENSE_THRESHOLD", 0.5)

# 总分权重
SCORE_W_BASE = _env_float("RECOMMEND_SCORE_W_BASE", 0.7)
SCORE_W_SR = _env_float("RECOMMEND_SCORE_W_SR", 0.3)

# 无分策略默认质量（SBBR）
QUALITY_DEFAULT_MISSING = _env_float("RECOMMEND_QUALITY_DEFAULT_MISSING", 50.0)

# 场景 regime：大盘 20 日斜率阈值
REGIME_TREND_SLOPE_MIN = _env_float("RECOMMEND_REGIME_TREND_SLOPE_MIN", 0.0005)

# VP / SR
SR_VP_LOOKBACK = _env_int("RECOMMEND_SR_VP_LOOKBACK", 60)
SR_VP_MAX_CODES = _env_int("RECOMMEND_SR_VP_MAX_CODES", 80)
SR_BAND_PCT_LOW = _env_float("RECOMMEND_SR_BAND_PCT_LOW", 0.02)
SR_BAND_PCT_HIGH = _env_float("RECOMMEND_SR_BAND_PCT_HIGH", 0.05)
SR_EXTREMA_LOOKBACK = _env_int("RECOMMEND_SR_EXTREMA_LOOKBACK", 20)

# 主题对齐加分
THEME_ALIGN_BONUS = _env_float("RECOMMEND_THEME_ALIGN_BONUS", 3.0)

# 尾盘确认
LATE_UPPER_SHADOW_RATIO = _env_float("RECOMMEND_LATE_UPPER_SHADOW_RATIO", 0.45)
LATE_FALSE_BREAK_PCT = _env_float("RECOMMEND_LATE_FALSE_BREAK_PCT", 0.01)

# 周/月
WEEKLY_MAIN_BOARDS = _env_int("RECOMMEND_WEEKLY_MAIN_BOARDS", 5)
WEEKLY_WATCH_POOL = _env_int("RECOMMEND_WEEKLY_WATCH_POOL", 30)
MONTHLY_THEME_BOARDS = _env_int("RECOMMEND_MONTHLY_THEME_BOARDS", 5)
MONTHLY_CORE_PER_THEME = _env_int("RECOMMEND_MONTHLY_CORE_PER_THEME", 3)

# 大盘环境指数
MARKET_INDEX_CODE = (os.getenv("RECOMMEND_MARKET_INDEX") or "000300").strip()

FORMULA_VERSION = "v2_eslope_sr"


def strategy_priority_for_regime(regime: str) -> Tuple[str, ...]:
    if regime == "trend":
        return STRATEGY_PRIORITY_TREND
    return STRATEGY_PRIORITY_RANGE


def brief_config_snapshot() -> Dict[str, Any]:
    return {
        "role_bonus_leader": ROLE_BONUS_LEADER,
        "role_bonus_mid": ROLE_BONUS_MID,
        "max_per_board": MAX_PER_BOARD_EXECUTABLE,
        "max_theme_boards": MAX_THEME_BOARDS_EXECUTABLE,
        "anti_chase_above_zone_pct": ANTI_CHASE_ABOVE_ZONE_PCT,
        "daily_top_exec": DAILY_TOP_EXECUTABLE,
        "daily_top_watch": DAILY_TOP_WATCH,
        "daily_top_exec_defense": DAILY_TOP_EXEC_DEFENSE,
        "e_slope_neg_min": E_SLOPE_NEG_MIN,
        "e_slope_neg_max": E_SLOPE_NEG_MAX,
        "e_slope_floor": E_SLOPE_FLOOR,
        "e_slope_defense_threshold": E_SLOPE_DEFENSE_THRESHOLD,
        "score_w_base": SCORE_W_BASE,
        "score_w_sr": SCORE_W_SR,
        "formula_version": FORMULA_VERSION,
        "theme_align_bonus": THEME_ALIGN_BONUS,
    }
