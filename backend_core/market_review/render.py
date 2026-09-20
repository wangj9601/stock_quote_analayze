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


def _delta_txt(from_v: Any, to_v: Any, unit: str = "", digits: int = 2) -> str:
    if from_v is None or to_v is None:
        return f"{_fmt(from_v, digits)} → {_fmt(to_v, digits)}"
    try:
        d = float(to_v) - float(from_v)
        sign = "+" if d > 0 else ""
        return f"{_fmt(from_v, digits)} → {_fmt(to_v, digits)}（{sign}{_fmt(d, digits)}{unit}）"
    except (TypeError, ValueError):
        return f"{from_v} → {to_v}"


def _gate_mark(ok: bool) -> str:
    return "✅ 达标" if ok else "❌ 不达标"


def _fmt_yi(v: Any) -> str:
    if v is None or v == "":
        return "--"
    try:
        return f"{float(v) / 1e8:.1f}"
    except (TypeError, ValueError):
        return "--"


def _yi_cell(row: Dict[str, Any]) -> str:
    if row.get("net_inflow_yi") is not None:
        return _fmt(row.get("net_inflow_yi"), 1)
    return _fmt_yi(row.get("net_inflow"))


def _breadth_cell(row: Dict[str, Any]) -> str:
    up, down = row.get("up_count"), row.get("down_count")
    if up is None and down is None:
        return "--"
    return f"{up if up is not None else '--'}/{down if down is not None else '--'}"


def _name_cell(row: Dict[str, Any]) -> str:
    name = row.get("name") or row.get("code") or "--"
    code = row.get("code") or ""
    return f"{name}({code})" if code else str(name)


