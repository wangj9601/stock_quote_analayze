# -*- coding: utf-8 -*-
"""每日复盘 PDF：HTML + xhtml2pdf（CJK）。"""

from __future__ import annotations

import html
import io
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


def _esc(v: Any) -> str:
    if v is None:
        return ""
    return html.escape(str(v))


def _fmt_yi(v: Any) -> str:
    if v is None or v == "":
        return "—"
    try:
        return f"{float(v) / 1e8:.1f}"
    except (TypeError, ValueError):
        return "—"


def _yi_cell(row: Dict[str, Any]) -> str:
    if row.get("net_inflow_yi") is not None:
        return _fmt(row.get("net_inflow_yi"), 1)
    return _fmt_yi(row.get("net_inflow"))


def _fmt(v: Any, digits: int = 2) -> str:
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
        if digits == 0:
            return str(int(round(f)))
        return f"{f:.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def register_cjk_font() -> str:
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError:
        return "Helvetica"
    names = set(pdfmetrics.getRegisteredFontNames())
    if "STSong-Light" not in names:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        except Exception:
            logger.exception("注册 STSong-Light 失败")
            return "Helvetica"
    return "STSong-Light"


def _kv_rows(pairs: Sequence[Tuple[str, Any]]) -> str:
    cells = []
    for k, v in pairs:
        if v is None or v == "":
            continue
        cells.append(f"<tr><th>{_esc(k)}</th><td>{_cell_html(v)}</td></tr>")
    if not cells:
        return "<p class='muted'>暂无</p>"
    return f"<table class='kv'>{''.join(cells)}</table>"


def _stock_line(r: Dict[str, Any], *, with_trigger: bool = False) -> tuple:
    name = _esc(r.get("name") or r.get("code") or "—")
    code = _esc(r.get("code") or "")
    line = f"<b>{name}</b>"
    if code:
        line += f" <span class='code'>{code}</span>"
    if with_trigger:
        trigger = str(r.get("trigger") or "").strip()
        if trigger and trigger not in ("--", "—"):
            line += f"<br/><span class='muted'>{_esc(trigger)}</span>"
    return ("html", line)


def _cell_html(c: Any) -> str:
    if isinstance(c, tuple) and len(c) == 2 and c[0] == "html":
        return str(c[1])
    return _esc(c)


def _signed(v: Any, digits: int = 2) -> tuple:
    text = _fmt(v, digits)
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ("html", _esc(text))
    if n > 0:
        return ("html", f"<span class='up'>{_esc(text)}</span>")
    if n < 0:
        return ("html", f"<span class='down'>{_esc(text)}</span>")
    return ("html", _esc(text))


def _plain_mark(text: Any) -> str:
    s = str(text or "")
    for ch in ("🟩", "❌", "★", "✅", "⚠", "️"):
        s = s.replace(ch, "")
    return " ".join(s.split())


def _pattern_zh(name: Any) -> str:
    raw = str(name or "").strip()
    if not raw or raw in ("--", "无明确形态"):
        return raw or "—"
    extra = {
        "head_shoulders_bottom": "头肩底",
        "head_shoulders_top": "头肩顶",
        "double_bottom": "双底",
        "double_top": "双顶",
        "symmetrical_triangle": "对称三角",
        "ascending_triangle": "上升三角",
        "descending_triangle": "下降三角",
        "falling_wedge": "下降楔形",
        "rising_wedge": "上升楔形",
    }
    if raw in extra:
        return extra[raw]
    try:
        from backend_core.analysis.chart_patterns.engine import _pattern_label_zh

        zh = _pattern_label_zh(raw)
        if zh and zh != raw:
            return zh
    except Exception:
        pass
    return raw


def _gate_value(it: Dict[str, Any]) -> str:
    val = it.get("value")
    gid = it.get("id")
    if gid in (4, 5) or isinstance(val, bool):
        return "是" if val else "否"
    if gid in (2, 3):
        return _fmt(val, 0)
    return _fmt(val)


