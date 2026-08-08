# -*- coding: utf-8 -*-
"""策略命中行 → 统一买卖建议（主依据策略+KDE/箱体；Fib/Pivot/共振带仅软参考）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ALIGN_TOL_PCT = 0.015


def _f(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _zone(
    *,
    low: Optional[float] = None,
    high: Optional[float] = None,
    price: Optional[float] = None,
    label: str,
    basis: str,
) -> Dict[str, Any]:
    z: Dict[str, Any] = {"label": label, "basis": basis}
    if price is not None:
        z["price"] = round(float(price), 4)
    if low is not None:
        z["low"] = round(float(low), 4)
    if high is not None:
        z["high"] = round(float(high), 4)
    return z


def _kde_support(row: Dict[str, Any]) -> Optional[float]:
    ns = _f(row.get("nearest_support"))
    if ns is not None:
        return ns
    st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
    return _f(st.get("nearest_support"))


def _kde_resistance(row: Dict[str, Any]) -> Optional[float]:
    nr = _f(row.get("nearest_resistance"))
    if nr is not None:
        return nr
    st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
    return _f(st.get("nearest_resistance"))


def _fmt_px(v: Any) -> str:
    return f"{round(float(v), 2):.2f}"


def _within_tol(a: Optional[float], b: Optional[float], tol_pct: float = ALIGN_TOL_PCT) -> bool:
    if a is None or b is None:
        return False
    pa, pb = float(a), float(b)
    if pa <= 0:
        return False
    return abs(pb - pa) / pa <= tol_pct


def _ref_summary(ref: Optional[Dict[str, Any]]) -> str:
    if not ref:
        return ""
    classic_ok = bool(ref.get("ok"))
    parts: List[str] = []
    if classic_ok:
        fs = ref.get("nearest_fib_support")
        fr = ref.get("nearest_fib_resistance")
        cs = ref.get("nearest_cam_support")
        cr = ref.get("nearest_cam_resistance")
        ps = ref.get("nearest_pivot_support")
        pr = ref.get("nearest_pivot_resistance")
        if fs is not None:
            parts.append(f"Fib支撑≈{_fmt_px(fs)}")
        if fr is not None:
            parts.append(f"Fib压力≈{_fmt_px(fr)}")
        if cs is not None:
            parts.append(f"Cam支撑≈{_fmt_px(cs)}")
        if cr is not None:
            parts.append(f"Cam压力≈{_fmt_px(cr)}")
        if ps is not None:
            parts.append(f"Pivot支撑≈{_fmt_px(ps)}")
        if pr is not None:
            parts.append(f"Pivot压力≈{_fmt_px(pr)}")
    vp = ref.get("volume_profile") if isinstance(ref.get("volume_profile"), dict) else {}
    if vp.get("ok"):
        if vp.get("poc") is not None:
            parts.append(f"VP POC≈{_fmt_px(vp['poc'])}")
        vs = ref.get("nearest_vp_support")
        if vs is None:
            vs = vp.get("nearest_support")
        vr = ref.get("nearest_vp_resistance")
        if vr is None:
            vr = vp.get("nearest_resistance")
        if vs is not None:
            parts.append(f"VP支撑≈{_fmt_px(vs)}")
        if vr is not None:
            parts.append(f"VP压力≈{_fmt_px(vr)}")
    conf = ref.get("confluence_zones") if isinstance(ref.get("confluence_zones"), dict) else {}
    if conf.get("ok"):
        nz_s = conf.get("nearest_support_zone") or {}
        nz_r = conf.get("nearest_resistance_zone") or {}
        if nz_s.get("center") is not None:
            parts.append(f"共振支撑≈{_fmt_px(nz_s['center'])}")
        if nz_r.get("center") is not None:
            parts.append(f"共振压力≈{_fmt_px(nz_r['center'])}")
    if not parts:
        return ""
    return "参考：" + " / ".join(parts)


def _resonance_note(
    primary: Optional[float],
    ref_a: Optional[float],
    ref_b: Optional[float],
    *,
    tol_pct: float = ALIGN_TOL_PCT,
) -> Optional[str]:
    if primary is None:
        return None
    for r in (ref_a, ref_b):
        if r is None or primary <= 0:
            continue
        if abs(float(r) - float(primary)) / float(primary) <= tol_pct:
            return f"附近另有 Fib/Pivot 共振（≈{_fmt_px(r)}）"
    return None


def _soft_align_confluence(
    *,
    stop_zone: Optional[Dict[str, Any]],
    take_profit: Optional[Dict[str, Any]],
    kde_s: Optional[float],
    kde_r: Optional[float],
    ref: Dict[str, Any],
    summary_bits: List[str],
    confidence: str,
) -> tuple:
    """共振带与 KDE 同向贴近时：标注 + 展示价对齐带中心（basis=kde+confluence）。"""
    conf = ref.get("confluence_zones") if isinstance(ref.get("confluence_zones"), dict) else {}
    if not conf.get("ok"):
        return stop_zone, take_profit, confidence

    nz_s = conf.get("nearest_support_zone") if isinstance(conf.get("nearest_support_zone"), dict) else None
    nz_r = conf.get("nearest_resistance_zone") if isinstance(conf.get("nearest_resistance_zone"), dict) else None
    center_s = _f((nz_s or {}).get("center"))
    center_r = _f((nz_r or {}).get("center"))

    if center_s is not None and kde_s is not None and _within_tol(kde_s, center_s):
        summary_bits.append(
            f"共振支撑带≈{_fmt_px(center_s)}"
            f"（{nz_s.get('low')}–{nz_s.get('high')}，来源{'+'.join(nz_s.get('sources') or [])}）"
            "与 KDE 同向贴近"
        )
        if stop_zone and (stop_zone.get("basis") or "").startswith("kde"):
            stop_zone = dict(stop_zone)
            stop_zone["price"] = round(center_s, 4)
            if nz_s.get("low") is not None:
                stop_zone["low"] = round(float(nz_s["low"]), 4)
            if nz_s.get("high") is not None:
                stop_zone["high"] = round(float(nz_s["high"]), 4)
            stop_zone["basis"] = "kde+confluence"
            stop_zone["label"] = (stop_zone.get("label") or "") + "（对齐共振带）"
            stop_zone["kde_price"] = round(float(kde_s), 4)
            if confidence == "medium":
                confidence = "high"

    if center_r is not None and kde_r is not None and _within_tol(kde_r, center_r):
        summary_bits.append(
            f"共振压力带≈{_fmt_px(center_r)}"
            f"（{nz_r.get('low')}–{nz_r.get('high')}，来源{'+'.join(nz_r.get('sources') or [])}）"
            "与 KDE 同向贴近"
        )
        if take_profit and (take_profit.get("basis") or "").startswith("kde"):
            take_profit = dict(take_profit)
            take_profit["prices"] = [round(center_r, 4)]
            take_profit["basis"] = "kde+confluence"
            take_profit["label"] = (take_profit.get("label") or "") + "（对齐共振带）"
            take_profit["kde_price"] = round(float(kde_r), 4)
            if confidence == "medium":
                confidence = "high"

    return stop_zone, take_profit, confidence


def build_trade_advice(
    strategy: str,
    row: Dict[str, Any],
    *,
    reference_levels: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成 trade_advice。strategy: gms|urt|sbbr|rpe"""
    kind = (strategy or "").strip().lower()
    ref = reference_levels if isinstance(reference_levels, dict) else None
    buy_zone: Optional[Dict[str, Any]] = None
    stop_zone: Optional[Dict[str, Any]] = None
    take_profit: Optional[Dict[str, Any]] = None
    sell_triggers: List[Dict[str, Any]] = []
    action = "watch"
    confidence = "medium"
    summary_bits: List[str] = []

    kde_s = _kde_support(row)
    kde_r = _kde_resistance(row)
    close = _f(row.get("close") or row.get("latest_price") or row.get("price"))

    if kind == "gms":
        buy_type = (row.get("buy_type") or "").strip()
        left = bool(row.get("left_buy_signal"))
        right = bool(row.get("right_buy_signal"))
        sell = bool(row.get("sell_signal"))
        board_weak = bool(row.get("board_weak"))
        if left or buy_type == "左侧":
            action = "buy"
            buy_zone = _zone(
                price=kde_s or close,
                label="左侧吸筹：贴近均值/结构支撑附近低吸",
                basis="gms_left+kde" if kde_s else "gms_left",
            )
            summary_bits.append("GMS左侧买点：宜在结构支撑附近分批承接")
        elif right or buy_type == "右侧":
            action = "buy"
            buy_zone = _zone(
                price=close,
                label="右侧动量：突破后回踩不破支撑再跟",
                basis="gms_right",
            )
            summary_bits.append("GMS右侧买点：回踩不破支撑再跟进")
        if kde_s is not None:
            stop_zone = _zone(price=kde_s, label="结构支撑下方视为防守失效", basis="kde")
        if kde_r is not None:
            take_profit = {
                "label": "靠近结构压力减仓/止盈",
                "basis": "kde",
                "prices": [round(kde_r, 4)],
            }
        if sell:
            sell_triggers.append(
                {"type": "gms_sell_signal", "label": "策略卖点触发，考虑减仓/离场", "basis": "sell_signal"}
            )
            if action == "buy":
                confidence = "low"
        if board_weak:
            confidence = "low"
            summary_bits.append("主行业板走弱，降低仓位与信心")
            if action == "buy":
                action = "watch"

    elif kind == "urt":
        if bool(row.get("buy_signal")):
            action = "buy"
            ma20 = _f(row.get("ma20"))
            buy_zone = _zone(
                price=close or ma20,
                label="上升趋势买点：信号价附近或回踩MA20/支撑不破",
                basis="urt_buy+ma20" if ma20 else "urt_buy",
            )
            summary_bits.append("URT买点成立：回踩MA20或结构支撑不破可持有/加")
        if kde_s is not None:
            stop_zone = _zone(price=kde_s, label="跌破最近结构支撑止损", basis="kde")
        if kde_r is not None:
            take_profit = {"label": "压力区止盈", "basis": "kde", "prices": [round(kde_r, 4)]}
        tags = row.get("risk_tags") or []
        if any(
            (t.get("id") if isinstance(t, dict) else t) in ("structure_rr_poor", "rr_poor")
            for t in tags
        ):
            confidence = "low"
            if action == "buy":
                action = "watch"
            summary_bits.append("结构盈亏比偏弱，降级为观察")

    elif kind == "sbbr":
        entry = bool(row.get("entry_signal"))
        bottom = bool(row.get("bottom_matched"))
        entry_low = _f(row.get("entry_low"))
        d_low = _f(row.get("defense_low"))
        d_high = _f(row.get("defense_high"))
        box_s = _f(row.get("box_support"))
        box_r = _f(row.get("box_resistance"))
        if entry:
            action = "buy"
            buy_zone = _zone(
                price=entry_low or close,
                low=entry_low,
                label="做底入场：entry_low 附近承接",
                basis="sbbr_entry",
            )
            summary_bits.append("SBBR入场信号：在入场低点附近布局")
        elif bottom:
            action = "watch"
            summary_bits.append("已筑底未入场：纳入关注，等待入场确认")
        if d_low is not None or d_high is not None:
            stop_zone = _zone(
                low=d_low,
                high=d_high,
                price=d_low,
                label="防守带：收盘跌破防守下沿离场",
                basis="defense",
            )
            sell_triggers.append(
                {
                    "type": "defense_breach",
                    "label": f"收盘跌破防守下沿{d_low}",
                    "basis": "defense",
                }
            )
        elif box_s is not None:
            stop_zone = _zone(price=box_s, label="箱体下沿防守", basis="box")
        if box_r is not None:
            take_profit = {
                "label": "箱体上沿/突破看高",
                "basis": "box",
                "prices": [round(box_r, 4)],
            }
        elif kde_r is not None:
            take_profit = {"label": "结构压力止盈", "basis": "kde", "prices": [round(kde_r, 4)]}
        pa = row.get("position_advice")
        if pa:
            summary_bits.append(str(pa))

    elif kind == "rpe":
        sig = (row.get("signal_type") or "").strip().lower()
        entry = bool(row.get("entry_signal"))
        watch_only = bool(row.get("watch_only"))
        veto = bool(row.get("trend_veto"))
        if veto:
            action = "avoid"
            confidence = "low"
            summary_bits.append("板块斜率趋势否决，避免开仓")
        elif sig == "lead" or watch_only:
            action = "watch"
            summary_bits.append("领涨/仅观察：不追高，等待回踩或补涨确认")
        elif entry or sig == "catch_up":
            action = "buy"
            buy_zone = _zone(
                price=kde_s or close,
                label="补涨：回踩比价带下沿/结构支撑附近",
                basis="rpe_catch_up+kde" if kde_s else "rpe_catch_up",
            )
            summary_bits.append("RPE补涨可交易：支撑附近低吸")
        if kde_s is not None:
            stop_zone = _zone(price=kde_s, label="跌破结构支撑离场", basis="kde")
        if kde_r is not None:
            take_profit = {"label": "结构压力减仓", "basis": "kde", "prices": [round(kde_r, 4)]}
        plan = row.get("structure_plan") if isinstance(row.get("structure_plan"), dict) else {}
        if plan.get("note"):
            summary_bits.append(str(plan["note"]))

    else:
        summary_bits.append(f"未知策略 {kind}")
        action = "watch"
        confidence = "low"

    # 共振带软融合（不删 KDE 主依据；仅展示价/summary）
    if ref:
        stop_zone, take_profit, confidence = _soft_align_confluence(
            stop_zone=stop_zone,
            take_profit=take_profit,
            kde_s=kde_s,
            kde_r=kde_r,
            ref=ref,
            summary_bits=summary_bits,
            confidence=confidence,
        )

    # Fib/Pivot 共振提示（不覆盖主 stop）
    if ref and ref.get("ok"):
        note = _resonance_note(
            (stop_zone or {}).get("price") or (stop_zone or {}).get("low"),
            ref.get("nearest_fib_support"),
            ref.get("nearest_cam_support") or ref.get("nearest_pivot_support"),
        )
        if note:
            summary_bits.append(note)
        note2 = _resonance_note(
            (take_profit or {}).get("prices", [None])[0]
            if take_profit and take_profit.get("prices")
            else None,
            ref.get("nearest_fib_resistance"),
            ref.get("nearest_cam_resistance") or ref.get("nearest_pivot_resistance"),
        )
        if note2:
            summary_bits.append(note2)
        rs = _ref_summary(ref)
        if rs:
            summary_bits.append(rs)

    if not summary_bits:
        summary_bits.append("暂无明确买卖建议，仅供观察")

    # normalize take_profit shape
    if take_profit and "prices" not in take_profit and take_profit.get("price") is not None:
        take_profit["prices"] = [take_profit["price"]]

    return {
        "action": action,
        "buy_zone": buy_zone,
        "stop_zone": stop_zone,
        "take_profit": take_profit,
        "sell_triggers": sell_triggers,
        "summary": "；".join(summary_bits),
        "confidence": confidence,
        "kde_support": round(float(kde_s), 2) if kde_s is not None else None,
        "kde_resistance": round(float(kde_r), 2) if kde_r is not None else None,
        "reference_levels": ref,
    }
