# -*- coding: utf-8 -*-
"""周报 / 月报：汇总已有每日复盘，不逐日补算。"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.market_review.compute import concept_matches_focus
from backend_core.market_review.period_picks import (
    apply_period_triggers,
    assemble_period_picks,
)
from backend_core.market_review.period_render import clean_industry_name, render_period_markdown
from backend_core.market_review.picks import (
    _load_zt,
    _norm_code,
    _roles_for_board,
    enrich_picks,
)

logger = logging.getLogger(__name__)


def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _d(v: Any) -> str:
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


def _as_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip():
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def parse_anchor(raw: Optional[str]) -> date:
    if not raw:
        return date.today()
    s = str(raw).strip().replace("/", "-")
    if len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return date.fromisoformat(s[:10])


def period_bounds(kind: str, anchor: date) -> Tuple[date, date, str]:
    """自然周（周一至周日）或自然月。周键用 ISO 周。"""
    if kind == "month":
        start = anchor.replace(day=1)
        if start.month == 12:
            end = date(start.year, 12, 31)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return start, end, f"{start.year}-{start.month:02d}"
    monday = anchor - timedelta(days=anchor.weekday())
    sunday = monday + timedelta(days=6)
    iso = monday.isocalendar()
    return monday, sunday, f"{iso.year}-W{iso.week:02d}"


def previous_bounds(kind: str, start: date) -> Tuple[date, date, str]:
    if kind == "month":
        prev_end = start - timedelta(days=1)
        return period_bounds("month", prev_end)
    return period_bounds("week", start - timedelta(days=1))


def weekday_gaps(start: date, end: date, have: Sequence[str]) -> List[str]:
    """区间内没有日复盘的周一至周五。休市日也会列在这里。"""
    known = {_d(x) for x in have}
    out: List[str] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5 and cur.isoformat() not in known:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def reconstruct_period_pct(first_close: Any, first_pct: Any, last_close: Any) -> Optional[float]:
    """用首日收盘和首日涨跌幅还原期初价，再对末日收盘算区间涨跌（百分数）。"""
    fc = _f(first_close)
    lc = _f(last_close)
    if fc is None or lc is None or fc == 0:
        return None
    fp = _f(first_pct)
    if fp is None:
        return (lc / fc - 1.0) * 100.0
    denom = 1.0 + fp / 100.0
    if denom == 0:
        return None
    prior = fc / denom
    if prior == 0:
        return None
    return (lc / prior - 1.0) * 100.0


def _on_list(row: Dict[str, Any]) -> bool:
    if row.get("today_hit") is True:
        return True
    status = str(row.get("today_status") or "")
    return "上榜" in status and "跌落" not in status


def select_persistent(boards: Sequence[Dict[str, Any]], n_days: int, kind: str) -> List[Dict[str, Any]]:
    """周至少 2 天；复盘日不足 3 天时用末日仍在榜的主线。月至少 5 天或不少于 30%。"""
    if n_days <= 0:
        return []
    horizon = "month" if kind == "month" else "week"
    if horizon == "week" and n_days < 3:
        return [dict(b) for b in boards if b.get("last_day_hit")]
    out = []
    for b in boards:
        hits = int(b.get("hit_days") or 0)
        if horizon == "week":
            if hits >= 2:
                out.append(dict(b))
        elif hits >= 5 or hits / float(n_days) >= 0.3:
            out.append(dict(b))
    return out


def _avg(values: Sequence[Any]) -> Optional[float]:
    nums = [float(v) for v in values if _f(v) is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def aggregate_daily_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    kind: str,
    start: date,
    end: date,
    period_key: str,
    prev_rows: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """只读已规范化的日快照，汇总区间正文。不含个股名单。"""
    ordered = sorted(rows, key=lambda r: _d(r.get("trade_date")))
    days = [_d(r.get("trade_date")) for r in ordered if _d(r.get("trade_date"))]
    first = ordered[0] if ordered else {}
    last = ordered[-1] if ordered else {}
    prev_ordered = sorted(prev_rows or [], key=lambda r: _d(r.get("trade_date")))

    indexes = _index_period(ordered)
    vol_vals = [r.get("vol_trillion") for r in ordered]
    prev_vol_vals = [r.get("vol_trillion") for r in prev_ordered]
    path = []
    for r in ordered:
        rules = _as_dict(r.get("rules_json"))
        tape = rules.get("tape") or {}
        path.append(
            {
                "trade_date": _d(r.get("trade_date")),
                "height": r.get("height"),
                "cb_count": r.get("cb_count"),
                "season": r.get("season"),
                "vol_trillion": r.get("vol_trillion"),
                "tape_label": tape.get("label") or "",
            }
        )
    seasons = [str(r.get("season")) for r in ordered if r.get("season")]
    switches = sum(1 for a, b in zip(seasons, seasons[1:]) if a != b)
    boards = _mainline_counts(ordered)
    persistent = select_persistent(boards, len(ordered), kind)
    persistent_codes = {str(b.get("board_code") or "") for b in persistent}
    for b in boards:
        b["persistent"] = str(b.get("board_code") or "") in persistent_codes

    last_main = _as_dict(last.get("mainline_json"))
    last_rules = _as_dict(last.get("rules_json"))
    gates = _gate_days(ordered)
    delta = {
        "height": _pair(first.get("height"), last.get("height")),
        "cb_count": _pair(first.get("cb_count"), last.get("cb_count")),
        "vol_trillion": _pair(first.get("vol_trillion"), last.get("vol_trillion")),
        "lo_value": _pair(first.get("lo_value"), last.get("lo_value")),
        "hi_value": _pair(first.get("hi_value"), last.get("hi_value")),
        "sp_value": _pair(first.get("sp_value"), last.get("sp_value")),
    }
    curve = {
        "lo": {
            **_pair(first.get("lo_value"), last.get("lo_value")),
            "end_percentile": last.get("lo_percentile"),
        },
        "hi": {
            **_pair(first.get("hi_value"), last.get("hi_value")),
            "end_percentile": last.get("hi_percentile"),
        },
        "sp": {
            **_pair(first.get("sp_value"), last.get("sp_value")),
            "end_percentile": last.get("sp_percentile"),
        },
    }
    gaps = weekday_gaps(start, end, days)
    note = ""
    if not ordered:
        note = "该区间没有每日复盘，请先完成日复盘。"
    elif gaps:
        note = "以下周一至周五没有日复盘（含可能休市）：" + "、".join(gaps)

    return {
        "period_type": "month" if kind == "month" else "week",
        "period_key": period_key,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "trade_days": days,
        "day_count": len(days),
        "missing_weekdays": gaps,
        "note": note,
        "indexes": indexes,
        "vol_avg": None if _avg(vol_vals) is None else round(_avg(vol_vals), 2),
        "prev_vol_avg": None if _avg(prev_vol_vals) is None else round(_avg(prev_vol_vals), 2),
        "path": path,
        "delta": delta,
        "gates": gates,
        "mainlines": boards,
        "persistent_mainlines": persistent,
        "industry_confirm": last_main.get("industry_confirm") or {},
        "seasons": seasons,
        "season_switches": switches,
        "end_season": last.get("season") or "",
        "curve": curve,
        "end_tape": (last_rules.get("tape") or {}),
        "end_gates": _as_dict(last.get("hard_gates")),
        "end_sector": (last_main.get("sector") or {}),
    }


def _pair(a: Any, b: Any) -> Dict[str, Any]:
    return {"from": a, "to": b}


def _index_period(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_name: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        env = (_as_dict(row.get("rules_json")).get("market_env") or {})
        for idx in env.get("indexes") or []:
            name = str(idx.get("name") or idx.get("ts_code") or "").strip()
            if not name:
                continue
            slot = by_name.setdefault(name, {"name": name, "first": None, "last": None})
            if slot["first"] is None:
                slot["first"] = idx
            slot["last"] = idx
    out = []
    for slot in by_name.values():
        first, last = slot["first"] or {}, slot["last"] or {}
        pct = reconstruct_period_pct(first.get("close"), first.get("pct_chg"), last.get("close"))
        out.append(
            {
                "name": slot["name"],
                "start_close": first.get("close"),
                "end_close": last.get("close"),
                "period_pct": None if pct is None else round(pct, 2),
            }
        )
    return out


def _mainline_counts(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    acc: Dict[str, Dict[str, Any]] = {}
    last_day = _d(rows[-1].get("trade_date")) if rows else ""
    for row in rows:
        day = _d(row.get("trade_date"))
        main = _as_dict(row.get("mainline_json"))
        for item in main.get("rows") or []:
            code = str(item.get("board_code") or "").strip()
            if not code:
                continue
            slot = acc.setdefault(
                code,
                {
                    "board_code": code,
                    "board_name": item.get("board_name") or code,
                    "hit_days": 0,
                    "days": set(),
                    "last_day_hit": False,
                    "tier_label": "",
                    "echelon": "",
                },
            )
            if item.get("board_name"):
                slot["board_name"] = item.get("board_name")
            if day == last_day:
                slot["tier_label"] = item.get("tier_label") or slot["tier_label"]
                slot["echelon"] = item.get("echelon") or slot["echelon"]
            if _on_list(item) and day not in slot["days"]:
                slot["days"].add(day)
                slot["hit_days"] += 1
                if day == last_day:
                    slot["last_day_hit"] = True
    out = []
    for slot in acc.values():
        slot = dict(slot)
        slot.pop("days", None)
        out.append(slot)
    out.sort(key=lambda r: (-int(r.get("hit_days") or 0), str(r.get("board_name") or "")))
    return out


def _gate_days(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    acc: Dict[Any, Dict[str, Any]] = {}
    total_days = 0
    for row in rows:
        gates = _as_dict(row.get("hard_gates"))
        items = gates.get("items") or []
        if not items:
            continue
        total_days += 1
        for it in items:
            gid = it.get("id")
            slot = acc.setdefault(
                gid,
                {
                    "id": gid,
                    "name": it.get("name") or "",
                    "standard": it.get("standard") or "",
                    "passed_days": 0,
                    "total_days": 0,
                },
            )
            slot["name"] = it.get("name") or slot["name"]
            slot["standard"] = it.get("standard") or slot["standard"]
            slot["total_days"] = total_days
            if it.get("passed"):
                slot["passed_days"] += 1
    for slot in acc.values():
        slot["total_days"] = total_days
    return [acc[k] for k in sorted(acc, key=lambda x: (x is None, str(x)))]


def draft_period_text(snap: Dict[str, Any]) -> Tuple[str, str]:
    kind = "本月" if snap.get("period_type") == "month" else "本周"
    nxt = "下月" if snap.get("period_type") == "month" else "下周"
    parts = [f"{kind}复盘区间 {snap.get('start_date')} 至 {snap.get('end_date')}，已有日复盘 {snap.get('day_count') or 0} 天。"]
    vols = []
    if snap.get("vol_avg") is not None:
        vols.append(f"日均成交 {snap.get('vol_avg')} 万亿")
    if snap.get("prev_vol_avg") is not None:
        vols.append(f"上一期日均 {snap.get('prev_vol_avg')} 万亿")
    if vols:
        parts.append("，".join(vols) + "。")
    sh = next((x for x in (snap.get("indexes") or []) if "上证" in str(x.get("name"))), None)
    if sh and sh.get("period_pct") is not None:
        parts.append(f"上证指数区间涨跌 {sh.get('period_pct')}%。")
    if snap.get("seasons"):
        parts.append(
            f"情绪路径 {' → '.join(snap.get('seasons') or [])}，切换 {snap.get('season_switches') or 0} 次，期末 {snap.get('end_season') or '—'}。"
        )
    names = [str(b.get("board_name")) for b in (snap.get("persistent_mainlines") or [])[:3] if b.get("board_name")]
    if names:
        parts.append("持续主线：" + "、".join(names) + "。")
    else:
        parts.append("区间内没有达到持续天数的概念主线。")
    viewpoint = "".join(parts)

    picks = snap.get("picks") or {}
    if picks.get("mode") == "retreat":
        advice = f"期末缩量或没有主线，{nxt}只做回避，不新开跟踪。规则合成参考，非投资建议。"
    elif picks.get("mode") == "empty":
        advice = f"主线成分不足，{nxt}不新开名单。规则合成参考，非投资建议。"
    else:
        advice = f"{nxt}不追高开，回踩再看结构是否守住。规则合成参考，非投资建议。"
    if snap.get("note"):
        advice = snap["note"] + advice
    return viewpoint, advice


def _load_rows(db: Session, start: date, end: date) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT trade_date, vol_trillion, cb_count, height, lo_value, hi_value, sp_value,
                   lo_percentile, hi_percentile, sp_percentile, season,
                   hard_gates, rules_json, mainline_json
            FROM market_daily_review
            WHERE trade_date >= :s AND trade_date <= :e
            ORDER BY trade_date
            """
        ),
        {"s": start.isoformat(), "e": end.isoformat()},
    ).mappings().all()
    out = []
    for row in rows:
        item = dict(row)
        item["trade_date"] = _d(item.get("trade_date"))
        for k in ("hard_gates", "rules_json", "mainline_json"):
            item[k] = _as_dict(item.get(k))
        out.append(item)
    return out