def _table(
    headers: Sequence[str],
    body: Sequence[Sequence[Any]],
    widths: Optional[Sequence[str]] = None,
) -> str:
    if not body:
        return "<p class='muted'>暂无</p>"
    cols = ""
    if widths and len(widths) == len(headers):
        cols = "<colgroup>" + "".join(f'<col width="{w}"/>' for w in widths) + "</colgroup>"
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    trs = []
    for row in body:
        trs.append("<tr>" + "".join(f"<td>{_cell_html(c)}</td>" for c in row) + "</tr>")
    return (
        f"<table>{cols}<thead><tr>{th}</tr></thead>"
        f"<tbody>{''.join(trs)}</tbody></table>"
    )


def build_daily_review_html(snapshot: Dict[str, Any]) -> str:
    font = register_cjk_font()
    trade_date = str(snapshot.get("trade_date") or "")[:10]
    gates = snapshot.get("hard_gates") or {}
    rules = snapshot.get("rules_json") or {}
    mainline = snapshot.get("mainline_json") or {}
    season = snapshot.get("season_detail") or {}
    delta = rules.get("delta") if isinstance(rules, dict) else {}
    if not isinstance(delta, dict):
        delta = {}

    def delta_txt(key: str, unit: str = "", digits: int = 2):
        d = delta.get(key) or {}
        a, b = d.get("from"), d.get("to")
        if a is None and b is None:
            return "—"
        try:
            if a is not None and b is not None:
                diff = float(b) - float(a)
                sign = "+" if diff > 0 else ""
                cls = "up" if diff > 0 else ("down" if diff < 0 else "")
                body = f"{_esc(_fmt(a, digits))} → {_esc(_fmt(b, digits))}"
                diff_txt = f"{sign}{_fmt(diff, digits)}{unit}"
                if cls:
                    body += f"（<span class='{cls}'>{_esc(diff_txt)}</span>）"
                else:
                    body += f"（{_esc(diff_txt)}）"
                return ("html", body)
        except (TypeError, ValueError):
            pass
        return f"{_fmt(a, digits)} → {_fmt(b, digits)}"

    gate_body = []
    for it in gates.get("items") or []:
        mark = "达标" if it.get("passed") else "不达标"
        gate_body.append(
            [
                it.get("id"),
                it.get("name"),
                it.get("standard"),
                _gate_value(it),
                ("html", f"<span class='{'ok' if it.get('passed') else 'bad'}'>{mark}</span>"),
            ]
        )

    main_body = []
    for r in mainline.get("rows") or []:
        main_body.append(
            [
                r.get("board_name") or r.get("board_code"),
                r.get("hits_10d"),
                _plain_mark(r.get("tier_label")),
                _plain_mark(r.get("today_status")),
                _plain_mark(r.get("echelon")),
            ]
        )

    ind = mainline.get("industry_confirm") or {}
    ind_body = []
    for r in ind.get("rows") or []:
        ind_body.append(
            [
                r.get("board_name") or r.get("board_code"),
                r.get("reason_text") or "—",
                _signed(r.get("change_percent")),
                _signed(r.get("net_inflow_yi"), 1) if r.get("net_inflow_yi") is not None else _yi_cell(r),
            ]
        )

    signals = rules.get("signals") or []
    sig_html = (
        "".join(f"<p>- {_esc(s)}</p>" for s in signals)
        if signals
        else "<p class='muted'>无</p>"
    )

    viewpoint = _esc(snapshot.get("viewpoint_md") or "").replace("\n", "<br/>")
    advice = _esc(snapshot.get("advice_md") or "").replace("\n", "<br/>")

    env = rules.get("market_env") if isinstance(rules, dict) else None
    if not isinstance(env, dict):
        env = {}
    breadth = env.get("breadth") or {}
    tape = (rules.get("tape") or {}) if isinstance(rules, dict) else {}
    env_bits = []
    if tape.get("label"):
        env_bits.append(f"盘面状态：{tape.get('label')}")
    if env.get("vol_delta_yi") is not None:
        env_bits.append(f"量能较昨日 { _fmt(env.get('vol_delta_yi'), 0) } 亿")
    if breadth:
        env_bits.append(
            f"上涨 {breadth.get('up_count', '—')} / 下跌 {breadth.get('down_count', '—')} / "
            f"跌停 {breadth.get('limit_down_count', '—')}"
        )
    idx_body = []
    for idx in env.get("indexes") or []:
        idx_body.append(
            [
                idx.get("name") or idx.get("ts_code"),
                _fmt(idx.get("close")),
                _signed(idx.get("pct_chg")),
                _fmt(idx.get("gap_to_high20"), 0),
                idx.get("note") or "",
            ]
        )
    env_html = ""
    if env_bits or idx_body:
        env_html = "<h2>大盘环境</h2>"
        if env_bits:
            env_html += "<p>" + _esc("；".join(env_bits)) + "</p>"
        env_html += _table(
            ["指数", "收盘", "涨跌幅%", "距20日高点", "备注"],
            idx_body,
            ["22%", "16%", "14%", "18%", "30%"],
        )

    sector = mainline.get("sector") or {}
    sector_html = ""
    if isinstance(sector, dict) and sector.get("main"):
        main = sector.get("main") or {}
        sector_html = (
            f"<p>当日主线：{_esc(main.get('board_name'))}，"
            f"净流入 {_esc(_yi_cell(main))} 亿</p>"
        )
    sentiment = (rules.get("sentiment") or {}) if isinstance(rules, dict) else {}
    fact_html = ""
    facts = sentiment.get("facts") or []
    watch = sentiment.get("watch") or []
    if facts or watch:
        fact_html = "<h3>当日事实与次日观察</h3>"
        fact_html += "".join(f"<p>- {_esc(x)}</p>" for x in list(facts) + list(watch))

    picks = (rules.get("picks") or {}) if isinstance(rules, dict) else {}
    picks_html = ""
    if isinstance(picks, dict) and picks:
        parts = ["<h2>明日个股</h2>", f"<p class='muted'>{_esc(picks.get('disclaimer') or '')}</p>"]
        if picks.get("note"):
            parts.append(f"<p>{_esc(picks.get('note'))}</p>")
        no_chase = picks.get("no_chase") or []
        if no_chase:
            body = []
            for r in no_chase:
                brk = r.get("break_count")
                seal_note = "炸板" if brk else "封死"
                if r.get("limit_band"):
                    seal_note = f"{seal_note} {r.get('limit_band')}"
                body.append(
                    [
                        _stock_line(r, with_trigger=True),
                        r.get("board_count") if r.get("board_count") is not None else "—",
                        _fmt(r.get("seal_yi")),
                        seal_note,
                        r.get("stance") or "—",
                    ]
                )
            parts.append("<h3>不追</h3>")
            parts.append(_table(["个股与次日", "连板", "封单(亿)", "封板", "立场"], body, ["40%", "10%", "14%", "16%", "20%"]))
        track = picks.get("track") or []
        if track:
            body = []
            for r in track:
                stance = r.get("stance") or "—"
                if r.get("brief_stance"):
                    stance = f"{stance}（简报{r.get('brief_stance')}）"
                sup = _fmt(r.get("p_sup"))
                res = _fmt(r.get("p_res"))
                indicator = " / ".join(
                    x
                    for x in (
                        str(r.get("macd") or "").strip(),
                        f"RSI {_fmt(r.get('rsi'), 0)}" if r.get("rsi") is not None else "",
                        str(r.get("kdj") or "").strip(),
                        str(r.get("trend") or "").strip(),
                    )
                    if x and x not in ("--", "—")
                )
                body.append(
                    [
                        _stock_line(r, with_trigger=True),
                        "、".join(r.get("strategies") or []) or "—",
                        stance,
                        f"{sup} / {res}",
                        _pattern_zh(r.get("pattern")),
                        indicator or "—",
                    ]
                )
            parts.append("<h3>可跟踪</h3>")
            parts.append(
                _table(
                    ["个股与触发", "策略", "立场", "支撑/压力", "形态", "指标"],
                    body,
                    ["28%", "14%", "12%", "16%", "12%", "18%"],
                )
            )
        sideline = picks.get("sideline") or []
        if sideline:
            body = [
                [
                    _stock_line(r, with_trigger=False),
                    r.get("industry") or "—",
                    _signed(r.get("change_percent")),
                    r.get("stance") or "只观察",
                ]
                for r in sideline
            ]
            parts.append("<h3>支线只观察</h3>")
            parts.append(_table(["个股", "行业", "涨幅%", "立场"], body, ["32%", "28%", "16%", "24%"]))
        avoid = picks.get("avoid") or []
        if avoid:
            body = [
                [ _stock_line(r, with_trigger=False), r.get("reason") or "—", "回避"]
                for r in avoid
            ]
            parts.append("<h3>回避</h3>")
            parts.append(_table(["个股", "原因", "立场"], body, ["32%", "48%", "20%"]))
        if not (no_chase or track or sideline or avoid) and not picks.get("note"):
            parts.append("<p>无新增跟踪</p>")
        picks_html = "".join(parts)

    zones = (rules.get("curve_zones") or {}) if isinstance(rules, dict) else {}
    pct_note = zones.get("percentile_note") or snapshot.get("percentile_note") or ""

    def _pct_cell(key: str) -> str:
        if pct_note == "样本不足":
            return "样本不足"
        val = snapshot.get(key)
        if val is None:
            return "样本不足" if (rules.get("percentile_sample") or 0) < 20 else "—"
        return _fmt(val)

    lo_zone = zones.get("lo") or "阈值未校准"
    hi_zone = zones.get("hi") or "阈值未校准"
    sp_zone = zones.get("sp") or ("变盘前夜" if rules.get("sp_eve") else "阈值未校准")
    zone_summary = zones.get("summary") or "阈值未校准"

    css = f"""
    @page {{ size: A4; margin: 12mm 11mm 14mm 11mm; }}
    body {{ font-family: {font}; font-size: 9.5pt; color: #1f2937; line-height: 1.45; }}
    h1 {{ font-size: 16pt; margin: 0 0 2pt; color: #111827; }}
    h2 {{ font-size: 12pt; margin: 12pt 0 4pt; padding: 0 0 2pt; border-bottom: 1.5pt solid #b91c1c; color: #111827; }}
    h3 {{ font-size: 10.5pt; margin: 8pt 0 3pt; color: #374151; }}
    p {{ margin: 3pt 0; }}
    .sub {{ font-size: 8.5pt; color: #6b7280; margin: 0 0 8pt; }}
    .lead {{ background-color: #f8fafc; border: 0.6pt solid #e5e7eb; padding: 6pt 8pt; margin: 0 0 6pt; }}
    .muted {{ color: #6b7280; font-size: 8pt; }}
    .code {{ color: #6b7280; font-size: 8pt; }}
    .up {{ color: #dc2626; }}
    .down {{ color: #15803d; }}
    .ok {{ color: #15803d; }}
    .bad {{ color: #dc2626; }}
    table {{ width: 100%; border-collapse: collapse; margin: 3pt 0 8pt; }}
    th, td {{ border: 0.4pt solid #e5e7eb; padding: 3pt 4pt; text-align: left; vertical-align: middle; font-size: 8.5pt; }}
    th {{ background-color: #f3f4f6; color: #374151; font-size: 8pt; }}
    table.kv th {{ width: 22%; background-color: #fafafa; font-weight: normal; color: #4b5563; }}
    tr {{ page-break-inside: avoid; }}
    ul {{ margin: 2pt 0 6pt 14pt; padding: 0; }}
    li {{ margin: 1pt 0; }}
    .footer {{ margin-top: 12pt; padding-top: 4pt; border-top: 0.4pt solid #e5e7eb; font-size: 8pt; color: #9ca3af; }}
    """

    src = str(snapshot.get("limit_source") or "")
    src_label = {"em_zt_pool": "东财涨停池", "hist_proxy": "日终涨幅代理", "zt_pool_em": "东财涨停池"}.get(src, src or "—")
    date_parts = str(trade_date).split("-")
    if len(date_parts) == 3 and all(p.isdigit() for p in date_parts):
        title_date = f"{date_parts[0]}年{date_parts[1]}月{date_parts[2]}日"
    else:
        title_date = str(trade_date)
    tape_label = tape.get("label") or "—"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>{css}</style></head>
