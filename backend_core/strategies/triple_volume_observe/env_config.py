"""扫描范围：环境变量（与 user_push_configs 通知订阅解耦）。"""

import os
from dataclasses import dataclass
from typing import List, Optional


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


@dataclass
class TripleVolumeScanEnvConfig:
    enabled: bool
    markets: List[str]  # CN, HK
    board_keys: List[str]  # 空表示不限板块（仍排除 ST）
    volume_ratio: float


def load_scan_env() -> TripleVolumeScanEnvConfig:
    enabled = _env("TRIPLE_VOLUME_OBSERVE_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    raw_m = _env("TRIPLE_VOLUME_MARKETS", "CN").upper()
    markets = [x.strip() for x in raw_m.split(",") if x.strip()]
    if not markets:
        markets = ["CN"]
    boards_raw = _env("TRIPLE_VOLUME_BOARDS", "")
    board_keys = [b.strip().upper() for b in boards_raw.split(",") if b.strip()]
    try:
        ratio = float(_env("TRIPLE_VOLUME_RATIO", "3") or "3")
    except ValueError:
        ratio = 3.0
    if ratio <= 0:
        ratio = 3.0
    return TripleVolumeScanEnvConfig(
        enabled=enabled,
        markets=markets,
        board_keys=board_keys,
        volume_ratio=ratio,
    )


def is_triple_volume_observe_enabled() -> bool:
    """是否启用 3倍量观察股定时任务 / 对应微信推送。"""
    return load_scan_env().enabled


# 定时推送与微信通知使用的 report_type（关闭时 PushService 直接跳过）
TRIPLE_VOLUME_PUSH_REPORT_TYPES = frozenset(
    ("triple_volume_observe_scan", "triple_volume_observe_eval")
)
