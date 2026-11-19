# -*- coding: utf-8 -*-
"""把各策略预计算返回值收成一条可展示的信号数量。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _as_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(payload: Dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        if key in payload and payload[key] is not None:
            number = _as_int(payload[key])
            if number is not None:
                return number
    return None


def _leaf_counts(payload: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    stored = _first_int(payload, "written", "saved")
    hits = _first_int(payload, "hits", "hit_count", "entry_count")
    if stored is None and hits is None:
        stored = _first_int(payload, "signal_count")
    return stored, hits


def _walk_counts(payload: Any) -> Tuple[Optional[int], Optional[int]]:
    if not isinstance(payload, dict):
        return None, None
    results = payload.get("results")
    if isinstance(results, list) and any(isinstance(item, dict) for item in results):
        stored_sum = 0
        hits_sum = 0
        seen_stored = False
        seen_hits = False
        for item in results:
            stored, hits = _walk_counts(item)
            if stored is not None:
                seen_stored = True
                stored_sum += stored
            if hits is not None:
                seen_hits = True
                hits_sum += hits
        return (
            stored_sum if seen_stored else None,
            hits_sum if seen_hits else None,
        )
    return _leaf_counts(payload)


def _is_failed(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("skipped"):
        return False
    if payload.get("success") is False or payload.get("ok") is False:
        return True
    results = payload.get("results")
    if isinstance(results, list):
        return any(_is_failed(item) for item in results if isinstance(item, dict))
    return False


def _error_text(payload: Any) -> str:
    if isinstance(payload, dict):
        if payload.get("error"):
            return str(payload["error"])
        results = payload.get("results")
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict) and (
                    item.get("success") is False or item.get("ok") is False
                ):
                    if item.get("error"):
                        return str(item["error"])
    return "预计算失败"


def describe_signal_counts(stored: Optional[int], hits: Optional[int]) -> Optional[str]:
    if stored is None and hits is None:
        return None
    if stored is not None and hits is not None and stored != hits:
        return f"写入 {stored} 条，买点 {hits} 条"
    count = stored if stored is not None else hits
    return f"信号 {count} 条"


def classify_signal_payload(name: str, payload: Any) -> Dict[str, Any]:
    """把预计算返回值变成节点日志用的结论。"""
    if isinstance(payload, dict) and payload.get("skipped"):
        reason = str(payload.get("reason") or payload.get("message") or "已跳过")
        return {
            "skipped": True,
            "failed": False,
            "signal_count": None,
            "written": None,
            "hits": None,
            "note": reason,
            "message": f"{name}已跳过：{reason}",
            "error": None,
        }

    stored, hits = _walk_counts(payload)
    phrase = describe_signal_counts(stored, hits)
    count = stored if stored is not None else hits
    failed = _is_failed(payload)
    if failed:
        message = f"{name}失败"
        if phrase:
            message += f"，{phrase}"
        return {
            "skipped": False,
            "failed": True,
            "signal_count": count,
            "written": stored,
            "hits": hits,
            "note": phrase or "",
            "message": message,
            "error": _error_text(payload),
        }

    message = f"{name}完成"
    if phrase:
        message += f"，{phrase}"
    return {
        "skipped": False,
        "failed": False,
        "signal_count": count,
        "written": stored,
        "hits": hits,
        "note": phrase or "",
        "message": message,
        "error": None,
    }


def pack_signal_runs(
    parts: List[Any],
    *,
    empty_reason: str = "无预计算版本",
) -> Dict[str, Any]:
    """把多个参数版本的预计算结果收成一份。"""
    if not parts:
        return {"skipped": True, "reason": empty_reason, "results": []}
    rows: List[Dict[str, Any]] = []
    for part in parts:
        if isinstance(part, dict):
            rows.append(part)
        else:
            rows.append({"success": False, "error": "预计算未返回结果"})
    failed = any(row.get("success") is False or row.get("ok") is False for row in rows)
    packed: Dict[str, Any] = {"success": not failed, "results": rows}
    if failed:
        packed["error"] = next(
            (
                str(row.get("error"))
                for row in rows
                if (row.get("success") is False or row.get("ok") is False) and row.get("error")
            ),
            "部分版本预计算失败",
        )
    return packed
