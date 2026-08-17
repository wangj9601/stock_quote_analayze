# -*- coding: utf-8 -*-
"""URT 回测详情 PDF：HTML + xhtml2pdf（CJK 字体）。"""

from __future__ import annotations

import html
import io
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

EXIT_MODE_LABELS = {
    "hit_rate": "命中率（不止损）",
    "signal_hit_rate": "命中率（不止损）",
    "risk_exit": "纪律出场（止损/连跌/回撤）",
    "structure_exit": "结构出场（支撑止损/阻力止盈）",
}

EXIT_REASON_ZH = {
    "target_hit": "触及目标",
    "horizon_end": "到期平仓",
    "price_stop": "价格止损",
    "time_stop": "时间止损",
    "trailing_take_profit": "回撤止盈",
    "structure_stop": "结构止损",
    "structure_target": "阻力止盈",
    "pct_target": "百分比止盈",
    "breakeven_stop": "保本止损",
    "fallback_trail": "移动止盈",
    "rule_exit": "规则离场",
    "stop_loss": "止损",
}

STOCK_POOL_LABELS = {
    "all": "全市场",
    "watchlist": "自选股",
    "industry_board": "行业板块",
    "concept_board": "概念板块",
    "single": "单股回测",
    "custom": "自定义列表",
}

