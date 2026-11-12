# -*- coding: utf-8 -*-
"""行业交易观察池自动候选：默认参数。"""

from __future__ import annotations

import os

from backend_core.board_gates.config import DEFAULT_BOARD_CODE_SOURCE, TREND_AVOID_MIDLONG

IN_SCORE_THRESHOLD = int(os.environ.get("OBSERVE_CANDIDATE_IN_THRESHOLD") or 2)
IN_CONFIRM_DAYS = int(os.environ.get("OBSERVE_CANDIDATE_IN_CONFIRM_DAYS") or 2)
OUT_CONFIRM_DAYS = int(os.environ.get("OBSERVE_CANDIDATE_OUT_CONFIRM_DAYS") or 3)
TOP_N_NEW = int(os.environ.get("OBSERVE_CANDIDATE_TOP_N") or 15)
SOFT_CAP = int(os.environ.get("OBSERVE_CANDIDATE_SOFT_CAP") or 40)
RS_SCORE_MIN = int(os.environ.get("OBSERVE_CANDIDATE_RS_SCORE_MIN") or 60)
RS_VETO_MAX = int(os.environ.get("OBSERVE_CANDIDATE_RS_VETO_MAX") or 29)
MIN_HIST_BARS = int(os.environ.get("OBSERVE_CANDIDATE_MIN_BARS") or 120)
MAINLINE_LOOKBACK_HITS = 2
SENTIMENT_TOP_N = 15

ACTION_SUGGEST_IN = "suggest_in"
ACTION_SUGGEST_OUT = "suggest_out"
ACTION_IN_POOL = "in_pool"
ACTION_WATCH = "watch"

LOCK_FOLLOW = "follow"
LOCK_INCLUDE = "include"
LOCK_EXCLUDE = "exclude"

SOURCE_MANUAL = "manual"
SOURCE_ADOPTED_AUTO = "adopted_auto"
SOURCE_SYNC = "sync"

TREND_VETO = TREND_AVOID_MIDLONG

__all__ = [
    "DEFAULT_BOARD_CODE_SOURCE",
    "IN_SCORE_THRESHOLD",
    "IN_CONFIRM_DAYS",
    "OUT_CONFIRM_DAYS",
    "TOP_N_NEW",
    "SOFT_CAP",
    "RS_SCORE_MIN",
    "RS_VETO_MAX",
    "MIN_HIST_BARS",
    "MAINLINE_LOOKBACK_HITS",
    "SENTIMENT_TOP_N",
    "ACTION_SUGGEST_IN",
    "ACTION_SUGGEST_OUT",
    "ACTION_IN_POOL",
    "ACTION_WATCH",
    "LOCK_FOLLOW",
    "LOCK_INCLUDE",
    "LOCK_EXCLUDE",
    "SOURCE_MANUAL",
    "SOURCE_ADOPTED_AUTO",
    "SOURCE_SYNC",
    "TREND_VETO",
]