def _concept_members(db: Session, board_codes: Sequence[str]) -> Dict[str, set]:
    clean = [str(c).strip() for c in board_codes if str(c or "").strip()]
    if not clean:
        return {}
    try:
        rows = db.execute(
            text(
                """
                SELECT board_code, stock_code
                FROM concept_board_constituents
                WHERE board_code = ANY(:codes)
                """
            ),
            {"codes": clean},
        ).fetchall()
    except Exception:
        logger.exception("概念成分查询失败")
        db.rollback()
        return {}
    out: Dict[str, set] = {}
    for board, stock in rows:
        code = _norm_code(stock)
        if not code:
            continue
        out.setdefault(str(board), set()).add(code)
    return out


def _load_industries(db: Session, codes: Sequence[str]) -> Dict[str, str]:
    """所属行业以同花顺行业板块为准，不用 stock_basic_info.industry。"""
    clean = [c for c in {_norm_code(x) for x in codes} if c]
    if not clean:
        return {}
    try:
        from backend_core.recommend.env import map_stocks_to_ths_industry

        mapped = map_stocks_to_ths_industry(db, clean)
    except Exception:
        logger.exception("同花顺行业查询失败")
        db.rollback()
        return {}
    out: Dict[str, str] = {}
    for code, info in (mapped or {}).items():
        if not isinstance(info, dict):
            continue
        if str(info.get("board_code_source") or "") != "tonghuashun":
            continue
        name = clean_industry_name(info.get("industry") or info.get("board_name"))
        key = _norm_code(code)
        if key and name:
            out[key] = name
    return out


