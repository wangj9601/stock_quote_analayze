# -*- coding: utf-8 -*-
"""周报 / 月报 Markdown 与 PDF。"""

from __future__ import annotations

import io
from typing import Any, Dict, List

from backend_core.market_review.pdf_export import (
    _esc,
    _fmt,
    _pattern_zh,
    _signed,
    _table,
    register_cjk_font,
)


def clean_industry_name(name: Any) -> str:
    """丢掉空值和 pandas 落库的 nan，只保留真实行业名。"""
    s = str(name or "").strip()
    if s.lower() in {"", "nan", "none", "null", "-", "--", "nat"}:
        return ""
    return s


def _num(v: Any, digits: int = 2) -> str:
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if digits == 0:
        return str(int(round(f)))
    return f"{f:.{digits}f}"


def _delta_line(pair: Dict[str, Any], unit: str = "", digits: int = 2) -> str:
    if not isinstance(pair, dict):
        return "—"
    a, b = pair.get("from"), pair.get("to")
    if a is None and b is None:
        return "—"
    try:
        if a is not None and b is not None:
            diff = float(b) - float(a)
            sign = "+" if diff > 0 else ""
            return f"{_num(a, digits)} → {_num(b, digits)}（{sign}{_num(diff, digits)}{unit}）"
    except (TypeError, ValueError):
        pass
    return f"{_num(a, digits)} → {_num(b, digits)}"


def period_title(snap: Dict[str, Any]) -> str:
    key = str(snap.get("period_key") or "")
    if snap.get("period_type") == "month" and len(key) >= 7:
        return f"{key[:4]}年{key[5:7]}月 股市复盘报告"
    if key.startswith("20") and "-W" in key:
        year, week = key.split("-W", 1)
        return f"{year}年第{int(week)}周 股市复盘报告"
    return f"{key} 股市复盘报告"


def render_period_markdown(snap: Dict[str, Any]) -> str:
    nxt = "下月" if snap.get("period_type") == "month" else "下周"
    lines: List[str] = [
        f"# {period_title(snap)}",
        "",
        f"区间 {snap.get('start_date') or '—'} 至 {snap.get('end_date') or '—'}，"
        f"日复盘 {snap.get('day_count') or 0} 天。",
        "",
    ]
    if snap.get("note"):
        lines.append(str(snap.get("note")))
        lines.append("")
    lines.append("## 大盘")
    lines.append("")
    vol = f"日均成交 {_num(snap.get('vol_avg'))} 万亿"
    if snap.get("prev_vol_avg") is not None:
        vol += f"，上一期日均 {_num(snap.get('prev_vol_avg'))} 万亿"
    lines.append(vol + "。")
    lines.append("")
    lines.append("| 指数 | 期初收盘 | 期末收盘 | 区间涨跌% |")
    lines.append("| --- | ---: | ---: | ---: |")
    for row in snap.get("indexes") or []:
        lines.append(
            f"| {row.get('name') or '—'} | {_num(row.get('start_close'))} | "
            f"{_num(row.get('end_close'))} | {_num(row.get('period_pct'))} |"
        )
    if not snap.get("indexes"):
        lines.append("| — | — | — | — |")
    lines.append("")
    lines.append("## 趋势路径")
    lines.append("")
    delta = snap.get("delta") or {}
    lines.append(f"- 高度：{_delta_line(delta.get('height') or {}, '板', 0)}")
    lines.append(f"- 连板：{_delta_line(delta.get('cb_count') or {}, '家', 0)}")
    lines.append(f"- 成交额：{_delta_line(delta.get('vol_trillion') or {}, '万亿')}")
    lines.append("")
    lines.append("| 日期 | 高度 | 连板 | 季节 | 成交(万亿) | 盘面 |")
    lines.append("| --- | ---: | ---: | --- | ---: | --- |")
    for row in snap.get("path") or []:
        lines.append(
            f"| {row.get('trade_date') or '—'} | {_num(row.get('height'), 0)} | "
            f"{_num(row.get('cb_count'), 0)} | {row.get('season') or '—'} | "
            f"{_num(row.get('vol_trillion'))} | {row.get('tape_label') or '—'} |"
        )
    lines.append("")
    lines.append("## 硬门槛达标天数")
    lines.append("")
    lines.append("| 门槛 | 标准 | 达标天数 |")
    lines.append("| --- | --- | ---: |")
    for row in snap.get("gates") or []:
        lines.append(
            f"| {row.get('name') or '—'} | {row.get('standard') or '—'} | "
            f"{row.get('passed_days') or 0}/{row.get('total_days') or 0} |"
        )
    lines.append("")
    lines.append("## 主线持续性")
    lines.append("")
    lines.append("| 概念 | 上榜天数 | 期末定性 | 梯队 | 持续 |")
    lines.append("| --- | ---: | --- | --- | --- |")
    for row in snap.get("mainlines") or []:
        lines.append(
            f"| {row.get('board_name') or '—'} | {int(row.get('hit_days') or 0)} | "
            f"{row.get('tier_label') or '—'} | {row.get('echelon') or '—'} | "
            f"{'是' if row.get('persistent') else '否'} |"
        )
    ind = snap.get("industry_confirm") or {}
    if ind.get("summary"):
        lines.append("")
        lines.append(f"期末行业赛道：{ind.get('summary')}")
    lines.append("")
    lines.append("## 情绪路径")
    lines.append("")
    seasons = snap.get("seasons") or []
    lines.append(
        f"路径：{' → '.join(seasons) if seasons else '—'}。切换 {snap.get('season_switches') or 0} 次，"
        f"期末 {snap.get('end_season') or '—'}。"
    )
    lines.append("")
    lines.append("## 双曲线")
    lines.append("")
    curve = snap.get("curve") or {}
    lines.append(f"- Lo：{_delta_line(curve.get('lo') or {})}")
    lines.append(f"- Hi：{_delta_line(curve.get('hi') or {})}")
    lines.append(f"- Sp：{_delta_line(curve.get('sp') or {})}")
    lines.append("")
    lines.extend(_picks_md(snap.get("picks") or {}, nxt))
    lines.append("## 观点与盘面分析")
    lines.append("")
    lines.append(snap.get("viewpoint_md") or "（待填写）")
    lines.append("")
    lines.append("## 操作建议")
    lines.append("")
    lines.append(snap.get("advice_md") or "（待填写）")
    lines.append("")
    lines.append(f"规则合成参考，非投资建议。报告区间：{snap.get('start_date') or '—'} 至 {snap.get('end_date') or '—'}。")
    lines.append("")
    return "\n".join(lines)