<body>
<h1>{_esc(title_date)} 股市复盘报告</h1>
<p class="sub">季节 {_esc(snapshot.get('season'))} | 盘面 {_esc(tape_label)} | 硬门槛 {_esc(gates.get('rate') or '—')} | 涨停口径 {_esc(src_label)}</p>

<h2>观点与盘面分析</h2>
<div class="lead">{viewpoint or '（待填写）'}</div>
{env_html}

<h2>一、趋势解读</h2>
{_kv_rows([
    ("H(高度)", delta_txt("height", "板", 0)),
    ("CB(连板)", delta_txt("cb_count", "家", 0)),
    ("昨连板收益", delta_txt("prev_cb_return", "%")),
    ("Lo", delta_txt("lo_value")),
    ("Hi", delta_txt("hi_value")),
    ("Vol(万亿)", delta_txt("vol_trillion", "万亿")),
    ("Sp", delta_txt("sp_value")),
])}
<p><b>结论：</b>{_esc(rules.get("summary") or "—")}</p>
<h3>信号</h3>
{sig_html}

<h2>二、五项硬门槛（{ _esc(gates.get("rate") or "") }）</h2>
{_table(["序号", "门槛", "标准", "今日", "结果"], gate_body, ["8%", "28%", "24%", "18%", "22%"])}

