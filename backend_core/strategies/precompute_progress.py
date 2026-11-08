# -*- coding: utf-8 -*-
"""策略信号预计算进度日志：默认每完成 200 只打印一次。"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

_DEFAULT_EVERY = 200


def precompute_progress_every() -> int:
    raw = (os.getenv("PRECOMPUTE_PROGRESS_EVERY") or "").strip()
    if not raw:
        return _DEFAULT_EVERY
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_EVERY


def maybe_log_precompute_progress(
    logger: logging.Logger,
    strategy: str,
    done: int,
    total: int,
    *,
    state: Optional[Dict[str, Any]] = None,
    every: Optional[int] = None,
    extra: str = "",
) -> None:
    """
    在扫描循环中调用：跨过 every 边界或全部完成时打 info。
    state 用于记住上次已打印水位，避免分块跳号漏打/重复打。
    """
    if done <= 0 or total <= 0:
        return
    step = int(every) if every is not None else precompute_progress_every()
    step = max(1, step)
    st = state if state is not None else {}
    last = int(st.get("last") or 0)
    crossed = done // step > last // step
    finished = done >= total
    if not crossed and not finished:
        return
    # 完成时若刚好落在边界上，只打一条
    if finished and last >= total:
        return
    suffix = f" {extra}" if extra else ""
    logger.info(
        "%s 预计算进度：已完成 %s/%s%s",
        strategy,
        min(done, total),
        total,
        suffix,
    )
    st["last"] = min(done, total)
