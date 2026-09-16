# -*- coding: utf-8 -*-
"""每日复盘 Markdown 渲染。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


def _fmt(v: Any, digits: int = 2) -> str:
    if v is None:
        return "--"
    try:
        f = float(v)
        if f == int(f) and digits == 0:
            return str(int(f))
        return f"{f:.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def _delta_txt(from_v: Any, to_v: Any, unit: str = "") -> str:
    if from_v is None or to_v is None:
        return f"{_fmt(from_v)} → {_fmt(to_v)}"
    try:
        d = float(to_v) - float(from_v)
        sign = "+" if d > 0 else ""
        return f"{_fmt(from_v)} → {_fmt(to_v)}（{sign}{_fmt(d)}{unit}）"
    except (TypeError, ValueError):
        return f"{from_v} → {to_v}"


def _gate_mark(ok: bool) -> str:
    return "✅ 达标" if ok else "❌ 不达标"


def render_markdown(snapshot: Dict[str, Any]) -> str:
    trade_date = snapshot.get("trade_date") or ""
    viewpoint = snapshot.get("viewpoint_md") or ""
    advice = snapshot.get("advice_md") or ""
    gates = snapshot.get("hard_gates") or {}
    season = snapshot.get("season_detail") or {}
    rules = snapshot.get("rules_json") or {}
    mainline = snapshot.get("mainline_json") or {}
    limit_source = snapshot.get("limit_source") or "hist_proxy"
    delta = rules.get("delta") or {}

    lines: List[str] = [
        f"# **{trade_date} 股市复盘报告**",
        "",
        "# **观点与盘面分析**",
        "",
        viewpoint.strip() or "（待填写）",
        "",
        "# **一、趋势解读**",
        "",
        "## **核心指标对比**",
        "",
        f"* **H(高度)**: {_delta_txt((delta.get('height') or {}).get('from'), (delta.get('height') or {}).get('to'), '板')}",
        f"* **CB(连板)**: {_delta_txt((delta.get('cb_count') or {}).get('from'), (delta.get('cb_count') or {}).get('to'), '家')}",
        f"* **昨连板收益**: {_delta_txt((delta.get('prev_cb_return') or {}).get('from'), (delta.get('prev_cb_return') or {}).get('to'), '%')}",
        f"* **Lo**: {_delta_txt((delta.get('lo_value') or {}).get('from'), (delta.get('lo_value') or {}).get('to'))}",
        f"* **Hi**: {_delta_txt((delta.get('hi_value') or {}).get('from'), (delta.get('hi_value') or {}).get('to'))}",
        f"* **Vol**: {_delta_txt((delta.get('vol_trillion') or {}).get('from'), (delta.get('vol_trillion') or {}).get('to'), '万亿')}",
        f"* **Sp**: {_delta_txt((delta.get('sp_value') or {}).get('from'), (delta.get('sp_value') or {}).get('to'))}",
        "",
        f"**结论**：{rules.get('summary') or '--'}",
        "",
    ]

    sigs = rules.get("signals") or []
    if sigs:
        lines.append("## **信号**")
        lines.append("")
        for i, s in enumerate(sigs, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    lines.extend(
        [
            "# **二、五项硬门槛达标检查**",
            "",
            "| 序号 | 硬门槛 | 标准 | 今日数值 | 结果 |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for it in gates.get("items") or []:
        lines.append(
            f"| {it.get('id')} | {it.get('name')} | {it.get('standard')} | "
            f"{_fmt(it.get('value'))} | {_gate_mark(bool(it.get('passed')))} |"
        )
    lines.append("")
    lines.append(
        f"**达标率：{gates.get('rate') or '--'}**"
    )
    lines.append("")

    lines.extend(
        [
            "# **三、主线板块统计**",
            "",
            "> 口径：同花顺**概念**定主线（近10日上榜 ≥3 = 核心主线）；**行业**仅作当日赛道确认，不计入主线次数。",
            "",
            "## **近10日概念主线筛选**",
            "",
            "| 板块 | 近10日上榜 | 定性 | 今日状态 | 梯队评估 |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for row in mainline.get("rows") or []:
        lines.append(
            f"| {row.get('board_name') or row.get('board_code')} | "
            f"{row.get('hits_10d')}次 | {row.get('tier_label')} | "
            f"{row.get('today_status')} | {row.get('echelon')} |"
        )
    if not (mainline.get("rows") or []):
        lines.append("| -- | -- | -- | -- | -- |")
    lines.append("")
    lines.append(f"**主线格局**：{mainline.get('summary') or '--'}")
    lines.append("")

    ind = mainline.get("industry_confirm") or {}
    lines.extend(
        [
            "## **当日行业赛道确认**",
            "",
            "| 行业板块 | 上榜原因 | 涨跌幅% | 净流入 |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )
    for row in ind.get("rows") or []:
        lines.append(
            f"| {row.get('board_name') or row.get('board_code')} | "
            f"{row.get('reason_text') or '—'} | "
            f"{_fmt(row.get('change_percent'))} | {_fmt(row.get('net_inflow'), 0)} |"
        )
    if not (ind.get("rows") or []):
        lines.append("| -- | -- | -- | -- |")
    lines.append("")
    lines.append(f"**赛道确认**：{ind.get('summary') or '--'}")
    lines.append("")

    season_name = snapshot.get("season") or season.get("season") or "--"
    lines.extend(
        [
            "# **四、情绪周期判定**",
            "",
            f"**判定：{season_name}期**",
            "",
            f"- 连板：{season.get('cb')}",
            f"- 高度：{season.get('height')}",
            f"- 昨连板收益：{_fmt(season.get('prev_cb_return'))}%",
            "",
            "# **五、双曲线分析 (Lo/Hi Spread)**",
            "",
            "| 指标 | 数值 | 百分位 | 区间定位 |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Lo** | {_fmt(snapshot.get('lo_value'))} | {_fmt(snapshot.get('lo_percentile'))}% | -- |",
            f"| **Hi** | {_fmt(snapshot.get('hi_value'))} | {_fmt(snapshot.get('hi_percentile'))}% | -- |",
            f"| **Spread** | {_fmt(snapshot.get('sp_value'))} | {_fmt(snapshot.get('sp_percentile'))}% | "
            f"{'变盘前夜区' if rules.get('sp_eve') else '--'} |",
            "",
            f"**四象限定位**：{rules.get('quadrant') or '--'}",
            "",
            "# **六、操作建议**",
            "",
            advice.strip() or "（待填写）",
            "",
            "---",
            f"涨停口径：`{limit_source}`（em_zt_pool=东财涨停池；hist_proxy=日终涨幅代理）",
            "",
            "报告审核：Person  ",
            f"报告日期：{trade_date}",
            "",
        ]
    )
    return "\n".join(lines)


def export_markdown_file(snapshot: Dict[str, Any], out_dir: Optional[Path] = None) -> Path:
    root = Path(__file__).resolve().parents[2]
    target_dir = out_dir or (root / "exported_docs")
    target_dir.mkdir(parents=True, exist_ok=True)
    trade_date = str(snapshot.get("trade_date") or "unknown")
    # 2026-09-15 → 2026年09月15日
    parts = trade_date.split("-")
    if len(parts) == 3:
        title = f"{parts[0]}年{parts[1]}月{parts[2]}日 股市复盘报告.md"
    else:
        title = f"{trade_date} 股市复盘报告.md"
    path = target_dir / title
    path.write_text(render_markdown(snapshot), encoding="utf-8")
    return path
