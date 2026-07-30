"""PostgreSQL JSON/JSONB 安全序列化辅助。

Python json.dumps 默认 allow_nan=True，会产出 Token \"NaN\"，
PostgreSQL 的 json/jsonb 类型拒绝该写法，导致 INSERT 失败。
"""

from __future__ import annotations

import math
from typing import Any


def sanitize_for_pg_json(obj: Any) -> Any:
    """递归将 NaN/Inf（含 numpy 标量）转为 None，保证可写入 PG JSON。"""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    item = getattr(obj, "item", None)  # numpy 标量
    if callable(item):
        try:
            return sanitize_for_pg_json(item())
        except (ValueError, AttributeError, TypeError):
            return None
    if isinstance(obj, dict):
        return {k: sanitize_for_pg_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_pg_json(v) for v in obj]
    return obj


def finite_or_none(value: Any) -> Any:
    """单个数值：非有限浮点则返回 None，其余原样返回。"""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return finite_or_none(item())
        except (ValueError, AttributeError, TypeError):
            return None
    return value