def _picks_md(picks: Dict[str, Any], nxt: str) -> List[str]:
    lines = [f"## {nxt}个股", "", picks.get("disclaimer") or "", ""]
    if picks.get("note"):
        lines.append(str(picks.get("note")))
        lines.append("")
    no_chase = picks.get("no_chase") or []
    if no_chase:
        lines.append("### 不追")
        lines.append("")
        lines.append("| 个股 | 连板 | 封单(亿) | 立场 | 区间涨跌% |")
        lines.append("| --- | ---: | ---: | --- | ---: |")
        for row in no_chase:
            lines.append(
                f"| {_name(row)} | {_num(row.get('board_count'), 0)} | {_num(row.get('seal_yi'))} | "
                f"{row.get('stance') or '—'} | {_num(row.get('period_pct'))} |"
            )
        lines.append("")
    track = picks.get("track") or []
    if track:
        lines.append("### 可跟踪")
        lines.append("")
        lines.append("| 个股 | 行业 | 立场 | 区间涨跌% | 形态 | 触发 |")
        lines.append("| --- | --- | --- | ---: | --- | --- |")
        for row in track:
            lines.append(
                f"| {_name(row)} | {_industry_cell(row)} | {row.get('stance') or '—'} | "
                f"{_num(row.get('period_pct'))} | {_pattern_zh(row.get('pattern'))} | {row.get('trigger') or '—'} |"
            )
        lines.append("")
    sideline = picks.get("sideline") or []
    if sideline:
        lines.append("### 支线只观察")
        lines.append("")
        lines.append("| 个股 | 行业 | 区间涨跌% | 立场 |")
        lines.append("| --- | --- | ---: | --- |")
        for row in sideline:
            lines.append(
                f"| {_name(row)} | {_industry_cell(row)} | {_num(row.get('period_pct'))} | {row.get('stance') or '只观察'} |"
            )
        lines.append("")
    avoid = picks.get("avoid") or []
    if avoid:
        lines.append("### 回避")
        lines.append("")
        lines.append("| 个股 | 原因 | 立场 |")
        lines.append("| --- | --- | --- |")
        for row in avoid:
            lines.append(f"| {_name(row)} | {row.get('reason') or '—'} | 回避 |")
        lines.append("")
    if not (no_chase or track or sideline or avoid) and not picks.get("note"):
        lines.append("无新增跟踪")
        lines.append("")
    return lines


