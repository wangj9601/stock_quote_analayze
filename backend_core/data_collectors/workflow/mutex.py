"""采集任务 / 流程运行全局互斥（单执行器）。"""

from __future__ import annotations

import threading
from typing import Optional, Tuple

_lock = threading.Lock()
_active_kind: Optional[str] = None  # task | workflow
_active_id: Optional[str] = None


def try_acquire(kind: str, execution_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    尝试占用全局执行槽。
    返回 (ok, existing_kind, existing_id)。
    """
    global _active_kind, _active_id
    with _lock:
        if _active_id is not None:
            return False, _active_kind, _active_id
        _active_kind = kind
        _active_id = execution_id
        return True, None, None


def release(execution_id: str) -> None:
    """仅当持有者匹配时释放。"""
    global _active_kind, _active_id
    with _lock:
        if _active_id == execution_id:
            _active_kind = None
            _active_id = None


def get_active() -> Tuple[Optional[str], Optional[str]]:
    with _lock:
        return _active_kind, _active_id


def is_busy() -> bool:
    with _lock:
        return _active_id is not None
