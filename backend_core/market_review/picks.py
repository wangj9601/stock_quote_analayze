# -*- coding: utf-8 -*-
"""每日复盘明日个股：主线不追 / 未涨停可跟踪 / 支线一只。不重跑全市场。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend_core.board_roles.classify import is_limit_up, limit_up_threshold_for_code
from backend_core.market_review.rules import yuan_to_yi
from backend_core.recommend.scoring import role_bonus

logger = logging.getLogger(__name__)

DISCLAIMER = "规则合成参考，非投资建议。这是明日计划，不是按收盘价买入。"
TRIGGER_TRACK = "高开越过压力不追，回踩支撑看是否守住。"
NO_CHASE_CAP = 6
AVOID_CAP = 16
INDUSTRY_CAP = 6
SIDELINE_CAP = 2
TRACK_CAP_WARM = 10
TRACK_CAP_COLD = 6


def _norm_code(code: Any) -> str:
    s = str(code or "").strip()
    if s.isdigit() and len(s) < 6:
        s = s.zfill(6)
    return s


def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def limit_band_for_code(code: Any) -> str:
    return "20cm" if limit_up_threshold_for_code(code) >= 15 else "10cm"


def track_cap(season: Any, passed: int, total: int, volume: Any, label: Any, has_main: bool) -> int:
    """缩量或没有主线时为 0。春/夏且门槛过半为 10，否则 6。"""
    if not has_main:
        return 0
    if str(volume or "") == "shrink" or str(label or "") == "缩量调整":
        return 0
    warm = str(season or "") in ("春", "夏") and total > 0 and int(passed) * 2 >= int(total)
    return TRACK_CAP_WARM if warm else TRACK_CAP_COLD


def macd_label(dif: Any, dea: Any, hist: Any) -> str:
    d = _f(dif)
    e = _f(dea)
    h = _f(hist)
    if d is None or e is None:
        return "--"
    cross = "金叉" if d > e else "死叉" if d < e else "粘合"
    if h is None:
        return cross
    axis = "零轴上" if h > 0 else "零轴下" if h < 0 else "零轴"
    return f"{cross}/{axis}"


def should_downgrade(macd: Any, rsi: Any, trend: Any) -> bool:
    """死叉、RSI 低于 40、斜率向下三者同时成立才降级。超买单独不否决。"""
    label = str(macd or "")
    rsi_v = _f(rsi)
    return "死叉" in label and rsi_v is not None and rsi_v < 40 and str(trend or "") == "向下"


def apply_indicator_gate(row: Dict[str, Any], *, macd: Any, rsi: Any, trend: Any) -> None:
    """只改可跟踪行。不追栏调用也不应被超买改掉。"""
    if row.get("stance") not in ("可跟踪",):
        return
    if should_downgrade(macd, rsi, trend):
        row["stance"] = "观察"
        row["downgrade"] = "死叉、RSI低于40且斜率向下，降为观察"


def long_upper_shadow(quote: Dict[str, Any]) -> bool:
    o, h, l, c = (_f(quote.get(k)) for k in ("open", "high", "low", "close"))
    if None in (o, h, l, c):
        return False
    rng = h - l
    if rng <= 0 or c <= 0:
        return False
    upper = h - max(o, c)
    body = abs(c - o)
    return upper / rng >= 0.5 and upper >= body * 2 and upper / c >= 0.02


def _trigger_text(sup: Any, res: Any, *, chase: bool) -> str:
    sup_v = _f(sup)
    res_v = _f(res)
    if chase:
        if res_v is not None:
            return f"次日看开盘是否越过压力 {res_v:.2f}，不追。"
        return "次日只看溢价，不追。"
    bits = []
    if res_v is not None:
        bits.append(f"高开越过压力 {res_v:.2f} 不追")
    else:
        bits.append("高开不追")
    if sup_v is not None:
        bits.append(f"回踩支撑 {sup_v:.2f} 看是否守住")
    else:
        bits.append("回踩支撑看是否守住")
    return "，".join(bits) + "。"


def assemble_picks(
    *,
    constituents: Set[str],
    quotes: Dict[str, Dict[str, Any]],
    zt_rows: Sequence[Dict[str, Any]],
    strategy_by_code: Dict[str, Dict[str, Any]],
    roles: Dict[str, str],
    season: Any,
    gates_passed: int,
    gates_total: int,
    tape_label: Any,
    tape_volume: Any,
    main: Optional[Dict[str, Any]],
    sideline_rep: Any,
    prev_zt_codes: Set[str],
    concept_codes: Optional[Set[str]],
    brief_stance: Dict[str, str],
    industry_name: str = "",
) -> Dict[str, Any]:
    """纯组栏。成分空则三栏皆空。"""
    empty = {
        "disclaimer": DISCLAIMER,
        "note": "主线成分不足",
        "mode": "empty",
        "track_cap": 0,
        "no_chase": [],
        "track": [],
        "sideline": [],
        "avoid": [],
    }
    universe = {_norm_code(c) for c in constituents if _norm_code(c)}
    if concept_codes:
        narrowed = universe & {_norm_code(c) for c in concept_codes}
        if narrowed:
            universe = narrowed
    if not universe or not main or not main.get("board_name"):
        return empty

    ind_name = industry_name or str(main.get("board_name") or "")
    zt_by: Dict[str, Dict[str, Any]] = {}
    for row in zt_rows:
        code = _norm_code(row.get("code"))
        if code:
            zt_by[code] = row

    no_chase_src = []
    for code in universe:
        quote = quotes.get(code) or {}
        zt = zt_by.get(code)
        chg = quote.get("change_percent")
        if chg is None and zt:
            chg = zt.get("change_percent")
        if zt is None and not is_limit_up(code, chg):
            continue
        brk = int((zt or {}).get("break_count") or 0)
        seal = _f((zt or {}).get("seal_fund"))
        seal_yi = (zt or {}).get("seal_yi")
        if seal_yi is None and seal is not None:
            conv = yuan_to_yi(seal)
            seal_yi = None if conv is None else round(conv, 2)
        no_chase_src.append(
            {
                "code": code,
                "name": (zt or {}).get("name") or quote.get("name") or code,
                "industry": ind_name,
                "stance": "炸板不追" if brk > 0 else "不追",
                "board_count": (zt or {}).get("board_count"),
                "seal_yi": seal_yi,
                "seal_fund": seal or 0,
                "break_count": brk,
                "limit_band": limit_band_for_code(code),
                "change_percent": _f((quote or {}).get("change_percent") if quote else None)
                or _f((zt or {}).get("change_percent")),
                "strategies": [],
                "brief_stance": brief_stance.get(code) or "",
                "trigger": "次日只看溢价，不追。",
            }
        )
    no_chase_src.sort(key=lambda r: (-(r.get("seal_fund") or 0), -(r.get("change_percent") or 0)))
    no_chase = no_chase_src[:NO_CHASE_CAP]
    for row in no_chase:
        row.pop("seal_fund", None)
    blocked = {r["code"] for r in no_chase_src}

    cap = track_cap(season, gates_passed, gates_total, tape_volume, tape_label, True)
    retreat = cap == 0
    track: List[Dict[str, Any]] = []
    sideline: List[Dict[str, Any]] = []
    avoid: List[Dict[str, Any]] = []

    if retreat:
        for code in universe:
            quote = quotes.get(code) or {}
            zt = zt_by.get(code)
            reasons = []
            if zt and int(zt.get("break_count") or 0) > 0:
                reasons.append("炸板")
            if code in prev_zt_codes and _f(quote.get("change_percent")) is not None and float(quote["change_percent"]) < 0:
                reasons.append("由强转弱")
            if long_upper_shadow(quote):
                reasons.append("长上影")
            if not reasons:
                continue
            avoid.append(
                {
                    "code": code,
                    "name": (zt or {}).get("name") or quote.get("name") or code,
                    "industry": ind_name,
                    "stance": "回避",
                    "reason": "、".join(reasons),
                    "change_percent": _f(quote.get("change_percent")),
                }
            )
        def _avoid_key(row: Dict[str, Any]) -> tuple:
            reason = str(row.get("reason") or "")
            return (
                0 if "炸板" in reason else 1 if "由强转弱" in reason else 2,
                -(row.get("change_percent") or 0),
            )

        avoid.sort(key=_avoid_key)
        avoid = avoid[:AVOID_CAP]
        note = "" if avoid else "无新增跟踪"
        return {
            "disclaimer": DISCLAIMER,
            "note": note,
            "mode": "retreat",
            "track_cap": 0,
            "no_chase": [],
            "track": [],
            "sideline": [],
            "avoid": avoid,
        }

    ranked = []
    for code, info in strategy_by_code.items():
        code = _norm_code(code)
        if code not in universe or code in blocked:
            continue
        quote = quotes.get(code) or {}
        if is_limit_up(code, quote.get("change_percent")) or code in zt_by:
            continue
        strategies = list(info.get("strategies") or [])
        role = roles.get(code)
        best = _f(info.get("best_score"))
        score = len(strategies) * 10.0 + role_bonus(role) + (min(best, 100.0) * 0.3 if best is not None else 0.0)
        ranked.append(
            {
                "code": code,
                "name": info.get("name") or quote.get("name") or code,
                "industry": ind_name,
                "stance": "可跟踪",
                "strategies": strategies,
                "role": role or "",
                "score": round(score, 2),
                "change_percent": _f(quote.get("change_percent")),
                "brief_stance": brief_stance.get(code) or "",
                "trigger": TRIGGER_TRACK,
                "pattern": "无明确形态",
                "macd": "--",
                "rsi": None,
                "kdj": "--",
                "trend": "--",
            }
        )
    ranked.sort(key=lambda r: -float(r.get("score") or 0))
    per_ind: Dict[str, int] = {}
    for row in ranked:
        ind = str(row.get("industry") or "")
        if per_ind.get(ind, 0) >= INDUSTRY_CAP:
            continue
        if len(track) >= cap:
            break
        per_ind[ind] = per_ind.get(ind, 0) + 1
        track.append(row)

    reps = sideline_rep if isinstance(sideline_rep, list) else ([sideline_rep] if sideline_rep else [])
    seen_side: Set[str] = set()
    for rep in reps:
        if len(sideline) >= SIDELINE_CAP:
            break
        if not isinstance(rep, dict) or not rep.get("code"):
            continue
        code = _norm_code(rep.get("code"))
        if not code or code in seen_side or is_limit_up(code, rep.get("change_percent")):
            continue
        seen_side.add(code)
        sideline.append(
            {
                "code": code,
                "name": rep.get("name") or code,
                "industry": rep.get("industry") or "",
                "stance": "只观察",
                "change_percent": _f(rep.get("change_percent")),
                "brief_stance": brief_stance.get(code) or "",
            }
        )

    return {
        "disclaimer": DISCLAIMER,
        "note": "",
        "mode": "plan",
        "track_cap": cap,
        "no_chase": no_chase,
        "track": track,
        "sideline": sideline,
        "avoid": [],
    }


def _query_codes(db: Session, sql: str, params: Dict[str, Any]) -> List[Any]:
    try:
        return db.execute(text(sql), params).fetchall()
    except Exception:
        logger.exception("复盘个股查询失败")
        db.rollback()
        return []


def _load_constituents(db: Session, board_code: str) -> Set[str]:
    rows = _query_codes(
        db,
        """
        SELECT stock_code FROM industry_board_constituents
        WHERE board_code = :bc
        """,
        {"bc": str(board_code)},
    )
    return {_norm_code(r[0]) for r in rows if r and r[0]}


def _load_concept_members(db: Session, board_codes: Sequence[str]) -> Set[str]:
    clean = [str(c).strip() for c in board_codes if str(c or "").strip()]
    if not clean:
        return set()
    rows = _query_codes(
        db,
        """
        SELECT stock_code FROM concept_board_constituents
        WHERE board_code = ANY(:codes)
        """,
        {"codes": clean},
    )
    return {_norm_code(r[0]) for r in rows if r and r[0]}


def _load_quotes(db: Session, trade_date: str, codes: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    clean = [c for c in {_norm_code(x) for x in codes} if c]
    if not clean:
        return {}
    rows = _query_codes(
        db,
        """
        SELECT code, name, open, high, low, close, change_percent
        FROM historical_quotes
        WHERE date = :d AND code = ANY(:codes)
        """,
        {"d": trade_date[:10], "codes": clean},
    )
    out = {}
    for code, name, o, h, l, c, chg in rows:
        key = _norm_code(code)
        out[key] = {
            "name": name,
            "open": _f(o),
            "high": _f(h),
            "low": _f(l),
            "close": _f(c),
            "change_percent": _f(chg),
        }
    return out


def _load_zt(db: Session, trade_date: str) -> List[Dict[str, Any]]:
    rows = _query_codes(
        db,
        """
        SELECT code, name, change_percent, seal_fund, board_count, break_count
        FROM stock_zt_pool_daily
        WHERE trade_date = :d
        """,
        {"d": trade_date[:10]},
    )
    out = []
    for code, name, chg, seal, board_count, brk in rows:
        seal_f = _f(seal)
        yi = yuan_to_yi(seal_f) if seal_f is not None else None
        out.append(
            {
                "code": _norm_code(code),
                "name": name,
                "change_percent": _f(chg),
                "seal_fund": seal_f,
                "seal_yi": None if yi is None else round(yi, 2),
                "board_count": int(board_count or 0),
                "break_count": int(brk or 0),
            }
        )
    return out


def _sideline_rep(db: Session, trade_date: str, sidelines: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered = sorted(
        [s for s in sidelines if s and _f(s.get("net_inflow")) and float(s["net_inflow"]) > 0],
        key=lambda s: -float(s.get("net_inflow") or 0),
    )
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for board in ordered:
        if len(out) >= SIDELINE_CAP:
            break
        if _f(board.get("change_percent")) is None or float(board["change_percent"]) <= 0:
            continue
        code = str(board.get("board_code") or "").strip()
        if not code:
            continue
        rows = _query_codes(
            db,
            """
            SELECT h.code, h.name, h.change_percent
            FROM industry_board_constituents c
            JOIN historical_quotes h ON h.code = c.stock_code AND h.date = :d
            WHERE c.board_code = :bc AND h.change_percent > 0
            ORDER BY h.change_percent DESC
            LIMIT 40
            """,
            {"d": trade_date[:10], "bc": code},
        )
        for stock_code, name, chg in rows:
            if len(out) >= SIDELINE_CAP:
                break
            if is_limit_up(stock_code, chg):
                continue
            key = _norm_code(stock_code)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "code": key,
                    "name": name,
                    "change_percent": _f(chg),
                    "industry": board.get("board_name") or "",
                }
            )
    return out


def _roles_for_board(db: Session, board_code: str) -> Dict[str, str]:
    try:
        from backend_core.board_roles.service import extract_leader_mid_from_payload, fetch_board_roles_payload

        payload = fetch_board_roles_payload(
            db,
            board_type="industry",
            board_code=str(board_code),
            board_code_source="tonghuashun",
            limit=None,
        )
        picked = extract_leader_mid_from_payload(payload)
    except Exception:
        logger.exception("主线龙头中军读取失败")
        db.rollback()
        return {}
    out: Dict[str, str] = {}
    for row in picked.get("leaders") or []:
        out[_norm_code(row.get("code"))] = "leader"
    for row in picked.get("mids") or []:
        code = _norm_code(row.get("code"))
        out.setdefault(code, "mid")
    return out


def _brief_map(db: Session, trade_date: str) -> Dict[str, str]:
    try:
        from backend_core.recommend.store import get_brief

        brief = get_brief(db, horizon="daily", asof_date=trade_date[:10])
    except Exception:
        logger.exception("读取策略推荐简报失败")
        db.rollback()
        return {}
    if not brief:
        return {}
    out = {}
    for item in brief.get("items") or []:
        if not isinstance(item, dict):
            continue
        code = _norm_code(item.get("code"))
        if code and item.get("stance"):
            out[code] = str(item.get("stance"))
    return out


def _index_strategies(grouped: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    by: Dict[str, Dict[str, Any]] = {}
    for rows in (grouped or {}).values():
        for row in rows or []:
            code = _norm_code(row.get("code"))
            if not code:
                continue
            slot = by.setdefault(code, {"strategies": [], "best_score": None, "name": row.get("name")})
            st = row.get("strategy")
            if st and st not in slot["strategies"]:
                slot["strategies"].append(st)
            sc = _f(row.get("score"))
            if sc is not None and (slot["best_score"] is None or sc > slot["best_score"]):
                slot["best_score"] = sc
            if row.get("name"):
                slot["name"] = row["name"]
    return by


def _slope_label(closes: Sequence[float]) -> str:
    ys = [float(x) for x in closes[-20:] if x is not None]
    if len(ys) < 10 or not ys[-1]:
        return "--"
    m = len(ys)
    xbar = (m - 1) / 2.0
    ybar = sum(ys) / m
    num = sum((i - xbar) * (ys[i] - ybar) for i in range(m))
    den = sum((i - xbar) ** 2 for i in range(m)) or 1.0
    rel = (num / den) / ys[-1]
    if rel > 0.001:
        return "向上"
    if rel < -0.001:
        return "向下"
    return "走平"


def _kdj_label(kdj: Dict[str, Any]) -> str:
    k = _f(kdj.get("k"))
    j = _f(kdj.get("j"))
    if k is None:
        return "--"
    if k >= 80 or (j is not None and j >= 100):
        return "超买"
    if k <= 20 or (j is not None and j <= 0):
        return "超卖"
    return "中性"


def _load_bars(db: Session, trade_date: str, codes: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    clean = [c for c in codes if c]
    if not clean:
        return {}
    start = (datetime.strptime(trade_date[:10], "%Y-%m-%d") - timedelta(days=180)).date().isoformat()
    rows = _query_codes(
        db,
        """
        SELECT code, date, open, high, low, close
        FROM historical_quotes
        WHERE code = ANY(:codes) AND date <= :d AND date >= :start
        ORDER BY code, date
        """,
        {"codes": clean, "d": trade_date[:10], "start": start},
    )
    out: Dict[str, List[Dict[str, Any]]] = {}
    for code, dt, o, h, l, c in rows:
        key = _norm_code(code)
        out.setdefault(key, []).append(
            {
                "date": str(dt)[:10],
                "open": _f(o),
                "high": _f(h),
                "low": _f(l),
                "close": _f(c),
            }
        )
    return out


def _macd_table(db: Session, trade_date: str, codes: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    clean = [c for c in codes if c]
    if not clean:
        return {}
    rows = _query_codes(
        db,
        """
        SELECT code, dif, dea, macd
        FROM macd_indicators
        WHERE market_type = 'CN' AND date = :d AND code = ANY(:codes)
        """,
        {"d": trade_date[:10], "codes": clean},
    )
    return {
        _norm_code(code): {"dif": _f(dif), "dea": _f(dea), "hist": _f(hist)}
        for code, dif, dea, hist in rows
    }


def enrich_picks(db: Session, trade_date: str, picks: Dict[str, Any]) -> Dict[str, Any]:
    """不追补压力；可跟踪补支撑压力与指标。缩量回避不补。"""
    no_chase = list(picks.get("no_chase") or [])
    track = list(picks.get("track") or [])
    codes = [r.get("code") for r in no_chase + track if r.get("code")]
    if not codes:
        return picks
    try:
        from backend_core.recommend.sr_levels import compute_sr_for_codes

        sr = compute_sr_for_codes(db, codes, trade_date[:10])
    except Exception:
        logger.exception("短名单支撑阻力失败")
        db.rollback()
        sr = {}
    bars = _load_bars(db, trade_date, [r.get("code") for r in track if r.get("code")])
    macd_rows = _macd_table(db, trade_date, [r.get("code") for r in track if r.get("code")])
    try:
        from backend_api.stock.stock_analysis import TechnicalIndicators
    except Exception:
        logger.exception("技术指标模块不可用")
        TechnicalIndicators = None  # type: ignore
    try:
        from backend_core.analysis.chart_patterns.engine import _pattern_label_zh, detect_all_counted
    except Exception:
        logger.exception("形态识别模块不可用")
        detect_all_counted = None  # type: ignore
        _pattern_label_zh = None  # type: ignore

    for row in no_chase:
        levels = sr.get(row["code"]) or {}
        row["p_res"] = levels.get("p_res")
        row["trigger"] = _trigger_text(None, levels.get("p_res"), chase=True)

    for row in track:
        levels = sr.get(row["code"]) or {}
        row["p_sup"] = levels.get("p_sup")
        row["p_res"] = levels.get("p_res")
        row["trigger"] = _trigger_text(levels.get("p_sup"), levels.get("p_res"), chase=False)
        series = bars.get(row["code"]) or []
        closes = [b["close"] for b in series if b.get("close") is not None]
        highs = [b["high"] for b in series if b.get("high") is not None]
        lows = [b["low"] for b in series if b.get("low") is not None]
        stored = macd_rows.get(row["code"]) or {}
        dif, dea, hist = stored.get("dif"), stored.get("dea"), stored.get("hist")
        if dif is None and TechnicalIndicators is not None and len(closes) >= 26:
            try:
                calc = TechnicalIndicators.calculate_macd(closes)
                dif, dea, hist = calc.get("macd"), calc.get("signal"), calc.get("histogram")
            except Exception:
                logger.exception("MACD 现算失败 %s", row.get("code"))
        row["macd"] = macd_label(dif, dea, hist)
        rsi = None
        if TechnicalIndicators is not None and len(closes) >= 15:
            try:
                rsi = TechnicalIndicators.calculate_rsi(closes)
            except Exception:
                logger.exception("RSI 现算失败 %s", row.get("code"))
        row["rsi"] = rsi
        kdj_txt = "--"
        if TechnicalIndicators is not None and len(closes) >= 9 and len(highs) >= 9 and len(lows) >= 9:
            try:
                kdj_txt = _kdj_label(TechnicalIndicators.calculate_kdj(highs, lows, closes))
            except Exception:
                logger.exception("KDJ 现算失败 %s", row.get("code"))
        row["kdj"] = kdj_txt
        trend = _slope_label(closes)
        row["trend"] = trend
        apply_indicator_gate(row, macd=row["macd"], rsi=rsi, trend=trend)
        if row.get("stance") == "观察" and row.get("downgrade"):
            row["trigger"] = f"{row['trigger']}{row['downgrade']}。"
        pattern = "无明确形态"
        if detect_all_counted is not None and len(series) >= 30:
            try:
                hits, _n = detect_all_counted(series)
                if hits:
                    hit = hits[0]
                    pattern = str(hit.get("label") or "")
                    if not pattern and _pattern_label_zh is not None:
                        pattern = _pattern_label_zh(str(hit.get("pattern_type") or ""))
                    pattern = pattern or "无明确形态"
            except Exception:
                logger.exception("形态识别失败 %s", row.get("code"))
                pattern = "--"
        row["pattern"] = pattern
    picks["no_chase"] = no_chase
    picks["track"] = track
    return picks


def build_review_picks(
    db: Session,
    trade_date: str,
    *,
    sector: Dict[str, Any],
    tape: Dict[str, Any],
    season: Dict[str, Any],
    gates: Dict[str, Any],
    concept_board_codes: Sequence[str],
    prev_date: Optional[str],
) -> Dict[str, Any]:
    main = (sector or {}).get("main") or {}
    board_code = str(main.get("board_code") or "").strip()
    if not board_code or not main.get("board_name"):
        return assemble_picks(
            constituents=set(),
            quotes={},
            zt_rows=[],
            strategy_by_code={},
            roles={},
            season=season.get("season"),
            gates_passed=int(gates.get("passed") or 0),
            gates_total=int(gates.get("total") or 0),
            tape_label=tape.get("label"),
            tape_volume=tape.get("volume"),
            main=None,
            sideline_rep=None,
            prev_zt_codes=set(),
            concept_codes=None,
            brief_stance={},
        )
    constituents = _load_constituents(db, board_code)
    if not constituents:
        return assemble_picks(
            constituents=set(),
            quotes={},
            zt_rows=[],
            strategy_by_code={},
            roles={},
            season=season.get("season"),
            gates_passed=int(gates.get("passed") or 0),
            gates_total=int(gates.get("total") or 0),
            tape_label=tape.get("label"),
            tape_volume=tape.get("volume"),
            main=main,
            sideline_rep=None,
            prev_zt_codes=set(),
            concept_codes=None,
            brief_stance={},
        )
    concept_members = _load_concept_members(db, concept_board_codes) if concept_board_codes else set()
    quotes = _load_quotes(db, trade_date, constituents)
    zt_rows = _load_zt(db, trade_date)
    prev_zt = {r["code"] for r in _load_zt(db, prev_date)} if prev_date else set()
    try:
        from backend_core.recommend.candidates import collect_strategy_buy_candidates

        grouped = collect_strategy_buy_candidates(db, trade_date[:10])
    except Exception:
        logger.exception("策略买点汇总失败")
        db.rollback()
        grouped = {}
    picks = assemble_picks(
        constituents=constituents,
        quotes=quotes,
        zt_rows=zt_rows,
        strategy_by_code=_index_strategies(grouped),
        roles=_roles_for_board(db, board_code),
        season=season.get("season"),
        gates_passed=int(gates.get("passed") or 0),
        gates_total=int(gates.get("total") or 0),
        tape_label=tape.get("label"),
        tape_volume=tape.get("volume"),
        main=main,
        sideline_rep=_sideline_rep(db, trade_date, (sector or {}).get("sidelines") or []),
        prev_zt_codes=prev_zt,
        concept_codes=concept_members or None,
        brief_stance=_brief_map(db, trade_date),
        industry_name=str(main.get("board_name") or ""),
    )
    if picks.get("mode") == "retreat":
        return picks
    return enrich_picks(db, trade_date, picks)
