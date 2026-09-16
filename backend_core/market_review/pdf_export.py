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


def _kv_rows(pairs: Sequence[Tuple[str, str]]) -> str:
    cells = []
    for k, v in pairs:
        if not v:
            continue
        cells.append(f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>")
    if not cells:
        return "<p class='muted'>暂无</p>"
    return f"<table class='kv'>{''.join(cells)}</table>"


def _table(headers: Sequence[str], body: Sequence[Sequence[Any]]) -> str:
    if not body:
        return "<p class='muted'>暂无</p>"
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    trs = []
    for row in body:
        trs.append("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"


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

    def delta_txt(key: str, unit: str = "") -> str:
        d = delta.get(key) or {}
        a, b = d.get("from"), d.get("to")
        if a is None and b is None:
            return "—"
        try:
            if a is not None and b is not None:
                diff = float(b) - float(a)
                sign = "+" if diff > 0 else ""
                return f"{_fmt(a)} → {_fmt(b)}（{sign}{_fmt(diff)}{unit}）"
        except (TypeError, ValueError):
            pass
        return f"{_fmt(a)} → {_fmt(b)}"

    gate_body = []
    for it in gates.get("items") or []:
        gate_body.append(
            [
                it.get("id"),
                it.get("name"),
                it.get("standard"),
                _fmt(it.get("value")),
                "达标" if it.get("passed") else "不达标",
            ]
        )

    main_body = []
    for r in mainline.get("rows") or []:
        main_body.append(
            [
                r.get("board_name") or r.get("board_code"),
                r.get("hits_10d"),
                r.get("tier_label"),
                r.get("today_status"),
                r.get("echelon"),
            ]
        )

    ind = mainline.get("industry_confirm") or {}
    ind_body = []
    for r in ind.get("rows") or []:
        ind_body.append(
            [
                r.get("board_name") or r.get("board_code"),
                r.get("reason_text") or "—",
                _fmt(r.get("change_percent")),
                _fmt(r.get("net_inflow"), 0),
            ]
        )

    signals = rules.get("signals") or []
    sig_html = (
        "<ul>" + "".join(f"<li>{_esc(s)}</li>" for s in signals) + "</ul>"
        if signals
        else "<p class='muted'>无</p>"
    )

    viewpoint = _esc(snapshot.get("viewpoint_md") or "").replace("\n", "<br/>")
    advice = _esc(snapshot.get("advice_md") or "").replace("\n", "<br/>")

    css = f"""
    @page {{ size: A4; margin: 14mm 12mm; }}
    body {{ font-family: {font}, Helvetica, sans-serif; font-size: 10pt; color: #111; line-height: 1.45; }}
    h1 {{ font-size: 16pt; margin: 0 0 8pt; }}
    h2 {{ font-size: 12pt; margin: 14pt 0 6pt; border-bottom: 1px solid #ccc; padding-bottom: 2pt; }}
    h3 {{ font-size: 11pt; margin: 10pt 0 4pt; }}
    p {{ margin: 4pt 0; }}
    .muted {{ color: #666; font-size: 9pt; }}
    table {{ width: 100%; border-collapse: collapse; margin: 4pt 0 8pt; font-size: 9pt; }}
    th, td {{ border: 1px solid #bbb; padding: 3pt 5pt; text-align: left; vertical-align: top; }}
    th {{ background: #f0f0f0; }}
    table.kv th {{ width: 28%; }}
    ul {{ margin: 4pt 0 4pt 16pt; padding: 0; }}
    .footer {{ margin-top: 16pt; font-size: 8pt; color: #666; }}
    """

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>{css}</style></head>
<body>
<h1>{_esc(trade_date)} 股市复盘报告</h1>
<p class="muted">口径 limit_source={_esc(snapshot.get('limit_source'))} · 季节 {_esc(snapshot.get('season'))} · 硬门槛 {(gates.get('rate') or '—')}</p>

<h2>观点与盘面分析</h2>
<p>{viewpoint or '（待填写）'}</p>

<h2>一、趋势解读</h2>
{_kv_rows([
    ("H(高度)", delta_txt("height", "板")),
    ("CB(连板)", delta_txt("cb_count", "家")),
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
{_table(["序号", "门槛", "标准", "今日", "结果"], gate_body)}

<h2>三、主线板块（近10日·同花顺概念）</h2>
<p class="muted">口径：概念定主线；行业仅作当日赛道确认。</p>
<p class="muted">{_esc(mainline.get("summary") or "")}</p>
{_table(["概念板块", "上榜", "定性", "今日", "梯队"], main_body)}
<h3>当日行业赛道确认</h3>
<p class="muted">{_esc(ind.get("summary") or "")}</p>
{_table(["行业板块", "上榜原因", "涨跌幅%", "净流入"], ind_body)}

<h2>四、情绪周期</h2>
{_kv_rows([
    ("判定", str(snapshot.get("season") or season.get("season") or "—")),
    ("连板", _fmt(season.get("cb"), 0)),
    ("高度", _fmt(season.get("height"), 0)),
    ("昨连板收益%", _fmt(season.get("prev_cb_return"))),
])}

<h2>五、双曲线 Lo / Hi / Spread</h2>
{_table(
    ["指标", "数值", "百分位", "备注"],
    [
        ["Lo", _fmt(snapshot.get("lo_value")), _fmt(snapshot.get("lo_percentile")), ""],
        ["Hi", _fmt(snapshot.get("hi_value")), _fmt(snapshot.get("hi_percentile")), ""],
        ["Sp", _fmt(snapshot.get("sp_value")), _fmt(snapshot.get("sp_percentile")),
         "变盘前夜" if rules.get("sp_eve") else ""],
    ],
)}
<p>四象限：{_esc(rules.get("quadrant") or "—")}</p>

<h2>六、操作建议</h2>
<p>{advice or '（待填写）'}</p>

<div class="footer">
规则合成参考，非投资建议。报告审核：Person · 报告日期：{_esc(trade_date)}
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