def _industry_cell(row: Dict[str, Any]) -> str:
    return clean_industry_name(row.get("industry")) or "—"


def _name(row: Dict[str, Any]) -> str:
    name = row.get("name") or row.get("code") or "—"
    code = row.get("code") or ""
    return f"{name}({code})" if code else str(name)


def build_period_review_html(snap: Dict[str, Any]) -> str:
    font = register_cjk_font()
    title = period_title(snap)
    nxt = "下月" if snap.get("period_type") == "month" else "下周"
    picks = snap.get("picks") or {}
    idx_body = [
        [
            row.get("name"),
            _fmt(row.get("start_close")),
            _fmt(row.get("end_close")),
            _signed(row.get("period_pct")),
        ]
        for row in snap.get("indexes") or []
    ]
    path_body = [
        [
            row.get("trade_date"),
            _num(row.get("height"), 0),
            _num(row.get("cb_count"), 0),
            row.get("season") or "—",
            _fmt(row.get("vol_trillion")),
            row.get("tape_label") or "—",
        ]
        for row in snap.get("path") or []
    ]
    gate_body = [
        [
            row.get("name"),
            row.get("standard"),
            f"{row.get('passed_days') or 0}/{row.get('total_days') or 0}",
        ]
        for row in snap.get("gates") or []
    ]
    main_body = [
        [
            row.get("board_name"),
            int(row.get("hit_days") or 0),
            row.get("tier_label") or "—",
            "是" if row.get("persistent") else "否",
        ]
        for row in snap.get("mainlines") or []
    ]
    delta = snap.get("delta") or {}
    curve = snap.get("curve") or {}
    picks_html = _picks_html(picks, nxt)
    css = f"""
    @page {{ size: A4; margin: 12mm 11mm 14mm 11mm; }}
    body {{ font-family: {font}; font-size: 9.5pt; color: #1f2937; line-height: 1.45; }}
    h1 {{ font-size: 16pt; margin: 0 0 2pt; color: #111827; }}
    h2 {{ font-size: 12pt; margin: 12pt 0 4pt; padding: 0 0 2pt; border-bottom: 1.5pt solid #b91c1c; color: #111827; }}
    h3 {{ font-size: 10.5pt; margin: 8pt 0 3pt; color: #374151; }}
    p {{ margin: 3pt 0; }}
    .sub {{ font-size: 8.5pt; color: #6b7280; margin: 0 0 8pt; }}
    .lead {{ background-color: #f8fafc; border: 0.6pt solid #e5e7eb; padding: 6pt 8pt; }}
    .muted {{ color: #6b7280; font-size: 8pt; }}
    .up {{ color: #dc2626; }}
    .down {{ color: #15803d; }}
    table {{ width: 100%; border-collapse: collapse; margin: 3pt 0 8pt; }}
    th, td {{ border: 0.4pt solid #e5e7eb; padding: 3pt 4pt; text-align: left; vertical-align: middle; font-size: 8.5pt; }}
    th {{ background-color: #f3f4f6; color: #374151; font-size: 8pt; }}
    tr {{ page-break-inside: avoid; }}
    .footer {{ margin-top: 12pt; padding-top: 4pt; border-top: 0.4pt solid #e5e7eb; font-size: 8pt; color: #9ca3af; }}
    """
    seasons = " → ".join(snap.get("seasons") or []) or "—"
    viewpoint = _esc(snap.get("viewpoint_md") or "（待填写）").replace("\n", "<br/>")
    advice = _esc(snap.get("advice_md") or "（待填写）").replace("\n", "<br/>")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>{css}</style></head>