def _picks_markdown(picks: Dict[str, Any]) -> List[str]:
    lines = [
        "# **明日个股**",
        "",
        picks.get("disclaimer") or "规则合成参考，非投资建议。",
        "",
    ]
    note = picks.get("note") or ""
    if note:
        lines.append(note)
        lines.append("")
    no_chase = picks.get("no_chase") or []
    track = picks.get("track") or []
    sideline = picks.get("sideline") or []
    avoid = picks.get("avoid") or []
    if no_chase:
        lines.extend(
            [
                "## **不追**",
                "",
                "| 个股 | 连板 | 封单(亿) | 炸板 | 涨跌停 | 立场 | 次日 |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for row in no_chase:
            lines.append(
                f"| {_name_cell(row)} | {row.get('board_count') if row.get('board_count') is not None else '--'} | "
                f"{_fmt(row.get('seal_yi'))} | {row.get('break_count') if row.get('break_count') is not None else '--'} | "
                f"{row.get('limit_band') or '--'} | {row.get('stance') or '--'} | {row.get('trigger') or '--'} |"
            )
        lines.append("")
    if track:
        lines.extend(
            [
                "## **可跟踪**",
                "",
                "| 个股 | 策略 | 立场 | 支撑 | 压力 | 明日触发 | 形态 | MACD | RSI | KDJ | 趋势 |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for row in track:
            strategies = "、".join(row.get("strategies") or []) or "--"
            brief = row.get("brief_stance") or ""
            stance = row.get("stance") or "--"
            if brief:
                stance = f"{stance}（简报{brief}）"
            lines.append(
                f"| {_name_cell(row)} | {strategies} | {stance} | {_fmt(row.get('p_sup'))} | "
                f"{_fmt(row.get('p_res'))} | {row.get('trigger') or '--'} | {row.get('pattern') or '--'} | "
                f"{row.get('macd') or '--'} | {_fmt(row.get('rsi'))} | {row.get('kdj') or '--'} | {row.get('trend') or '--'} |"
            )
        lines.append("")
    if sideline:
        lines.extend(
            [
                "## **支线只观察**",
                "",
                "| 个股 | 行业 | 涨幅% | 立场 |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for row in sideline:
            lines.append(
                f"| {_name_cell(row)} | {row.get('industry') or '--'} | {_fmt(row.get('change_percent'))} | {row.get('stance') or '只观察'} |"
            )
        lines.append("")
    if avoid:
        lines.extend(
            [
                "## **回避**",
                "",
                "| 个股 | 原因 | 立场 |",
                "| :--- | :--- | :--- |",
            ]
        )
        for row in avoid:
            lines.append(f"| {_name_cell(row)} | {row.get('reason') or '--'} | 回避 |")
        lines.append("")
    if not (no_chase or track or sideline or avoid) and not note:
        lines.append("无新增跟踪")
        lines.append("")
    return lines


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
    ]

    env = snapshot.get("market_env") or rules.get("market_env") or {}
    if not isinstance(env, dict):
        env = {}
    indexes = env.get("indexes") or []
    breadth = env.get("breadth") or {}
    if indexes or breadth or env.get("vol_delta_yi") is not None:
        lines.extend(["# **一、大盘环境**", ""])
        if env.get("vol_trillion") is not None or env.get("vol_delta_yi") is not None:
            vol_line = f"成交额 {_fmt(env.get('vol_trillion') if env.get('vol_trillion') is not None else snapshot.get('vol_trillion'))} 万亿"
            if env.get("vol_delta_yi") is not None:
                vol_line += f"，较昨日 {_fmt(env.get('vol_delta_yi'), 0)} 亿"
            if env.get("above_2t"):
                vol_line += "，站上 2 万亿"
            lines.append(vol_line)
            lines.append("")
        if breadth:
            zt = snapshot.get("limit_up_count")
            lines.append(
                f"上涨 {breadth.get('up_count', '--')} 家，下跌 {breadth.get('down_count', '--')} 家，"
                f"平盘 {breadth.get('flat_count', '--')} 家；涨停 {zt if zt is not None else '--'}，"
                f"跌停 {breadth.get('limit_down_count', '--')}。"
            )
            lines.append("")
        if indexes:
            lines.extend(
                [
                    "| 指数 | 收盘 | 涨跌幅% | 成交额(亿) | 距20日高点 | 备注 |",
                    "| :--- | :--- | :--- | :--- | :--- | :--- |",
                ]
            )
            for idx in indexes:
                lines.append(
                    f"| {idx.get('name') or idx.get('ts_code')} | {_fmt(idx.get('close'))} | "
                    f"{_fmt(idx.get('pct_chg'))} | {_fmt(idx.get('amount_yi'), 0)} | "
                    f"{_fmt(idx.get('gap_to_high20'), 0)} | {idx.get('note') or '--'} |"
                )
            lines.append("")

    lines.extend(
        [
            "# **二、趋势解读**",
        "",
        "## **核心指标对比**",
        "",
        f"* **H(高度)**: {_delta_txt((delta.get('height') or {}).get('from'), (delta.get('height') or {}).get('to'), '板', 0)}",
        f"* **CB(连板)**: {_delta_txt((delta.get('cb_count') or {}).get('from'), (delta.get('cb_count') or {}).get('to'), '家', 0)}",
        f"* **昨连板收益**: {_delta_txt((delta.get('prev_cb_return') or {}).get('from'), (delta.get('prev_cb_return') or {}).get('to'), '%')}",
        f"* **Lo**: {_delta_txt((delta.get('lo_value') or {}).get('from'), (delta.get('lo_value') or {}).get('to'))}",
        f"* **Hi**: {_delta_txt((delta.get('hi_value') or {}).get('from'), (delta.get('hi_value') or {}).get('to'))}",
        f"* **Vol**: {_delta_txt((delta.get('vol_trillion') or {}).get('from'), (delta.get('vol_trillion') or {}).get('to'), '万亿')}",
        f"* **Sp**: {_delta_txt((delta.get('sp_value') or {}).get('from'), (delta.get('sp_value') or {}).get('to'))}",
        "",
        f"**结论**：{rules.get('summary') or '--'}",
        "",
        ]
    )

    sigs = rules.get("signals") or []
    if sigs:
        lines.append("## **信号**")
        lines.append("")
        for i, s in enumerate(sigs, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    lines.extend(
        [
            "# **三、五项硬门槛达标检查**",
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
            "# **四、主线板块统计**",
            "",
            "> 口径：同花顺**概念**定主线（近10日上榜 ≥3 = 核心主线）；**行业**仅作当日赛道确认，不计入主线次数。",
            "",
        ]
    )
    sector = mainline.get("sector") or {}
    if isinstance(sector, dict) and (
        sector.get("leaders")
        or sector.get("laggards")
        or sector.get("main")
        or sector.get("capital_in")
        or sector.get("ladder")
        or sector.get("flow_top")
    ):
        main = sector.get("main") or {}
        if main.get("board_name"):
            yi = _yi_cell(main)
            lines.append(
                f"**当日主线**：{main.get('board_name')}，涨跌幅 {_fmt(main.get('change_percent'))}%，"
                f"净流入 {yi} 亿。"
            )
        else:
            lines.append("**当日主线**：不明确。")
        sides = [s.get("board_name") for s in (sector.get("sidelines") or []) if s and s.get("board_name")]
        if sides:
            lines.append(f"**支线**：{'、'.join(sides)}。")
        lines.append("")

        def _chg_table(title: str, rows: List[Dict[str, Any]]) -> None:
            if not rows:
                return
            lines.append(f"## **{title}**")
            lines.append("")
            lines.append("| 板块 | 涨跌幅% | 净流入(亿) | 上涨/下跌 |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for row in rows:
                lines.append(
                    f"| {row.get('board_name') or row.get('board_code')} | "
                    f"{_fmt(row.get('change_percent'))} | {_yi_cell(row)} | {_breadth_cell(row)} |"
                )
            lines.append("")

        _chg_table("领涨行业", sector.get("leaders") or [])
        _chg_table("领跌行业", sector.get("laggards") or [])

        rot = sector.get("rotation") or {}
        dropped = rot.get("dropped") or []
        new_in = rot.get("new_inflow") or []
        if dropped or new_in:
            lines.append("## **轮动**")
            lines.append("")
            if dropped:
                lines.append(f"昨日上榜今日跌出：{'、'.join(dropped)}。")
            if new_in:
                bits = []
                for row in new_in:
                    bits.append(f"{row.get('board_name')}（{_yi_cell(row)}亿）")
                lines.append(f"今日新进且净流入居前：{'、'.join(bits)}。")
            lines.append("")

        def _flow_table(title: str, rows: List[Dict[str, Any]]) -> None:
            if not rows:
                return
            lines.append(f"## **{title}**")
            lines.append("")
            lines.append("| 板块 | 净流入(亿) |")
            lines.append("| :--- | :--- |")
            for row in rows:
                lines.append(
                    f"| {row.get('board_name') or row.get('board_code')} | {_yi_cell(row)} |"
                )
            lines.append("")

        _flow_table("行业净流入前五", sector.get("capital_in") or [])
        _flow_table("行业净流出前三", sector.get("capital_out") or [])

        ladder = sector.get("ladder") or None
        if ladder:
            hs = sector.get("height_stock") or {}
            height_bit = ""
            if hs.get("name"):
                height_bit = f"最高板：{_name_cell(hs)} {hs.get('board_count')} 板。"
            lines.append(
                f"**连板梯队**：2 板 {ladder.get('b2', 0)}，3 板 {ladder.get('b3', 0)}，"
                f"4 板及以上 {ladder.get('b4plus', 0)}。{height_bit}"
            )
            lines.append("")
        seals = sector.get("seal_leaders") or []
        if seals:
            lines.append("## **主线涨停（按封单）**")
            lines.append("")
            lines.append("| 个股 | 涨幅% | 封单(亿) | 连板 |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for row in seals:
                seal = row.get("seal_yi")
                seal_txt = _fmt(seal, 2) if seal is not None else "--"
                lines.append(
                    f"| {_name_cell(row)} | {_fmt(row.get('change_percent'))} | "
                    f"{seal_txt} | {row.get('board_count')} |"
                )
            lines.append("")
        flows = sector.get("flow_top") or []
        if flows:
            lines.append("## **个股主力净流入前五**")
            lines.append("")
            lines.append("| 个股 | 净流入(亿) |")
            lines.append("| :--- | :--- |")
            for row in flows:
                lines.append(f"| {_name_cell(row)} | {_fmt(row.get('net_inflow_yi'), 2)} |")
            lines.append("")
        main_flows = sector.get("main_flow_top") or []
        if main_flows:
            lines.append("## **主线内吸金前三**")
            lines.append("")
            lines.append("| 个股 | 净流入(亿) |")
            lines.append("| :--- | :--- |")
            for row in main_flows:
                lines.append(f"| {_name_cell(row)} | {_fmt(row.get('net_inflow_yi'), 2)} |")
            lines.append("")

    lines.extend(
        [
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
            "| 行业板块 | 上榜原因 | 涨跌幅% | 净流入(亿) |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )
    for row in ind.get("rows") or []:
        lines.append(
            f"| {row.get('board_name') or row.get('board_code')} | "
            f"{row.get('reason_text') or '—'} | "
            f"{_fmt(row.get('change_percent'))} | {_yi_cell(row)} |"
        )
    if not (ind.get("rows") or []):
        lines.append("| -- | -- | -- | -- |")
    lines.append("")
    lines.append(f"**赛道确认**：{ind.get('summary') or '--'}")
    lines.append("")

    season_name = snapshot.get("season") or season.get("season") or "--"
    sentiment = rules.get("sentiment") or {}
    facts = sentiment.get("facts") or []
    watch = sentiment.get("watch") or []
    lines.extend(
        [
            "# **五、情绪周期判定**",
            "",
            f"**判定：{season_name}期**",
            "",
            f"- 连板：{season.get('cb')}",
            f"- 高度：{season.get('height')}",
            f"- 昨连板收益：{_fmt(season.get('prev_cb_return'))}%",
            "",
        ]
    )
    if facts:
        lines.append("**当日事实**：")
        lines.append("")
        for i, fact in enumerate(facts, 1):
            lines.append(f"{i}. {fact}")
        lines.append("")
    if watch:
        lines.append("**次日观察**：")
        lines.append("")
        for i, item in enumerate(watch, 1):
            lines.append(f"{i}. {item}")
        lines.append("")

    picks = rules.get("picks") if isinstance(rules.get("picks"), dict) else None
    if picks:
        lines.extend(_picks_markdown(picks))

    zones = rules.get("curve_zones") or {}
    note = snapshot.get("percentile_note") or zones.get("percentile_note") or ""

    def _pct_txt(key: str) -> str:
        if note == "样本不足":
            return "样本不足"
        val = snapshot.get(key)
        if val is None:
            return "样本不足" if (rules.get("percentile_sample") or 0) < 20 else "--"
        return f"{_fmt(val)}%"

    lines.extend(
        [
            "# **六、双曲线分析 (Lo/Hi Spread)**",
            "",
            "| 指标 | 数值 | 百分位 | 区间定位 |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Lo** | {_fmt(snapshot.get('lo_value'))} | {_pct_txt('lo_percentile')} | {zones.get('lo') or '阈值未校准'} |",
            f"| **Hi** | {_fmt(snapshot.get('hi_value'))} | {_pct_txt('hi_percentile')} | {zones.get('hi') or '阈值未校准'} |",
            f"| **Spread** | {_fmt(snapshot.get('sp_value'))} | {_pct_txt('sp_percentile')} | "
            f"{zones.get('sp') or ('变盘前夜区' if rules.get('sp_eve') else '阈值未校准')} |",
            "",
            f"**区间定位**：{zones.get('summary') or '阈值未校准'}",
            "",
            "# **七、操作建议**",
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
