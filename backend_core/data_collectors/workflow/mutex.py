"""采集任务 / 流程运行互斥：单任务槽 + 多流程并行。"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

_lock = threading.Lock()
_active: Dict[str, str] = {}  # execution_id -> kind (task | workflow)


def try_acquire(kind: str, execution_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    尝试占用执行槽。
    - task：全局仅允许一个，且不能与任何 workflow 并发。
    - workflow：允许多个并行，但不能与 task 并发。
    返回 (ok, existing_kind, existing_id)。
    """
    with _lock:
        if kind == "task":
            if _active:
                eid, existing_kind = next(iter(_active.items()))
                return False, existing_kind, eid
            _active[execution_id] = kind
            return True, None, None

        if kind == "workflow":
            for eid, existing_kind in _active.items():
                if existing_kind == "task":
                    return False, existing_kind, eid
            _active[execution_id] = kind
            return True, None, None

        raise ValueError(f"unknown kind: {kind}")


def release(execution_id: str) -> None:
    """释放指定 execution_id 占用的槽位。"""
    with _lock:
        _active.pop(execution_id, None)


def get_active() -> Tuple[Optional[str], Optional[str]]:
    """返回任意一个活跃执行（兼容旧接口）。"""
    with _lock:
        if not _active:
            return None, None
        eid, kind = next(iter(_active.items()))
        return kind, eid


def list_active() -> List[Dict[str, str]]:
    """返回所有活跃执行列表。"""
    with _lock:
        return [{"kind": k, "id": eid} for eid, k in _active.items()]


def is_busy() -> bool:
    with _lock:
        return bool(_active)


def workflow_count() -> int:
    with _lock:
        return sum(1 for k in _active.values() if k == "workflow")