def _load_range_stats(db: Session, start: str, end: str, codes: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    clean = [c for c in {_norm_code(x) for x in codes} if c]
    if not clean:
        return {}
    try:
        rows = db.execute(
            text(
                """
                SELECT code, name, high, low, close, change_percent, date
                FROM historical_quotes
                WHERE date >= :s AND date <= :e AND code = ANY(:codes)
                """
            ),
            {"s": start, "e": end, "codes": clean},
        ).fetchall()
    except Exception:
        logger.exception("区间行情查询失败")
        db.rollback()
        return {}
    bucket: Dict[str, List[tuple]] = {}
    for code, name, high, low, close, chg, dt in rows:
        key = _norm_code(code)
        bucket.setdefault(key, []).append((_d(dt), name, _f(high), _f(low), _f(close), _f(chg)))
    out: Dict[str, Dict[str, Any]] = {}
    for code, bars in bucket.items():
        bars.sort(key=lambda x: x[0])
        first = bars[0]
        last = bars[-1]
        highs = [b[2] for b in bars if b[2] is not None]
        lows = [b[3] for b in bars if b[3] is not None]
        period_high = max(highs) if highs else None
        period_low = min(lows) if lows else None
        mid = None
        if period_high is not None and period_low is not None:
            mid = (period_high + period_low) / 2.0
        pct = reconstruct_period_pct(first[4], first[5], last[4])
        out[code] = {
            "name": last[1] or first[1] or code,
            "period_pct": None if pct is None else round(pct, 2),
            "last_close": last[4],
            "last_change": last[5],
            "period_high": period_high,
            "period_low": period_low,
            "mid": mid,
        }
    return out


def _daily_track_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        picks = (_as_dict(row.get("rules_json")).get("picks") or {})
        for item in picks.get("track") or []:
            code = _norm_code(item.get("code"))
            if not code:
                continue
            counts[code] = counts.get(code, 0) + 1
    return counts


def _faded_names(rows: Sequence[Dict[str, Any]], stats: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    half = max(1, len(rows) // 2)
    early = rows[:half]
    seen = set()
    out = []
    for row in early:
        picks = (_as_dict(row.get("rules_json")).get("picks") or {})
        for item in picks.get("no_chase") or []:
            code = _norm_code(item.get("code"))
            if not code or code in seen:
                continue
            st = stats.get(code) or {}
            pct = _f(st.get("period_pct"))
            last_chg = _f(st.get("last_change"))
            if (pct is not None and pct < 0) or (last_chg is not None and last_chg < 0):
                seen.add(code)
                out.append(
                    {
                        "code": code,
                        "name": item.get("name") or st.get("name") or code,
                        "reason": "由强转弱",
                    }
                )
    return out


def _last_avoid(last: Dict[str, Any]) -> List[Dict[str, Any]]:
    picks = (_as_dict(last.get("rules_json")).get("picks") or {})
    out = []
    for item in picks.get("avoid") or []:
        code = _norm_code(item.get("code"))
        if not code:
            continue
        out.append(
            {
                "code": code,
                "name": item.get("name") or code,
                "reason": item.get("reason") or "回避",
                "industry": item.get("industry") or "",
            }
        )
    return out


def _sideline_candidates(
    db: Session,
    last: Dict[str, Any],
    persistent: Sequence[Dict[str, Any]],
    stats: Dict[str, Dict[str, Any]],
    blocked: set,
) -> List[Dict[str, Any]]:
    sector = (_as_dict(last.get("mainline_json")).get("sector") or {})
    focus = [str(b.get("board_name") or "") for b in persistent]
    boards = []
    for row in sector.get("sidelines") or []:
        if _f(row.get("net_inflow")) is None or float(row["net_inflow"]) <= 0:
            continue
        if concept_matches_focus(row.get("board_name"), focus):
            continue
        boards.append(row)
    boards.sort(key=lambda r: -float(r.get("net_inflow") or 0))
    found: List[Dict[str, Any]] = []
    end = _d(last.get("trade_date"))
    for board in boards[:3]:
        code = str(board.get("board_code") or "").strip()
        if not code or not end:
            continue
        try:
            rows = db.execute(
                text(
                    """
                    SELECT h.code, h.name, h.change_percent
                    FROM industry_board_constituents c
                    JOIN historical_quotes h ON h.code = c.stock_code AND h.date = :d
                    WHERE c.board_code = :bc AND h.change_percent > 0
                    ORDER BY h.change_percent DESC
                    LIMIT 30
                    """
                ),
                {"d": end, "bc": code},
            ).fetchall()
        except Exception:
            logger.exception("支线成分查询失败")
            db.rollback()
            continue
        for stock, name, chg in rows:
            key = _norm_code(stock)
            if not key or key in blocked:
                continue
            st = stats.get(key) or {}
            found.append(
                {
                    "code": key,
                    "name": name or st.get("name") or key,
                    "industry": board.get("board_name") or "",
                    "change_percent": _f(chg),
                    "period_pct": st.get("period_pct"),
                }
            )
    return found


def build_period_picks(db: Session, rows: Sequence[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, Any]:
    kind = summary.get("period_type") or "week"
    persistent = summary.get("persistent_mainlines") or []
    if not rows or not persistent:
        return assemble_period_picks(
            kind=kind,
            constituents={},
            stats={},
            zt_rows=[],
            roles={},
            daily_track_counts={},
            season=summary.get("end_season"),
            gates_passed=int((summary.get("end_gates") or {}).get("passed") or 0),
            gates_total=int((summary.get("end_gates") or {}).get("total") or 0),
            tape_label=(summary.get("end_tape") or {}).get("label"),
            tape_volume=(summary.get("end_tape") or {}).get("volume"),
            has_main=bool(persistent),
            sideline_rows=[],
            faded=[],
            last_avoid=[],
        )
    hit_by_code = {str(b.get("board_code")): int(b.get("hit_days") or 0) for b in persistent}
    members = _concept_members(db, list(hit_by_code))
    ordered_boards = sorted(persistent, key=lambda b: -int(b.get("hit_days") or 0))
    constituents: Dict[str, Dict[str, Any]] = {}
    for board in ordered_boards:
        bcode = str(board.get("board_code") or "")
        for stock in members.get(bcode) or set():
            slot = constituents.setdefault(
                stock,
                {"name": stock, "industry": "", "overlap_days": 0, "concept": ""},
            )
            hits = hit_by_code.get(bcode, 0)
            if hits >= int(slot.get("overlap_days") or 0):
                slot["overlap_days"] = hits
                slot["concept"] = board.get("board_name") or bcode
    industries = _load_industries(db, list(constituents))
    for code, meta in constituents.items():
        meta["industry"] = industries.get(code) or ""

    start = summary.get("start_date") or ""
    end = summary.get("end_date") or ""
    stats = _load_range_stats(db, start, end, list(constituents))
    for code, st in stats.items():
        if code in constituents and st.get("name"):
            constituents[code]["name"] = st["name"]

    last = rows[-1]
    end_day = _d(last.get("trade_date"))
    zt_rows = _load_zt(db, end_day) if end_day else []
    sector = summary.get("end_sector") or {}
    main = sector.get("main") or {}
    roles = _roles_for_board(db, str(main.get("board_code") or "")) if main.get("board_code") else {}
    gates = summary.get("end_gates") or {}
    tape = summary.get("end_tape") or {}
    picks = assemble_period_picks(
        kind=kind,
        constituents=constituents,
        stats=stats,
        zt_rows=zt_rows,
        roles=roles,
        daily_track_counts=_daily_track_counts(rows),
        season=summary.get("end_season"),
        gates_passed=int(gates.get("passed") or 0),
        gates_total=int(gates.get("total") or 0),
        tape_label=tape.get("label"),
        tape_volume=tape.get("volume"),
        has_main=True,
        sideline_rows=[],
        faded=_faded_names(rows, stats),
        last_avoid=_last_avoid(last),
    )
    if picks.get("mode") == "plan":
        side_codes = []
        # 先用末日涨幅挑候选，区间涨跌再补
        preview = _sideline_candidates(db, last, persistent, stats, set())
        side_codes = [r["code"] for r in preview]
        extra = _load_range_stats(db, start, end, side_codes)
        for row in preview:
            st = extra.get(row["code"]) or {}
            if st.get("period_pct") is not None:
                row["period_pct"] = st["period_pct"]
            if st.get("name"):
                row["name"] = st["name"]
        picks = assemble_period_picks(
            kind=kind,
            constituents=constituents,
            stats=stats,
            zt_rows=zt_rows,
            roles=roles,
            daily_track_counts=_daily_track_counts(rows),
            season=summary.get("end_season"),
            gates_passed=int(gates.get("passed") or 0),
            gates_total=int(gates.get("total") or 0),
            tape_label=tape.get("label"),
            tape_volume=tape.get("volume"),
            has_main=True,
            sideline_rows=preview,
            faded=_faded_names(rows, stats),
            last_avoid=_last_avoid(last),
        )
        try:
            picks = enrich_picks(db, end_day, picks)
        except Exception:
            logger.exception("周期名单指标补全失败")
            db.rollback()
        picks = apply_period_triggers(picks, kind)
    return picks


def build_period_snapshot(
    db: Session,
    kind: str,
    anchor: str,
    *,
    keep_overrides: bool = True,
) -> Dict[str, Any]:
    horizon = "month" if str(kind) == "month" else "week"
    day = parse_anchor(anchor)
    start, end, key = period_bounds(horizon, day)
    prev_start, prev_end, _prev_key = previous_bounds(horizon, start)
    rows = _load_rows(db, start, end)
    prev_rows = _load_rows(db, prev_start, prev_end)
    summary = aggregate_daily_rows(
        rows,
        kind=horizon,
        start=start,
        end=end,
        period_key=key,
        prev_rows=prev_rows,
    )
    summary["anchor_date"] = day.isoformat()
    try:
        summary["picks"] = build_period_picks(db, rows, summary)
    except Exception:
        logger.exception("周期个股名单失败")
        db.rollback()
        summary["picks"] = {
            "disclaimer": "规则合成参考，非投资建议。",
            "note": "名单生成失败",
            "mode": "empty",
            "no_chase": [],
            "track": [],
            "sideline": [],
            "avoid": [],
        }
    viewpoint, advice = draft_period_text(summary)
    existing = db.execute(
        text(
            """
            SELECT viewpoint_md, advice_md, viewpoint_override, advice_override
            FROM market_period_review
            WHERE period_type = :t AND period_key = :k
            """
        ),
        {"t": horizon, "k": key},
    ).mappings().first()
    vp_override = bool(existing and existing.get("viewpoint_override"))
    ad_override = bool(existing and existing.get("advice_override"))
    if keep_overrides and vp_override and existing.get("viewpoint_md"):
        viewpoint = existing["viewpoint_md"]
    if keep_overrides and ad_override and existing.get("advice_md"):
        advice = existing["advice_md"]
    summary["viewpoint_md"] = viewpoint
    summary["advice_md"] = advice
    summary["viewpoint_override"] = vp_override
    summary["advice_override"] = ad_override
    _save_period(db, summary)
    summary["markdown"] = render_period_markdown(summary)
    return summary


def _save_period(db: Session, snap: Dict[str, Any]) -> None:
    payload = dict(snap)
    payload.pop("markdown", None)
    db.execute(
        text(
            """
            INSERT INTO market_period_review (
                period_type, period_key, start_date, end_date, snapshot_json,
                viewpoint_md, advice_md, viewpoint_override, advice_override,
                computed_at, updated_at
            ) VALUES (
                :period_type, :period_key, :start_date, :end_date, CAST(:snapshot_json AS jsonb),
                :viewpoint_md, :advice_md, :viewpoint_override, :advice_override,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (period_type, period_key) DO UPDATE SET
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                snapshot_json = EXCLUDED.snapshot_json,
                viewpoint_md = EXCLUDED.viewpoint_md,
                advice_md = EXCLUDED.advice_md,
                viewpoint_override = EXCLUDED.viewpoint_override,
                advice_override = EXCLUDED.advice_override,
                computed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """
        ),
        {
            "period_type": snap.get("period_type"),
            "period_key": snap.get("period_key"),
            "start_date": snap.get("start_date"),
            "end_date": snap.get("end_date"),
            "snapshot_json": json.dumps(payload, ensure_ascii=False, default=str),
            "viewpoint_md": snap.get("viewpoint_md") or "",
            "advice_md": snap.get("advice_md") or "",
            "viewpoint_override": bool(snap.get("viewpoint_override")),
            "advice_override": bool(snap.get("advice_override")),
        },
    )
    db.commit()


def get_period_snapshot(db: Session, kind: str, anchor: str) -> Optional[Dict[str, Any]]:
    horizon = "month" if str(kind) == "month" else "week"
    _start, _end, key = period_bounds(horizon, parse_anchor(anchor))
    row = db.execute(
        text(
            """
            SELECT snapshot_json, viewpoint_md, advice_md, viewpoint_override, advice_override
            FROM market_period_review
            WHERE period_type = :t AND period_key = :k
            """
        ),
        {"t": horizon, "k": key},
    ).mappings().first()
    if not row:
        return None
    data = _as_dict(row.get("snapshot_json"))
    data["viewpoint_md"] = row.get("viewpoint_md") or data.get("viewpoint_md") or ""
    data["advice_md"] = row.get("advice_md") or data.get("advice_md") or ""
    data["viewpoint_override"] = bool(row.get("viewpoint_override"))
    data["advice_override"] = bool(row.get("advice_override"))
    data["period_type"] = data.get("period_type") or horizon
    data["period_key"] = data.get("period_key") or key
    data["markdown"] = render_period_markdown(data)
    return data


def update_period_text(
    db: Session,
    kind: str,
    anchor: str,
    *,
    viewpoint_md: Optional[str] = None,
    advice_md: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    current = get_period_snapshot(db, kind, anchor)
    if not current:
        return None
    if viewpoint_md is not None:
        current["viewpoint_md"] = viewpoint_md
        current["viewpoint_override"] = True
    if advice_md is not None:
        current["advice_md"] = advice_md
        current["advice_override"] = True
    _save_period(db, current)
    return get_period_snapshot(db, kind, anchor)
