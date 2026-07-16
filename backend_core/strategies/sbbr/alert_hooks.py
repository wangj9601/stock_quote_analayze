"""SBBR 告警钩子：入场 / 破位 / 退出。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _format_entry_message(rows: List[Dict[str, Any]], trade_date: str) -> str:
    lines = [f"【SBBR 做小做底】入场信号 {trade_date}", f"共 {len(rows)} 只："]
    for r in rows[:30]:
        lines.append(
            f"- {r.get('code')} {r.get('name') or ''} "
            f"模式={r.get('bottom_mode') or '-'} 收盘={r.get('close')} "
            f"防守下沿={r.get('defense_low')}"
        )
    if len(rows) > 30:
        lines.append(f"... 另有 {len(rows) - 30} 只")
    return "\n".join(lines)


def _format_position_message(events: List[Dict[str, Any]], trade_date: str) -> str:
    lines = [f"【SBBR 持仓评估】{trade_date}", f"事件 {len(events)} 条："]
    for e in events[:40]:
        lines.append(
            f"- {e.get('code')} {e.get('name') or ''} "
            f"类型={e.get('event_type')} 收盘={e.get('close')} "
            f"说明={e.get('message') or ''}"
        )
    return "\n".join(lines)


def notify_sbbr_events(
    *,
    entry_rows: Optional[List[Dict[str, Any]]] = None,
    position_events: Optional[List[Dict[str, Any]]] = None,
    trade_date: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    尝试通过 PushService / 日志广播告警。
    若推送基础设施不可用，则仅打日志，不抛错。
    """
    alert_cfg = (config or {}).get("alert") or {}
    result = {"entry_sent": False, "position_sent": False, "errors": []}

    messages: List[str] = []
    if entry_rows and alert_cfg.get("enable_entry", True):
        messages.append(_format_entry_message(entry_rows, trade_date))
    if position_events and (
        alert_cfg.get("enable_defense_breach", True) or alert_cfg.get("enable_exit", True)
    ):
        filtered = []
        for e in position_events:
            et = e.get("event_type")
            if et == "defense_breach" and not alert_cfg.get("enable_defense_breach", True):
                continue
            if et in ("exit_partial", "exit_full") and not alert_cfg.get("enable_exit", True):
                continue
            filtered.append(e)
        if filtered:
            messages.append(_format_position_message(filtered, trade_date))

    if not messages:
        return result

    text = "\n\n".join(messages)
    logger.info("SBBR alert:\n%s", text)

    try:
        from backend_api.services.push_service import PushService

        # 尽力推送给订阅了报告的用户；无专用 report_type 时写一条系统日志即可
        ps = PushService()
        if hasattr(ps, "broadcast_text"):
            ps.broadcast_text(text, title="SBBR做小做底告警")
            result["entry_sent"] = bool(entry_rows)
            result["position_sent"] = bool(position_events)
        elif hasattr(ps, "send_admin_notification"):
            ps.send_admin_notification(subject="SBBR做小做底告警", body=text)
            result["entry_sent"] = bool(entry_rows)
            result["position_sent"] = bool(position_events)
        else:
            # 无通用广播时，至少保证日志可见
            result["errors"].append("no_broadcast_api")
    except Exception as e:
        logger.warning("SBBR push failed (logged only): %s", e)
        result["errors"].append(str(e))

    return result