<body>
<h1>{_esc(title)}</h1>
<p class="sub">区间 {_esc(snap.get('start_date'))} 至 {_esc(snap.get('end_date'))} | 日复盘 {snap.get('day_count') or 0} 天 | 期末季节 {_esc(snap.get('end_season') or '—')}</p>
<p class="muted">{_esc(snap.get('note') or '')}</p>
<h2>观点与盘面分析</h2>
<div class="lead">{viewpoint}</div>
<h2>大盘</h2>
<p>日均成交 {_esc(_num(snap.get('vol_avg')))} 万亿，上一期日均 {_esc(_num(snap.get('prev_vol_avg')))} 万亿。</p>
{_table(["指数", "期初收盘", "期末收盘", "区间涨跌%"], idx_body, ["28%", "24%", "24%", "24%"])}
<h2>趋势路径</h2>
<p>高度 {_esc(_delta_line(delta.get('height') or {}, '板', 0))}；连板 {_esc(_delta_line(delta.get('cb_count') or {}, '家', 0))}。</p>
{_table(["日期", "高度", "连板", "季节", "成交(万亿)", "盘面"], path_body, ["18%", "12%", "12%", "14%", "22%", "22%"])}
<h2>硬门槛达标天数</h2>
{_table(["门槛", "标准", "达标天数"], gate_body, ["34%", "40%", "26%"])}
<h2>主线持续性</h2>
{_table(["概念", "上榜天数", "期末定性", "持续"], main_body, ["34%", "18%", "28%", "20%"])}
<h2>情绪路径</h2>
<p>{_esc(seasons)}。切换 {snap.get('season_switches') or 0} 次。</p>
<h2>双曲线</h2>
<p>Lo {_esc(_delta_line(curve.get('lo') or {}))}；Hi {_esc(_delta_line(curve.get('hi') or {}))}；Sp {_esc(_delta_line(curve.get('sp') or {}))}。</p>
{picks_html}
<h2>操作建议</h2>
<p>{advice}</p>
<div class="footer">规则合成参考，非投资建议。报告区间：{_esc(snap.get('start_date'))} 至 {_esc(snap.get('end_date'))}</div>
</body></html>"""


def _picks_html(picks: Dict[str, Any], nxt: str) -> str:
    parts = [f"<h2>{_esc(nxt)}个股</h2>", f"<p class='muted'>{_esc(picks.get('disclaimer') or '')}</p>"]
    if picks.get("note"):
        parts.append(f"<p>{_esc(picks.get('note'))}</p>")
    no_chase = picks.get("no_chase") or []
    if no_chase:
        body = [
            [
                f"{r.get('name') or ''} {r.get('code') or ''}",
                _num(r.get("board_count"), 0),
                _fmt(r.get("seal_yi")),
                r.get("stance") or "—",
                _signed(r.get("period_pct")),
            ]
            for r in no_chase
        ]
        parts.append("<h3>不追</h3>")
        parts.append(_table(["个股", "连板", "封单(亿)", "立场", "区间涨跌%"], body, ["28%", "12%", "16%", "22%", "22%"]))
    track = picks.get("track") or []
    if track:
        body = [
            [
                f"{r.get('name') or ''} {r.get('code') or ''}",
                _industry_cell(r),
                r.get("stance") or "—",
                _signed(r.get("period_pct")),
                _pattern_zh(r.get("pattern")),
                r.get("trigger") or "—",
            ]
            for r in track
        ]
        parts.append("<h3>可跟踪</h3>")
        parts.append(_table(["个股", "行业", "立场", "区间涨跌%", "形态", "触发"], body, ["18%", "14%", "12%", "14%", "14%", "28%"]))
    sideline = picks.get("sideline") or []
    if sideline:
        body = [
            [f"{r.get('name') or ''} {r.get('code') or ''}", _industry_cell(r), _signed(r.get("period_pct")), r.get("stance") or "只观察"]
            for r in sideline
        ]
        parts.append("<h3>支线只观察</h3>")
        parts.append(_table(["个股", "行业", "区间涨跌%", "立场"], body, ["28%", "28%", "22%", "22%"]))
    avoid = picks.get("avoid") or []
    if avoid:
        body = [[f"{r.get('name') or ''} {r.get('code') or ''}", r.get("reason") or "—", "回避"] for r in avoid]
        parts.append("<h3>回避</h3>")
        parts.append(_table(["个股", "原因", "立场"], body, ["32%", "48%", "20%"]))
    if not (no_chase or track or sideline or avoid) and not picks.get("note"):
        parts.append("<p>无新增跟踪</p>")
    return "".join(parts)


def build_period_review_pdf_bytes(snap: Dict[str, Any]) -> bytes:
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError("服务端 PDF 导出依赖未安装：请安装 xhtml2pdf") from e
    register_cjk_font()
    html = build_period_review_html(snap)
    output = io.BytesIO()
    status = pisa.CreatePDF(html, dest=output, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"xhtml2pdf 生成 PDF 失败（错误数 {status.err}）")
    pdf = output.getvalue()
    if not pdf.startswith(b"%PDF"):
        raise RuntimeError("生成的内容不是有效 PDF")
    return pdf