CN_BOARD_LABELS = {
    "MAIN": "主板",
    "CYB": "创业板",
    "SZ_SME": "中小板",
    "KCB": "科创板",
    "BJ": "北证",
}


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def _pct(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


def _num(v: Any) -> str:
    if v is None:
        return "-"
    try:
        return str(float(v) if not isinstance(v, (int, float)) else v)
    except (TypeError, ValueError):
        return "-"


def resolve_exit_mode(task: Dict[str, Any]) -> str:
    summary = task.get("summary") if isinstance(task.get("summary"), dict) else {}
    config = task.get("config") if isinstance(task.get("config"), dict) else {}
    risk = summary.get("risk_params") if isinstance(summary.get("risk_params"), dict) else {}
    cfg_risk = config.get("risk_params") if isinstance(config.get("risk_params"), dict) else {}
    raw = (
        summary.get("exit_mode")
        or config.get("exit_mode")
        or risk.get("exit_mode")
        or cfg_risk.get("exit_mode")
        or summary.get("backtest_mode")
        or ""
    )
    m = str(raw or "").strip().lower()
    if m == "structure_exit":
        return "structure_exit"
    if m == "risk_exit":
        return "risk_exit"
    if m in ("signal_hit_rate", "hit_rate"):
        return "hit_rate"
    if summary.get("apply_stop_loss") is True:
        return "risk_exit"
    return "hit_rate"


def exit_mode_label(mode: str) -> str:
    return EXIT_MODE_LABELS.get(mode, mode or "命中率（不止损）")


def register_cjk_font() -> str:
    """注册 xhtml2pdf 可用的中文字体，返回 CSS font-family 名。

    优先使用 ReportLab 内置 CID 字体 STSong-Light（简体），避免仅 registerFont
    而未 @font-face 时 xhtml2pdf 回退 Helvetica 导致中文方框。
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError:
        return "Helvetica"

    names = set(pdfmetrics.getRegisteredFontNames())
    if "STSong-Light" not in names:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            logger.info("URT PDF 已注册 CID 字体: STSong-Light")
        except Exception:
            logger.exception("注册 STSong-Light 失败")
            return "Helvetica"
    return "STSong-Light"


def _resolve_font_family() -> str:
    return register_cjk_font()


def _kv_table(rows: Sequence[Tuple[str, str]]) -> str:
    cells = []
    for k, v in rows:
        if v is None or v == "":
            continue
        cells.append(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>")
    if not cells:
        return "<p class='muted'>暂无</p>"
    return f"<table class='kv'>{''.join(cells)}</table>"


def _data_table(headers: Sequence[str], body: Sequence[Sequence[Any]]) -> str:
    if not body:
        return "<p class='muted'>暂无</p>"
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    trs = []
    for row in body:
        trs.append("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"


def _stock_pool_label(config: Dict[str, Any]) -> str:
    mode = str(config.get("stock_pool_mode") or "all")
    base = STOCK_POOL_LABELS.get(mode, mode)
    pool = config.get("stock_pool")
    if isinstance(pool, list) and pool and mode != "all":
        return f"{base}（{len(pool)} 只）"
    return base


def _risk_alert(mode: str) -> str:
    if mode == "structure_exit":
        return "当前回测为「结构出场」：支撑止损/阻力止盈参与模拟；下方百分比风控作回退与文档快照。"
    if mode == "risk_exit":
        return "当前回测为「纪律出场」：以下价格止损/连跌/回撤参数参与出场模拟。"
    return "当前回测为「命中率/不止损」模式：以下风控参数仅作策略配置快照，不参与出场模拟。"


def build_backtest_detail_html(
    task: Dict[str, Any],
    logs: Optional[Sequence[Any]] = None,
) -> str:
    """根据任务详情与日志生成 xhtml2pdf 友好 HTML。"""
    config = task.get("config") if isinstance(task.get("config"), dict) else {}
    summary = task.get("summary") if isinstance(task.get("summary"), dict) else {}
    mode = resolve_exit_mode(task)
    mode_label = exit_mode_label(mode)

    basic: List[Tuple[str, str]] = [
        ("任务ID", str(task.get("task_id") or "")[:8] or "-"),
        ("名称", str(task.get("name") or "-")),
        ("状态", str(task.get("status") or "-")),
        ("进度", f"{int(float(task.get('progress') or 0))}%"),
        ("创建时间", str(task.get("created_at") or "-")),
    ]
    if config:
        basic.append(("股票池", _stock_pool_label(config)))
        seg = str(config.get("cn_board_segment") or "").upper()
        if seg and seg != "ALL":
            basic.append(("A股板块", CN_BOARD_LABELS.get(seg, seg)))
        basic.extend(
            [
                ("日期范围", f"{config.get('start_date') or '-'} ~ {config.get('end_date') or '-'}"),
                ("目标涨幅", f"{float(config.get('target_pct') or 0) * 100:.1f}%"),
                ("观察期", f"{config.get('horizon_days') if config.get('horizon_days') is not None else 20} 个交易日"),
                ("最低得分", str(config.get("min_score") if config.get("min_score") is not None else summary.get("min_score") or "-")),
                ("优先读缓存", "是" if config.get("use_trace") else "否"),
                ("出场模式", mode_label),
            ]
        )
        if summary.get("stock_pool_size") is not None:
            basic.append(("股票池规模", str(summary.get("stock_pool_size"))))

    trade_logic = summary.get("trade_logic") or config.get("trade_logic") or {}
    if not isinstance(trade_logic, dict):
        trade_logic = {}
    trade_parts: List[str] = []
    if trade_logic.get("summary"):
        trade_parts.append(f"<p class='note'>{_esc(trade_logic.get('summary'))}</p>")
    rules = trade_logic.get("rules")
    if isinstance(rules, list) and rules:
        trade_parts.append(
            "<ol>" + "".join(f"<li>{_esc(r)}</li>" for r in rules) + "</ol>"
        )
    exit_pri = trade_logic.get("exit_priority")
    if isinstance(exit_pri, list) and exit_pri:
        trade_parts.append(
            _data_table(
                ["优先级", "出场类型", "代码", "判定说明"],
                [
                    [
                        i + 1,
                        r.get("label") or EXIT_REASON_ZH.get(str(r.get("code") or ""), r.get("code") or ""),
                        r.get("code") or "",
                        r.get("desc") or "",
                    ]
                    for i, r in enumerate(exit_pri)
                    if isinstance(r, dict)
                ],
            )
        )
    trade_html = "".join(trade_parts) or "<p class='muted'>暂无交易逻辑说明</p>"

    risk = (
        summary.get("risk_params")
        or config.get("risk_params")
        or config.get("strategy_risk")
        or {}
    )
    if not isinstance(risk, dict):
        risk = {}
    risk_parts = [f"<p class='note'>{_esc(_risk_alert(mode))}</p>"]
    if risk.get("stop_loss_pct_max") is not None or risk.get("time_stop_down_days") is not None:
        risk_rows: List[Tuple[str, str]] = [
            (
                "价格止损阈值",
                f"−{_num(risk.get('stop_loss_pct_max'))}%（文档区间 {_num(risk.get('stop_loss_pct_min'))}%–{_num(risk.get('stop_loss_pct_max'))}%）",
            ),
            ("时间止损", f"连续收跌 ≥ {risk.get('time_stop_down_days') if risk.get('time_stop_down_days') is not None else '-'} 日"),
            (
                "止盈警惕涨幅",
                f"{_num(risk.get('take_profit_alert_pct_min'))}%–{_num(risk.get('take_profit_alert_pct_max'))}%",
            ),
            ("高点回撤止盈", f"≥ {_num(risk.get('trailing_drawdown_pct'))}%"),
        ]
        if risk.get("structure_stop_buffer_pct") is not None:
            try:
                buf = f"{float(risk.get('structure_stop_buffer_pct')) * 100:.0f}%"
            except (TypeError, ValueError):
                buf = str(risk.get("structure_stop_buffer_pct"))
            risk_rows.append(("结构止损缓冲", buf))
        risk_rows.append(("出场模式", mode_label))
        risk_parts.append(_kv_table(risk_rows))
    else:
        risk_parts.append("<p class='muted'>暂无风控参数快照</p>")
    risk_html = "".join(risk_parts)

    if summary:
        s_rows: List[Tuple[str, str]] = [
            ("信号数", str(summary.get("total_signals") if summary.get("total_signals") is not None else summary.get("total_samples") or 0)),
            ("命中数", str(summary.get("target_hits") if summary.get("target_hits") is not None else summary.get("hit_count") or 0)),
            ("命中率", _pct(summary.get("hit_rate"))),
            ("胜率", _pct(summary.get("win_rate"))),
            ("均盈亏(期末)", f"{summary.get('avg_pnl_pct') if summary.get('avg_pnl_pct') is not None else '-'}%"),
            ("均最大涨幅", f"{summary.get('avg_max_gain_pct') if summary.get('avg_max_gain_pct') is not None else '-'}%"),
            ("目标涨幅", f"{float(summary.get('target_pct') or 0) * 100:.1f}%"),
            ("出场模式", mode_label),
        ]
        if summary.get("avg_bars_held") is not None:
            s_rows.append(("均持有天数", str(summary.get("avg_bars_held"))))
        summary_html = _kv_table(s_rows)
    else:
        summary_html = "<p class='muted'>暂无汇总</p>"

    structure_html = ""
    ses = summary.get("structure_exit_stats")
    if isinstance(ses, dict):
        structure_html = "<h2>结构出场归因</h2>" + _kv_table(
            [
                ("结构止损", str(ses.get("structure_stop") or 0)),
                ("阻力止盈", str(ses.get("structure_target") or 0)),
                ("百分比止盈", str(ses.get("pct_target") or 0)),
                ("百分比止损回退", str(ses.get("price_stop") or 0)),
                ("保本止损", str(ses.get("breakeven_stop") or 0)),
                ("移动止盈", str(ses.get("fallback_trail") or 0)),
                ("分批出场", str(ses.get("partial_exit_count") or 0)),
                ("到期平仓", str(ses.get("horizon_end") or 0)),
                ("结构缺失回退率", _pct(ses.get("structure_fallback_rate"))),
                ("回退-无支撑", str(ses.get("fallback_no_support") or 0)),
                ("回退-止损≥入场", str(ses.get("fallback_stop_above_entry") or 0)),
                ("弱结构笔数", str(ses.get("weak_structure_count") or 0)),
                ("KDE重算笔数", str(ses.get("kde_recomputed_count") or 0)),
            ]
        )

    buckets_html = ""
    buckets = summary.get("by_score_bucket")
    if isinstance(buckets, dict) and buckets:
        buckets_html = "<h2>按分数分桶</h2>" + _data_table(
            ["分桶", "样本数", "命中", "命中率"],
            [
                [
                    name,
                    (buckets[name] or {}).get("total") or 0,
                    (buckets[name] or {}).get("hit") or 0,
                    _pct((buckets[name] or {}).get("hit_rate")),
                ]
                for name in buckets
            ],
        )

    exit_html = ""
    dist = summary.get("exit_reason_dist")
    if isinstance(dist, dict) and dist:
        exit_html = "<h2>离场原因分布</h2>" + _data_table(
            ["原因", "中文", "笔数"],
            [[name, EXIT_REASON_ZH.get(name, name), dist[name]] for name in dist],
        )

    log_lines: List[str] = []
    for item in (logs or [])[:80]:
        if isinstance(item, dict):
            log_lines.append(str(item.get("text") or item.get("message") or item))
        else:
            log_lines.append(str(item))
    logs_html = (
        f"<pre class='logs'>{_esc(chr(10).join(log_lines))}</pre>"
        if log_lines
        else "<p class='muted'>暂无日志</p>"
    )

    font_family = _resolve_font_family()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<title>URT 交易回测详情</title>
<style>
@page {{ size: a4; margin: 1.5cm; }}
body, p, h1, h2, h3, li, td, th, span, div, pre {{
  font-family: {font_family};
  font-size: 10pt;
  line-height: 1.45;
  color: #222;
}}
h1 {{ font-size: 16pt; margin: 0 0 10px; }}
h2 {{
  font-size: 12pt;
  margin: 14px 0 6px;
  color: #1e40af;
  border-bottom: 1px solid #bfdbfe;
  padding-bottom: 3px;
}}
.note {{
  margin: 0 0 8px;
  padding: 6px 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}}
.muted {{ color: #94a3b8; }}
table {{ width: 100%; border-collapse: collapse; margin: 4px 0 8px; font-size: 9pt; }}
th, td {{ border: 1px solid #ccc; padding: 3px 6px; text-align: left; vertical-align: top; }}
th {{ background: #f1f5f9; }}
table.kv th {{ width: 32%; }}
ol {{ margin: 0 0 8px; padding-left: 18px; }}
.logs {{
  white-space: pre-wrap;
  word-wrap: break-word;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 6px;
  font-size: 8pt;
}}
</style>
</head>
<body>
  <h1>URT 交易回测详情</h1>
  <h2>基本信息</h2>
  {_kv_table(basic)}
  <h2>交易逻辑细节</h2>
  {trade_html}
  <h2>风控参数</h2>
  {risk_html}
  <h2>汇总统计</h2>
  {summary_html}
  {structure_html}
  {buckets_html}
  {exit_html}
  <h2>日志</h2>
  {logs_html}
</body>
</html>
"""


def render_backtest_pdf(
    task: Dict[str, Any],
    logs: Optional[Sequence[Any]] = None,
) -> bytes:
    """生成 PDF 字节流。依赖 xhtml2pdf。"""
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError("服务端PDF导出依赖未安装：请安装 xhtml2pdf（pip install xhtml2pdf）") from e

    register_cjk_font()
    html_content = build_backtest_detail_html(task, logs=logs)
    output = io.BytesIO()
    status = pisa.CreatePDF(html_content, dest=output, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"xhtml2pdf 生成PDF失败（错误数 {status.err}）")
    pdf_bytes = output.getvalue()
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError("生成的内容不是有效PDF")
    return pdf_bytes