<h2>三、主线板块（近10日，同花顺概念）</h2>
<p class="muted">口径：概念定主线；行业仅作当日赛道确认。</p>
<p class="muted">{_esc(mainline.get("summary") or "")}</p>
{sector_html}
{_table(["概念板块", "上榜", "定性", "今日", "梯队"], main_body, ["24%", "12%", "20%", "22%", "22%"])}
<h3>当日行业赛道确认</h3>
<p class="muted">{_esc(ind.get("summary") or "")}</p>
{_table(["行业板块", "上榜原因", "涨跌幅%", "净流入(亿)"], ind_body, ["24%", "40%", "16%", "20%"])}

<h2>四、情绪周期</h2>
{_kv_rows([
    ("判定", str(snapshot.get("season") or season.get("season") or "—")),
    ("连板", _fmt(season.get("cb"), 0)),
    ("高度", _fmt(season.get("height"), 0)),
    ("昨连板收益%", _fmt(season.get("prev_cb_return"))),
])}
{fact_html}
{picks_html}

<h2>五、双曲线 Lo / Hi / Spread</h2>
{_table(
    ["指标", "数值", "百分位", "区间定位"],
    [
        ["Lo", _fmt(snapshot.get("lo_value")), _pct_cell("lo_percentile"), lo_zone],
        ["Hi", _fmt(snapshot.get("hi_value")), _pct_cell("hi_percentile"), hi_zone],
        ["Sp", _fmt(snapshot.get("sp_value")), _pct_cell("sp_percentile"), sp_zone],
    ],
    ["16%", "22%", "22%", "40%"],
)}
<p>区间定位：{_esc(zone_summary)}</p>

