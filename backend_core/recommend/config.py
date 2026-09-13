"""推荐简报可配置常量（一期硬约束默认值）。"""

from __future__ import annotations

import os
from typing import Any, Dict


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


# 角色小加分（可配置，避免复杂双轨）
ROLE_BONUS_LEADER = _env_float("RECOMMEND_ROLE_BONUS_LEADER", 3.0)
ROLE_BONUS_MID = _env_float("RECOMMEND_ROLE_BONUS_MID", 2.0)

# 策略优先级（主策略展示用）
STRATEGY_PRIORITY = ("urt", "gms", "sbbr", "rpe")

# 清单规模
DAILY_TOP_EXECUTABLE = _env_int("RECOMMEND_DAILY_TOP_EXEC", 15)
DAILY_TOP_WATCH = _env_int("RECOMMEND_DAILY_TOP_WATCH", 25)

# 分散约束
MAX_PER_BOARD_EXECUTABLE = _env_int("RECOMMEND_MAX_PER_BOARD", 2)
MAX_THEME_BOARDS_EXECUTABLE = _env_int("RECOMMEND_MAX_THEME_BOARDS", 3)

# 防追高
ANTI_CHASE_ABOVE_ZONE_PCT = _env_float("RECOMMEND_ANTI_CHASE_ABOVE_ZONE_PCT", 0.05)
ANTI_CHASE_N_DAY_GAIN_PCT = _env_float("RECOMMEND_ANTI_CHASE_N_DAY_GAIN", 18.0)
ANTI_CHASE_LOOKBACK_DAYS = _env_int("RECOMMEND_ANTI_CHASE_LOOKBACK", 5)

# 板环境否决：短窗斜率阈值（负且明显）
BOARD_SLOPE_VETO_5 = _env_float("RECOMMEND_BOARD_SLOPE_VETO_5", -0.002)
BOARD_SLOPE_VETO_10 = _env_float("RECOMMEND_BOARD_SLOPE_VETO_10", -0.0015)

# 周/月
WEEKLY_MAIN_BOARDS = _env_int("RECOMMEND_WEEKLY_MAIN_BOARDS", 5)
WEEKLY_WATCH_POOL = _env_int("RECOMMEND_WEEKLY_WATCH_POOL", 30)
MONTHLY_THEME_BOARDS = _env_int("RECOMMEND_MONTHLY_THEME_BOARDS", 5)
MONTHLY_CORE_PER_THEME = _env_int("RECOMMEND_MONTHLY_CORE_PER_THEME", 3)

# 大盘环境指数
MARKET_INDEX_CODE = (os.getenv("RECOMMEND_MARKET_INDEX") or "000300").strip()


def brief_config_snapshot() -> Dict[str, Any]:
    return {
        "role_bonus_leader": ROLE_BONUS_LEADER,
        "role_bonus_mid": ROLE_BONUS_MID,
        "max_per_board": MAX_PER_BOARD_EXECUTABLE,
        "max_theme_boards": MAX_THEME_BOARDS_EXECUTABLE,
        "anti_chase_above_zone_pct": ANTI_CHASE_ABOVE_ZONE_PCT,
        "daily_top_exec": DAILY_TOP_EXECUTABLE,
        "daily_top_watch": DAILY_TOP_WATCH,
    }
