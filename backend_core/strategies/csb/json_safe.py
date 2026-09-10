# -*- coding: utf-8 -*-
"""PostgreSQL JSON 安全序列化（独立副本，不依赖 GMS）。"""

from __future__ import annotations

import math
from typing import Any


def sanitize_for_pg_json(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    item = getattr(obj, "item", None)
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