<h2>六、操作建议</h2>
<p>{advice or '（待填写）'}</p>

<div class="footer">
规则合成参考，非投资建议。报告日期：{_esc(trade_date)}
</div>
</body></html>"""


def build_daily_review_pdf_bytes(snapshot: Dict[str, Any]) -> bytes:
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError(
            "服务端 PDF 导出依赖未安装：请安装 xhtml2pdf（pip install xhtml2pdf）"
        ) from e

    register_cjk_font()
    html_content = build_daily_review_html(snapshot)
    output = io.BytesIO()
    status = pisa.CreatePDF(html_content, dest=output, encoding="utf-8")
    if status.err:
        raise RuntimeError(f"xhtml2pdf 生成 PDF 失败（错误数 {status.err}）")
    pdf_bytes = output.getvalue()
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError("生成的内容不是有效 PDF")
    return pdf_bytes


def export_pdf_file(
    snapshot: Dict[str, Any],
    out_dir: Optional[Path] = None,
    pdf_bytes: Optional[bytes] = None,
) -> Path:
    root = Path(__file__).resolve().parents[2]
    target_dir = out_dir or (root / "exported_docs")
    target_dir.mkdir(parents=True, exist_ok=True)
    trade_date = str(snapshot.get("trade_date") or "unknown")[:10]
    parts = trade_date.split("-")
    if len(parts) == 3:
        title = f"{parts[0]}年{parts[1]}月{parts[2]}日 股市复盘报告.pdf"
    else:
        title = f"{trade_date} 股市复盘报告.pdf"
    path = target_dir / title
    path.write_bytes(pdf_bytes or build_daily_review_pdf_bytes(snapshot))
    return path
