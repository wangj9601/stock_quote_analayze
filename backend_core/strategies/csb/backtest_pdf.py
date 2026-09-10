# -*- coding: utf-8 -*-
"""CSB 回测 PDF 报告（简化版，接口对齐 URT）。"""

from __future__ import annotations

import html
import io
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXIT_MODE_LABELS = {
    "hit_rate": "命中率（不止损）",
    "risk_exit": "纪律出场",
    "structure_exit": "结构出场（假突破/基准/MA跟踪）",
}


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def _pct_rate(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


def resolve_exit_mode(task: Dict[str, Any]) -> str:
    summary = task.get("summary") if isinstance(task.get("summary"), dict) else {}
    config = task.get("config") if isinstance(task.get("config"), dict) else {}
    raw = summary.get("exit_mode") or config.get("exit_mode") or summary.get("backtest_mode") or "hit_rate"
    m = str(raw).strip().lower()
    if m in ("structure_exit", "risk_exit"):
        return m
    return "hit_rate"


def build_csb_backtest_html(task: Dict[str, Any]) -> str:
    summary = task.get("summary") or {}
    config = task.get("config") or {}
    mode = resolve_exit_mode(task)
    rows = [
        ("任务名称", task.get("name")),
        ("区间", f"{config.get('start_date')} ~ {config.get('end_date')}"),
        ("出场模式", EXIT_MODE_LABELS.get(mode, mode)),
        ("信号数", summary.get("total_signals")),
        ("命中率", _pct_rate(summary.get("hit_rate"))),
        ("胜率", _pct_rate(summary.get("win_rate"))),
        ("均盈亏", summary.get("avg_pnl_pct")),
        ("均最大涨幅", summary.get("avg_max_gain_pct")),
    ]
    body_rows = "".join(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>" for k, v in rows)
    logic = summary.get("trade_logic") or {}
    rules = logic.get("rules") or []
    rules_html = "".join(f"<li>{_esc(r)}</li>" for r in rules)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>CSB回测报告</title></head>
<body><h1>CSB 回测报告</h1><table>{body_rows}</table>
<h2>交易逻辑</h2><p>{_esc(logic.get('summary'))}</p><ul>{rules_html}</ul></body></html>"""


def render_csb_backtest_pdf(task: Dict[str, Any]) -> Optional[bytes]:
    """生成 PDF；无 xhtml2pdf 时返回 None。"""
    try:
        from xhtml2pdf import pisa
    except ImportError:
        logger.warning("xhtml2pdf 未安装，跳过 CSB PDF")
        return None
    html_content = build_csb_backtest_html(task)
    buf = io.BytesIO()
    pisa.CreatePDF(html_content, dest=buf)
    return buf.getvalue()
