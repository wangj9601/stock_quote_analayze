# -*- coding: utf-8 -*-
"""URT 买点检测；卖点规则对象化供回测扩展。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .indicators import build_indicators, hard_filter_pass
from .scoring import compute_score_breakdown


def history_calendar_days_for_fetch(cfg: Dict[str, Any]) -> int:
    """
    拉历史 K 线用日历跨度：至少覆盖策略 history_calendar_days，
    并保证足以支撑 KDE 最大回看（交易日 ×1.6 近似换算）；
    同时尽量覆盖均线积分最长周期（约 250 根）。
    """
    from .indicators import recommended_bars_for_ma_score

    hist = int(cfg.get("history_calendar_days") or 120)
    kde_max = int(cfg.get("kde_lookback_max") or 750)
    kde_cal = int(kde_max * 1.6) + 40
    ma_score_bars = int(recommended_bars_for_ma_score(cfg))
    ma_score_cal = int(ma_score_bars * 1.6) + 20
    return max(hist, kde_cal, ma_score_cal)


def _pick_confluence_nearest(
    conf: Dict[str, Any],
    price: float,
    *,
    prefer_strong: bool = True,
) -> Dict[str, Any]:
    """从共振带取现价下方最近支撑 / 上方最近阻力（可选优先 strong tier）。"""
    out: Dict[str, Any] = {
        "nearest_support": None,
        "nearest_resistance": None,
        "support_zone": None,
        "resistance_zone": None,
        "pick": None,
    }
    if not conf.get("ok"):
        return out

    def _zones(side: str) -> List[Dict[str, Any]]:
        key = "supports" if side == "support" else "resistances"
        rows = conf.get(key) or []
        return [z for z in rows if isinstance(z, dict) and z.get("center") is not None]

    def _center(z: Dict[str, Any]) -> Optional[float]:
        try:
            return float(z.get("center"))
        except (TypeError, ValueError):
            return None

    below = []
    for z in _zones("support"):
        c = _center(z)
        if c is not None and c < price:
            below.append(z)
    above = []
    for z in _zones("resistance"):
        c = _center(z)
        if c is not None and c > price:
            above.append(z)

    ns_zone = None
    if prefer_strong:
        strong_below = [z for z in below if z.get("tier") == "strong"]
        if strong_below:
            ns_zone = max(strong_below, key=lambda z: float(z["center"]))
    if ns_zone is None:
        nz = conf.get("nearest_support_zone")
        if isinstance(nz, dict) and _center(nz) is not None and float(nz["center"]) < price:
            ns_zone = nz
        elif below:
            ns_zone = max(below, key=lambda z: float(z["center"]))

    nr_zone = None
    if prefer_strong:
        strong_above = [z for z in above if z.get("tier") == "strong"]
        if strong_above:
            nr_zone = min(strong_above, key=lambda z: float(z["center"]))
    if nr_zone is None:
        nz = conf.get("nearest_resistance_zone")
        if isinstance(nz, dict) and _center(nz) is not None and float(nz["center"]) > price:
            nr_zone = nz
        elif above:
            nr_zone = min(above, key=lambda z: float(z["center"]))

    if ns_zone is not None:
        out["support_zone"] = ns_zone
        out["nearest_support"] = round(float(ns_zone["center"]), 2)
    if nr_zone is not None:
        out["resistance_zone"] = nr_zone
        out["nearest_resistance"] = round(float(nr_zone["center"]), 2)

    if ns_zone or nr_zone:
        used_strong = bool(
            (ns_zone and ns_zone.get("tier") == "strong")
            or (nr_zone and nr_zone.get("tier") == "strong")
        )
        out["pick"] = "confluence_strong" if used_strong and prefer_strong else "confluence"
    return out


def _compute_structure_levels(
    bars_desc: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    *,
    price: Optional[float],
) -> Dict[str, Any]:
    """
    信号日结构位：与个股关键价位同口径。
    1) ZigZag 结构锚窗 KDE（compute_kde_bundle）
    2) Fib/Pivot/Cam + VP → compute_confluence_from_reference
    3) 默认以共振带中心作为 nearest_support / nearest_resistance（供结构出场）
    bars_desc 为日期 DESC（最新在前）。
    """
    empty = {
        "support_levels": [],
        "resistance_levels": [],
        "nearest_support": None,
        "nearest_resistance": None,
        "kde_ok": False,
        "kde_reason": "insufficient_samples",
        "kde_bw": None,
        "kde_lookback_used": 0,
        "kde_lookback_expanded": False,
        "kde_window_mode": "calendar",
        "method": "kde_volume_weighted",
        "structure_level_source": None,
        "confluence_ok": False,
    }
    if not bars_desc or price is None:
        return empty
    try:
        px = float(price)
    except (TypeError, ValueError):
        return empty
    if px <= 0:
        return empty

    use_structural = cfg.get("structure_use_structural_window")
    if use_structural is None:
        use_structural = True
    use_confluence = cfg.get("structure_use_confluence")
    if use_confluence is None:
        use_confluence = True
    prefer_confluence = cfg.get("structure_prefer_confluence")
    if prefer_confluence is None:
        prefer_confluence = True
    prefer_strong = cfg.get("structure_prefer_strong_confluence")
    if prefer_strong is None:
        prefer_strong = True

    # 1) 结构锚窗 KDE（与 GMS / 个股 KeyLevels 同路径）
    from backend_core.strategies.gms.structure_levels import compute_structure_levels as gms_kde_structure

    kde_cfg = dict(cfg or {})
    if not bool(use_structural):
        # 强制日历窗：用配置初始回看（≠60 时 GMS 关闭结构锚）
        init_cal = int(
            kde_cfg.get("kde_lookback_days")
            or kde_cfg.get("kde_lookback_initial")
            or 60
        )
        if init_cal == 60:
            init_cal = 61
        kde_cfg["kde_lookback_days"] = init_cal
        kde_cfg["kde_lookback_initial"] = init_cal
    st = gms_kde_structure(bars_desc, kde_cfg, price=px)
    out = dict(empty)
    out.update(st or {})
    out["kde_nearest_support"] = st.get("nearest_support")
    out["kde_nearest_resistance"] = st.get("nearest_resistance")
    out["structure_level_source"] = "kde"
    out["method"] = "structural_kde+confluence" if use_confluence else "structural_kde"

    if not bool(use_confluence):
        return out

    # 2) classic + VP + confluence
    try:
        from backend_core.analysis.classic_levels import (
            DEFAULT_LOOKBACK,
            compute_classic_levels_from_bars,
        )
        from backend_core.analysis.confluence_zones import compute_confluence_from_reference
        from backend_core.analysis.volume_profile import compute_volume_profile_from_bars
    except Exception:
        return out

    asc = list(reversed(bars_desc))
    try:
        ref = compute_classic_levels_from_bars(asc, last_close=px)
        vp = compute_volume_profile_from_bars(asc, last_close=px, lookback=DEFAULT_LOOKBACK)
        ref["volume_profile"] = {
            "ok": bool(vp.get("ok")),
            "reason": vp.get("reason"),
            "lookback": vp.get("lookback"),
            "bars_used": vp.get("bars_used"),
            "poc": vp.get("poc"),
            "vah": vp.get("vah"),
            "val": vp.get("val"),
            "nearest_support": vp.get("nearest_support"),
            "nearest_resistance": vp.get("nearest_resistance"),
        }
        conf = compute_confluence_from_reference(
            ref,
            kde_support=st.get("nearest_support"),
            kde_resistance=st.get("nearest_resistance"),
            kde_supports=st.get("support_levels"),
            kde_resistances=st.get("resistance_levels"),
            kde_multi_windows=st.get("kde_multi_windows"),
            last_close=px,
            atr=ref.get("atr"),
        )
    except Exception:
        return out

    out["confluence_ok"] = bool(conf.get("ok"))
    out["confluence_zones"] = {
        "ok": bool(conf.get("ok")),
        "nearest_support_zone": conf.get("nearest_support_zone"),
        "nearest_resistance_zone": conf.get("nearest_resistance_zone"),
        "supports": (conf.get("supports") or [])[:6],
        "resistances": (conf.get("resistances") or [])[:6],
    }
    nz_s = conf.get("nearest_support_zone") if isinstance(conf.get("nearest_support_zone"), dict) else None
    nz_r = conf.get("nearest_resistance_zone") if isinstance(conf.get("nearest_resistance_zone"), dict) else None
    out["nearest_confluence_support"] = (
        round(float(nz_s["center"]), 2) if nz_s and nz_s.get("center") is not None else None
    )
    out["nearest_confluence_resistance"] = (
        round(float(nz_r["center"]), 2) if nz_r and nz_r.get("center") is not None else None
    )

    picked = _pick_confluence_nearest(conf, px, prefer_strong=bool(prefer_strong))
    if bool(prefer_confluence) and (picked.get("nearest_support") is not None or picked.get("nearest_resistance") is not None):
        if picked.get("nearest_support") is not None:
            out["nearest_support"] = picked["nearest_support"]
        if picked.get("nearest_resistance") is not None:
            out["nearest_resistance"] = picked["nearest_resistance"]
        out["structure_level_source"] = picked.get("pick") or "confluence"
        out["confluence_support_zone"] = picked.get("support_zone")
        out["confluence_resistance_zone"] = picked.get("resistance_zone")
        # 共振覆盖后重算 RR（与位置分/硬闸一致）
        try:
            from backend_core.strategies.gms.structure_levels import (
                compute_structure_rr,
                resolve_structure_rr_min_downside_pct,
                resolve_structure_rr_min_upside_pct,
            )

            floor_pct = resolve_structure_rr_min_downside_pct(cfg)
            up_pct = resolve_structure_rr_min_upside_pct(cfg)
            rr_info = compute_structure_rr(
                px,
                out.get("nearest_support"),
                out.get("nearest_resistance"),
                min_downside_pct=floor_pct,
                min_upside_pct=up_pct,
            )
            out["rr"] = rr_info.get("rr")
            out["rr_reason"] = rr_info.get("reason")
            out["rr_downside_floored"] = bool(rr_info.get("downside_floored"))
            out["rr_min_downside_pct"] = rr_info.get("min_downside_pct")
            out["rr_downside_raw"] = rr_info.get("downside_raw")
            out["rr_downside"] = rr_info.get("downside")
        except Exception:
            pass
    return out


def hydrate_detail_from_score_detail(detail: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 score_detail 回填顶层展示/判定字段。

    urt_signal_trace 表未存 ma5/ma10、中期阳线、多头布尔、过热涨幅等列，
    这些值写在 score_detail（inputs / parts / 顶层）里；历史回放重建 buy_logic
    时若只读顶层会得到 None，并误判「中期阳通过 / 多头未通过 / 涨幅=—」。
    """
    if not isinstance(detail, dict):
        return detail
    sd = detail.get("score_detail")
    if not isinstance(sd, dict):
        return detail
    inputs = sd.get("inputs") if isinstance(sd.get("inputs"), dict) else {}
    parts = sd.get("parts") if isinstance(sd.get("parts"), dict) else {}
    ma_bull = parts.get("ma_bull") if isinstance(parts.get("ma_bull"), dict) else {}
    yang_med = parts.get("yang_medium") if isinstance(parts.get("yang_medium"), dict) else {}

    def _fill(key: str, *candidates: Any) -> None:
        if detail.get(key) is not None:
            return
        for v in candidates:
            if v is not None:
                detail[key] = v
                return

    _fill("ma5", inputs.get("ma5"), ma_bull.get("ma5"))
    _fill("ma10", inputs.get("ma10"), ma_bull.get("ma10"))
    _fill("ma20_stack", ma_bull.get("ma20_stack"), inputs.get("ma20"))
    _fill("yang_count_10", inputs.get("yang_count_10"))
    _fill("yang_count_15", inputs.get("yang_count_15"))
    _fill("yang_count_20", inputs.get("yang_count_20"))
    for item in yang_med.get("items") or []:
        if not isinstance(item, dict) or item.get("window") is None:
            continue
        try:
            w = int(item["window"])
        except (TypeError, ValueError):
            continue
        _fill(f"yang_count_{w}", item.get("count"))
    _fill("yang_medium_ok", yang_med.get("ok"))
    _fill("yang_medium_detail", yang_med.get("items"))
    _fill("ma_bull_ok", ma_bull.get("ok"))
    _fill("ma_bear_ok", ma_bull.get("bear_ok"), inputs.get("ma_bear_ok"))
    _fill("ma_bull_periods", ma_bull.get("periods"))
    _fill("ma_bull_values", ma_bull.get("values"))
    _fill("ma_bull_score_periods", ma_bull.get("score_periods"))
    _fill("ma_bull_score_values", ma_bull.get("score_values"))
    _fill("ma_bull_depth", ma_bull.get("depth"))
    _fill("ret_from_low_n", sd.get("ret_from_low_n"))
    _fill("ma20_bias", sd.get("ma20_bias"))
    _fill("overheat_lookback_days", sd.get("overheat_lookback_days"))
    if not detail.get("overheat_hard_gate") and isinstance(sd.get("overheat_hard_gate"), dict):
        detail["overheat_hard_gate"] = sd["overheat_hard_gate"]
    if not detail.get("structure_hard_gate") and isinstance(sd.get("structure_hard_gate"), dict):
        detail["structure_hard_gate"] = sd["structure_hard_gate"]
    oh = detail.get("overheat_hard_gate") if isinstance(detail.get("overheat_hard_gate"), dict) else {}
    if detail.get("overheat_gate_ok") is None and oh:
        detail["overheat_gate_ok"] = not bool(oh.get("blocked"))
    gate = detail.get("structure_hard_gate") if isinstance(detail.get("structure_hard_gate"), dict) else {}
    if detail.get("structure_gate_ok") is None and gate:
        detail["structure_gate_ok"] = not bool(gate.get("blocked"))
    return detail


def build_buy_logic(detail: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    结构化买点判断逻辑（供信号明细页展示）。
    买点 = 硬筛全部通过 AND 结构硬闸通过 AND 得分 ≥ min_score。
    """
    detail = hydrate_detail_from_score_detail(dict(detail) if isinstance(detail, dict) else {})
    rule_a = cfg.get("yang_rule_a") or {}
    rule_b = cfg.get("yang_rule_b") or {}
    ma_period = int(cfg.get("ma_period") or 20)
    vol_need = float(cfg.get("volume_multiple") or 3.0)
    min_score = float(cfg.get("min_score") or 70)
    from .scoring import resolve_turnover_flags

    to_flags = resolve_turnover_flags(cfg)
    use_turnover = to_flags["hard_filter"]
    use_volume_ratio = bool(cfg.get("use_volume_ratio"))
    use_yang_medium = bool(cfg.get("use_yang_medium"))
    require_ma_bull = bool(cfg.get("require_ma_bull"))
    hard_gate_enabled = cfg.get("structure_rr_hard_gate_enabled") is not False
    overheat_gate_enabled = cfg.get("overheat_hard_gate_enabled") is not False
    min_turn = float(cfg.get("min_turnover") or 0) if use_turnover else None
    min_vr = float(cfg.get("min_volume_ratio") or 0) if use_volume_ratio else None
    a_w = int(rule_a.get("window") or 4)
    a_n = int(rule_a.get("min_up_days") or rule_a.get("min_yang") or 3)
    b_w = int(rule_b.get("window") or 5)
    b_n = int(rule_b.get("min_up_days") or rule_b.get("min_yang") or 4)

    close = detail.get("close")
    ma20 = detail.get("ma20")
    if detail.get("above_ma20") is not None:
        above = bool(detail.get("above_ma20"))
    elif close is not None and ma20 is not None:
        try:
            above = float(close) >= float(ma20)
        except (TypeError, ValueError):
            above = False
    else:
        above = False
    ya = int(detail.get("yang_count_4") or 0)
    yb = int(detail.get("yang_count_5") or 0)
    y10 = detail.get("yang_count_10")
    y15 = detail.get("yang_count_15")
    y20 = detail.get("yang_count_20")
    rule_a_ok = bool(detail.get("rule_a_ok")) if detail.get("rule_a_ok") is not None else (ya >= a_n)
    rule_b_ok = bool(detail.get("rule_b_ok")) if detail.get("rule_b_ok") is not None else (yb >= b_n)
    yang_ok = rule_a_ok or rule_b_ok
    yang_medium_ok = (
        bool(detail.get("yang_medium_ok"))
        if detail.get("yang_medium_ok") is not None
        else True
    )
    ma_bull_ok = bool(detail.get("ma_bull_ok")) if detail.get("ma_bull_ok") is not None else False
    ma_bear_ok = bool(detail.get("ma_bear_ok")) if detail.get("ma_bear_ok") is not None else False
    vm = detail.get("volume_multiple")
    try:
        vm_f = float(vm) if vm is not None else None
    except (TypeError, ValueError):
        vm_f = None
    volume_ok = vm_f is not None and vm_f >= vol_need
    turnover = detail.get("turnover_rate")
    volume_ratio = detail.get("volume_ratio")
    turnover_ok = True
    if use_turnover:
        try:
            turnover_ok = turnover is not None and float(turnover) >= float(min_turn)
        except (TypeError, ValueError):
            turnover_ok = False
    vr_ok = True
    if use_volume_ratio:
        try:
            vr_ok = volume_ratio is not None and float(volume_ratio) >= float(min_vr)
        except (TypeError, ValueError):
            vr_ok = False

    filter_ok = detail.get("filter_ok")
    if filter_ok is None:
        filter_ok = bool(
            above
            and yang_ok
            and volume_ok
            and turnover_ok
            and vr_ok
            and (yang_medium_ok if use_yang_medium else True)
            and (ma_bull_ok if require_ma_bull else True)
        )
    else:
        filter_ok = bool(filter_ok)
    score = float(detail.get("score") or 0)
    score_ok = bool(detail.get("score_ok")) if detail.get("score_ok") is not None else (score >= min_score)

    gate = detail.get("structure_hard_gate") or {}
    structure_gate_ok = True
    if hard_gate_enabled:
        if detail.get("structure_gate_ok") is not None:
            structure_gate_ok = bool(detail.get("structure_gate_ok"))
        elif isinstance(gate, dict) and gate.get("blocked"):
            structure_gate_ok = False

    oh_gate = detail.get("overheat_hard_gate") or {}
    overheat_gate_ok = True
    if overheat_gate_enabled:
        if detail.get("overheat_gate_ok") is not None:
            overheat_gate_ok = bool(detail.get("overheat_gate_ok"))
        elif isinstance(oh_gate, dict) and oh_gate.get("blocked"):
            overheat_gate_ok = False

    buy = (
        bool(detail.get("buy_signal"))
        if detail.get("buy_signal") is not None
        else (filter_ok and structure_gate_ok and overheat_gate_ok and score_ok)
    )

    mid_rules = cfg.get("yang_medium_rules") or []
    mid_rule_txt = "、".join(
        f"{int(r.get('window'))}日≥{int(r.get('min_up_days') or 0)}阳"
        for r in mid_rules
        if isinstance(r, dict) and r.get("window") is not None
    ) or "10日≥6阳、15日≥8阳、20日≥10阳"
    bull_periods = detail.get("ma_bull_periods") or cfg.get("ma_bull_periods") or [5, 10, 20]
    bull_label = ">".join(f"MA{p}" for p in bull_periods)
    hang_thr = cfg.get("structure_hang_min_upside_pct")
    try:
        hang_thr_pct = float(hang_thr) * 100.0 if hang_thr is not None else 8.0
    except (TypeError, ValueError):
        hang_thr_pct = 8.0
    gate_reasons = gate.get("reasons") if isinstance(gate, dict) else None
    gate_actual = (
        "通过"
        if structure_gate_ok
        else ("；".join(gate_reasons) if gate_reasons else "结构硬闸未通过")
    )

    steps = [
        {
            "id": "above_ma",
            "name": f"站上MA{ma_period}",
            "rule": f"收盘价 ≥ MA{ma_period}",
            "actual": (
                f"收盘={close}，MA{ma_period}={ma20}"
                if close is not None and ma20 is not None
                else "—"
            ),
            "pass": above,
            "required": True,
        },
        {
            "id": "yang",
            "name": "连阳确认",
            "rule": f"{a_w}日≥{a_n}阳 或 {b_w}日≥{b_n}阳",
            "actual": f"{a_w}日阳线={ya}，{b_w}日阳线={yb}",
            "pass": yang_ok,
            "required": True,
            "detail": {
                "rule_a": f"{a_w}日≥{a_n}阳 → {'通过' if rule_a_ok else '未通过'}",
                "rule_b": f"{b_w}日≥{b_n}阳 → {'通过' if rule_b_ok else '未通过'}",
            },
        },
        {
            "id": "volume_multiple",
            "name": "放量确认",
            "rule": f"当日量 / 过去均量 ≥ {vol_need}",
            "actual": f"量比倍数={vm_f if vm_f is not None else '—'}",
            "pass": volume_ok,
            "required": True,
        },
    ]
    steps.append(
        {
            "id": "yang_medium",
            "name": "中期阳线密度",
            "rule": mid_rule_txt + ("（硬筛）" if use_yang_medium else "（展示/打分，默认不硬筛）"),
            "actual": f"10日阳={y10}，15日阳={y15}，20日阳={y20}",
            "pass": yang_medium_ok if use_yang_medium else True,
            "required": use_yang_medium,
            "note": None if use_yang_medium else "未开启硬筛，本步不否决买点",
        }
    )
    steps.append(
        {
            "id": "ma_bull",
            "name": "均线多头排列",
            "rule": bull_label + ("（硬筛）" if require_ma_bull else "（展示/打分，默认不硬筛）"),
            "actual": (
                f"MA5={detail.get('ma5')}，MA10={detail.get('ma10')}，"
                f"MA20={detail.get('ma20_stack') or ma20} → "
                f"{'多头' if ma_bull_ok else ('空头' if ma_bear_ok else '非多头')}"
            ),
            "pass": ma_bull_ok if require_ma_bull else True,
            "required": require_ma_bull,
            "note": None if require_ma_bull else "未开启硬筛，本步不否决买点",
        }
    )
    if use_turnover:
        steps.append(
            {
                "id": "turnover",
                "name": "换手率下限",
                "rule": f"换手率 ≥ {min_turn}%",
                "actual": f"换手率={turnover if turnover is not None else '—'}",
                "pass": turnover_ok,
                "required": True,
            }
        )
    if use_volume_ratio:
        steps.append(
            {
                "id": "volume_ratio",
                "name": "量比下限",
                "rule": f"量比 ≥ {min_vr}",
                "actual": f"量比={volume_ratio if volume_ratio is not None else '—'}",
                "pass": vr_ok,
                "required": True,
            }
        )
    if hard_gate_enabled:
        steps.append(
            {
                "id": "structure_hard_gate",
                "name": "结构硬闸",
                "rule": (
                    f"否决：破位支撑 / 贴·超阻力 / 上行空间不足"
                    f"（相对现价<{float(cfg.get('structure_rr_min_upside_pct') or 0.03) * 100:g}%）"
                    f" / 悬空离支撑（相对支撑≥{hang_thr_pct:g}%）；RR 偏低仅提示"
                ),
                "actual": gate_actual,
                "pass": structure_gate_ok,
                "required": True,
                "note": "KDE 无效时不硬闸",
            }
        )
    if overheat_gate_enabled:
        oh_reasons = oh_gate.get("reasons") if isinstance(oh_gate, dict) else None
        ret_v = detail.get("ret_from_low_n")
        bias_v = detail.get("ma20_bias")
        lb = detail.get("overheat_lookback_days") or cfg.get("overheat_lookback_days") or 10
        hard_pct = float(cfg.get("overheat_hard_pct") or 0.25) * 100
        bias_hard = float(cfg.get("overheat_bias_hard_pct") or 0.20) * 100
        ret_txt = f"{float(ret_v) * 100:.1f}%" if ret_v is not None else "—"
        bias_txt = f"{float(bias_v) * 100:.1f}%" if bias_v is not None else "—"
        oh_actual = (
            "通过"
            if overheat_gate_ok
            else ("；".join(oh_reasons) if oh_reasons else "过热硬闸未通过")
        )
        steps.append(
            {
                "id": "overheat_hard_gate",
                "name": "近期涨幅硬闸",
                "rule": (
                    f"否决：近{lb}日相对最低价涨幅≥{hard_pct:g}%"
                    f" 或 相对MA20乖离≥{bias_hard:g}%"
                ),
                "actual": f"{oh_actual}（涨幅={ret_txt}，乖离={bias_txt}）",
                "pass": overheat_gate_ok,
                "required": True,
            }
        )
    steps.append(
        {
            "id": "min_score",
            "name": "最低得分门槛",
            "rule": f"综合得分 ≥ {min_score}",
            "actual": f"得分={score}",
            "pass": score_ok,
            "required": True,
            "note": "须在硬筛与风险硬闸通过后再判定",
        }
    )

    formula_detail = (
        f"硬筛：站上MA{ma_period} ∧ 连阳({a_w}≥{a_n}∨{b_w}≥{b_n}) ∧ 放量≥{vol_need}"
        + (f" ∧ 中期阳线({mid_rule_txt})" if use_yang_medium else "")
        + (f" ∧ 多头({bull_label})" if require_ma_bull else "")
        + (f" ∧ 换手≥{min_turn}" if use_turnover else "")
        + (f" ∧ 量比≥{min_vr}" if use_volume_ratio else "")
        + (" ∧ 结构硬闸" if hard_gate_enabled else "")
        + (" ∧ 过热硬闸" if overheat_gate_enabled else "")
        + f"；再要求得分≥{min_score}"
    )

    return {
        "formula": "买点 = 硬筛全部通过 AND 结构硬闸通过 AND 过热硬闸通过 AND 得分≥最低得分",
        "formula_detail": formula_detail,
        "min_score": min_score,
        "score": score,
        "filter_ok": filter_ok,
        "structure_gate_ok": structure_gate_ok,
        "overheat_gate_ok": overheat_gate_ok,
        "score_ok": score_ok,
        "buy_signal": buy,
        "filter_reason": detail.get("filter_reason") or "",
        "steps": steps,
    }


def evaluate_buy_signal(
    bars_desc: list,
    cfg: Dict[str, Any],
    *,
    require_pass: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    对截至最新日的 DESC K 线判定 URT 买点。
    require_pass=True：仅硬筛+结构硬闸+得分通过才返回；False：始终返回指标与得分明细（供明细页）。
    KDE 支撑/阻力参与混合结构硬闸；RR 偏低仅软标签（另计入位置与 RR 分项）。
    """
    ind = build_indicators(bars_desc, cfg)
    if not ind:
        return None
    ok, reason = hard_filter_pass(ind, cfg)
    # 全市场扫描：硬筛失败则跳过 KDE/打分（KDE 是主要耗时）
    if require_pass and not ok:
        return None

    yang_rule = "4d3" if ind.get("rule_a_ok") else "5d4"
    if ind.get("rule_a_ok") and ind.get("rule_b_ok"):
        yang_rule = "4d3+5d4"
    elif not ind.get("rule_a_ok") and not ind.get("rule_b_ok"):
        yang_rule = "none"

    structure = _compute_structure_levels(bars_desc, cfg, price=ind.get("close"))
    from .risk_tags import (
        build_overheat_risk_tags,
        build_trend_risk_tags,
        build_turnover_risk_tags,
        enrich_structure_with_rr,
        evaluate_overheat_hard_gate,
    )

    enriched = enrich_structure_with_rr(structure, price=ind.get("close"), cfg=cfg)
    structure = enriched["structure"]
    risk_tags = list(enriched.get("risk_tags") or [])
    risk_tags.extend(build_trend_risk_tags(ind))
    risk_tags.extend(build_overheat_risk_tags(ind, cfg))

    # 打分前注入结构字段（位置/RR 分项）
    ind = dict(ind)
    ind["nearest_support"] = structure.get("nearest_support")
    ind["nearest_resistance"] = structure.get("nearest_resistance")
    ind["structure_rr"] = structure.get("rr")
    ind["kde_ok"] = structure.get("kde_ok")

    score, score_detail = compute_score_breakdown(ind, cfg)
    min_score = float(cfg.get("min_score") or 70)
    score_ok = score >= min_score

    to_part = (score_detail.get("parts") or {}).get("turnover") if isinstance(score_detail, dict) else None
    risk_tags.extend(build_turnover_risk_tags(ind, cfg, turnover_part=to_part))
    hard_gate = enriched.get("structure_hard_gate") or {}
    structure_gate_ok = not bool(hard_gate.get("blocked"))
    overheat_gate = evaluate_overheat_hard_gate(ind, cfg)
    overheat_gate_ok = not bool(overheat_gate.get("blocked"))
    buy = bool(ok and structure_gate_ok and overheat_gate_ok and score_ok)

    if require_pass and not buy:
        return None

    # 持久化进 score_detail，预计算重读无需改表
    if isinstance(score_detail, dict):
        score_detail = dict(score_detail)
        score_detail["structure"] = {
            "support_levels": structure.get("support_levels") or [],
            "resistance_levels": structure.get("resistance_levels") or [],
            "nearest_support": structure.get("nearest_support"),
            "nearest_resistance": structure.get("nearest_resistance"),
            "kde_nearest_support": structure.get("kde_nearest_support"),
            "kde_nearest_resistance": structure.get("kde_nearest_resistance"),
            "kde_ok": structure.get("kde_ok"),
            "kde_reason": structure.get("kde_reason"),
            "kde_bw": structure.get("kde_bw"),
            "kde_lookback_used": structure.get("kde_lookback_used"),
            "kde_lookback_expanded": structure.get("kde_lookback_expanded"),
            "kde_window_mode": structure.get("kde_window_mode"),
            "kde_anchor": structure.get("kde_anchor"),
            "kde_multi_windows": structure.get("kde_multi_windows"),
            "method": structure.get("method") or "structural_kde+confluence",
            "structure_level_source": structure.get("structure_level_source"),
            "confluence_ok": structure.get("confluence_ok"),
            "nearest_confluence_support": structure.get("nearest_confluence_support"),
            "nearest_confluence_resistance": structure.get("nearest_confluence_resistance"),
            "confluence_zones": structure.get("confluence_zones"),
            "rr": structure.get("rr"),
            "rr_reason": structure.get("rr_reason"),
            "rr_downside_floored": structure.get("rr_downside_floored"),
            "rr_min_downside_pct": structure.get("rr_min_downside_pct"),
            "rr_downside_raw": structure.get("rr_downside_raw"),
            "rr_downside": structure.get("rr_downside"),
            "hanging": structure.get("hanging"),
            "hang_distance_pct": structure.get("hang_distance_pct"),
        }
        score_detail["risk_tags"] = risk_tags
        score_detail["structure_hard_gate"] = hard_gate
        score_detail["overheat_hard_gate"] = overheat_gate
        score_detail["ret_from_low_n"] = ind.get("ret_from_low_n")
        score_detail["ma20_bias"] = ind.get("ma20_bias")
        score_detail["overheat_lookback_days"] = ind.get("overheat_lookback_days")

    from backend_core.analysis.trade_advice import build_trade_advice

    ref_levels = None
    if structure.get("confluence_zones"):
        ref_levels = {
            "confluence_zones": structure.get("confluence_zones"),
            "nearest_confluence_support": structure.get("nearest_confluence_support"),
            "nearest_confluence_resistance": structure.get("nearest_confluence_resistance"),
            "atr": None,
            "last_close": ind.get("close"),
        }
    advice_row = {
        "buy_signal": buy,
        "close": ind.get("close"),
        "ma20": ind.get("ma20"),
        "nearest_support": structure.get("nearest_support"),
        "nearest_resistance": structure.get("nearest_resistance"),
        "structure": structure,
        "structure_rr": structure.get("rr"),
        "risk_tags": risk_tags,
    }
    trade_advice = build_trade_advice("urt", advice_row, reference_levels=ref_levels)
    if isinstance(score_detail, dict):
        score_detail["trade_advice"] = trade_advice

    payload = {
        "signal_date": ind.get("date"),
        "close": ind.get("close"),
        "open": ind.get("open"),
        "ma20": ind.get("ma20"),
        "above_ma20": ind.get("above_ma20"),
        "ma5": ind.get("ma5"),
        "ma10": ind.get("ma10"),
        "ma20_stack": ind.get("ma20_stack"),
        "ma_bull_ok": ind.get("ma_bull_ok"),
        "ma_bear_ok": ind.get("ma_bear_ok"),
        "ma_bull_periods": ind.get("ma_bull_periods"),
        "ma_bull_values": ind.get("ma_bull_values"),
        "ma_bull_score_periods": ind.get("ma_bull_score_periods"),
        "ma_bull_score_values": ind.get("ma_bull_score_values"),
        "ma_bull_depth": ind.get("ma_bull_depth"),
        "yang_count_4": ind.get("yang_count_4"),
        "yang_count_5": ind.get("yang_count_5"),
        "yang_count_10": ind.get("yang_count_10"),
        "yang_count_15": ind.get("yang_count_15"),
        "yang_count_20": ind.get("yang_count_20"),
        "yang_medium_ok": ind.get("yang_medium_ok"),
        "yang_medium_detail": ind.get("yang_medium_detail"),
        "yang_rule": yang_rule,
        "rule_a_ok": ind.get("rule_a_ok"),
        "rule_b_ok": ind.get("rule_b_ok"),
        "avg_volume_20": ind.get("avg_volume_20"),
        "volume": ind.get("volume"),
        "volume_multiple": ind.get("volume_multiple"),
        "volume_ratio": ind.get("volume_ratio"),
        "turnover_rate": ind.get("turnover_rate"),
        "turnover_median_n": ind.get("turnover_median_n"),
        "turnover_lookback": ind.get("turnover_lookback"),
        "score": score,
        "signal_strength": score,
        "score_detail": score_detail,
        "buy_signal": buy,
        "filter_ok": ok,
        "filter_reason": reason,
        "structure_gate_ok": structure_gate_ok,
        "structure_hard_gate": hard_gate,
        "overheat_gate_ok": overheat_gate_ok,
        "overheat_hard_gate": overheat_gate,
        "ret_from_low_n": ind.get("ret_from_low_n"),
        "ma20_bias": ind.get("ma20_bias"),
        "overheat_lookback_days": ind.get("overheat_lookback_days"),
        "low_n": ind.get("low_n"),
        "score_ok": score_ok,
        "support_levels": structure["support_levels"],
        "resistance_levels": structure["resistance_levels"],
        "nearest_support": structure["nearest_support"],
        "nearest_resistance": structure["nearest_resistance"],
        "kde_ok": structure["kde_ok"],
        "kde_reason": structure["kde_reason"],
        "kde_lookback_used": structure["kde_lookback_used"],
        "kde_lookback_expanded": structure["kde_lookback_expanded"],
        "trade_advice": trade_advice,
        "structure_rr": structure.get("rr"),
        "structure_rr_reason": structure.get("rr_reason"),
        "structure_rr_downside_floored": structure.get("rr_downside_floored"),
        "structure_rr_min_downside_pct": structure.get("rr_min_downside_pct"),
        "hanging": structure.get("hanging"),
        "hang_distance_pct": structure.get("hang_distance_pct"),
        "risk_tags": risk_tags,
    }
    payload["buy_logic"] = build_buy_logic(payload, cfg)
    return payload


def extract_signal_structure_levels(sig: Dict[str, Any]) -> Dict[str, Any]:
    """从买点行 / score_detail.structure 取信号日关键支撑阻力。"""
    sd = sig.get("score_detail") if isinstance(sig.get("score_detail"), dict) else {}
    st = sd.get("structure") if isinstance(sd.get("structure"), dict) else {}
    ns = sig.get("nearest_support")
    if ns is None:
        ns = st.get("nearest_support")
    nr = sig.get("nearest_resistance")
    if nr is None:
        nr = st.get("nearest_resistance")
    rr = sig.get("structure_rr")
    if rr is None:
        rr = st.get("rr")
    kde_ok = sig.get("kde_ok") if sig.get("kde_ok") is not None else st.get("kde_ok")
    kde_reason = sig.get("kde_reason") if sig.get("kde_reason") is not None else st.get("kde_reason")
    return {
        "nearest_support": ns,
        "nearest_resistance": nr,
        "structure_rr": rr,
        "kde_ok": kde_ok,
        "kde_reason": kde_reason,
        "structure_level_source": (
            sig.get("structure_level_source")
            if sig.get("structure_level_source") is not None
            else st.get("structure_level_source")
        ),
        "confluence_ok": (
            sig.get("confluence_ok") if sig.get("confluence_ok") is not None else st.get("confluence_ok")
        ),
    }


def compute_weak_structure_levels(
    bars_desc: List[Dict[str, Any]],
    *,
    price: float,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    KDE 缺失时的弱结构兜底（P2）：
    - 支撑：近窗最低价（排除信号日），若不低于现价则尝试 MA20
    - 阻力：近窗最高价中高于现价的最近一侧
    """
    cfg = cfg or {}
    out: Dict[str, Any] = {
        "nearest_support": None,
        "nearest_resistance": None,
        "structure_source": None,
        "ok": False,
    }
    try:
        px = float(price)
    except (TypeError, ValueError):
        return out
    if px <= 0 or not bars_desc:
        return out
    try:
        lb = int(cfg.get("structure_weak_lookback") or 20)
    except (TypeError, ValueError):
        lb = 20
    lb = max(5, lb)
    # DESC → 取含信号日的一段，再转 ASC
    window = list(reversed(bars_desc[: lb + 1]))
    if len(window) < 5:
        return out

    def _f(bar: Dict[str, Any], key: str) -> Optional[float]:
        v = bar.get(key)
        if v is None and key in ("low", "high"):
            v = bar.get("close")
        try:
            x = float(v)
            return x if x > 0 else None
        except (TypeError, ValueError):
            return None

    # 支撑/阻力用信号日前的历史（去掉末日）
    hist = window[:-1] if len(window) > 1 else window
    lows = [x for x in (_f(b, "low") for b in hist) if x is not None]
    highs = [x for x in (_f(b, "high") for b in hist) if x is not None]
    closes = [x for x in (_f(b, "close") for b in window) if x is not None]

    support = None
    source = None
    if lows:
        swing_low = min(lows)
        if swing_low < px:
            support = round(swing_low, 4)
            source = "weak_swing"
    if support is None and len(closes) >= 20:
        ma20 = sum(closes[-20:]) / 20.0
        if 0 < ma20 < px:
            support = round(ma20, 4)
            source = "weak_ma20"

    resist = None
    above = [h for h in highs if h > px * 1.005]
    if above:
        resist = round(min(above), 4)

    out["nearest_support"] = support
    out["nearest_resistance"] = resist
    out["structure_source"] = source
    out["ok"] = support is not None
    return out


def resolve_structure_exit_levels(
    *,
    entry_price: float,
    nearest_support: Any = None,
    nearest_resistance: Any = None,
    cfg: Optional[Dict[str, Any]] = None,
    target_pct: float = 0.10,
    structure_source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    结构出场价位：
    - 止损：支撑 × (1 - structure_stop_buffer_pct)；无支撑则回退百分比止损
    - 止盈：阻力（上行空间足够）否则 entry×(1+target_pct)
    - P3：回退止损可用 structure_fallback_stop_loss_pct（默认 8）替代 risk 上限
    """
    cfg = cfg or {}
    risk = cfg.get("risk") if isinstance(cfg.get("risk"), dict) else {}
    try:
        buf = float(cfg.get("structure_stop_buffer_pct"))
    except (TypeError, ValueError):
        buf = 0.02
    if buf < 0:
        buf = 0.0
    # 出场专用阻力上行门槛（默认 5%）；未配置时回退选股口径再回退 5%
    min_up = None
    for key, default in (
        ("structure_exit_min_upside_pct", None),
        ("structure_rr_min_upside_pct", None),
    ):
        try:
            raw = cfg.get(key)
            if raw is not None:
                min_up = float(raw)
                break
        except (TypeError, ValueError):
            continue
    if min_up is None:
        min_up = 0.05
    try:
        stop_max = float(risk.get("stop_loss_pct_max") or 10)
    except (TypeError, ValueError):
        stop_max = 10.0
    # P3：结构缺失回退时可用更紧的止损（百分比）
    try:
        fb_stop = cfg.get("structure_fallback_stop_loss_pct")
        fallback_stop_max = float(fb_stop) if fb_stop is not None else min(stop_max, 8.0)
    except (TypeError, ValueError):
        fallback_stop_max = min(stop_max, 8.0)
    if fallback_stop_max <= 0:
        fallback_stop_max = stop_max

    entry = float(entry_price)
    src = str(structure_source or "").strip() or None
    out: Dict[str, Any] = {
        "stop_price": None,
        "target_price": None,
        "stop_basis": None,
        "target_basis": None,
        "structure_fallback": False,
        "fallback_reason": None,
        "structure_source": src,
        "nearest_support": None,
        "nearest_resistance": None,
        "buffer_pct": buf,
        "fallback_stop_loss_pct": fallback_stop_max,
    }
    if entry <= 0:
        return out

    support = None
    try:
        if nearest_support is not None:
            support = float(nearest_support)
    except (TypeError, ValueError):
        support = None
    resist = None
    try:
        if nearest_resistance is not None:
            resist = float(nearest_resistance)
    except (TypeError, ValueError):
        resist = None

    out["nearest_support"] = support
    out["nearest_resistance"] = resist
    if support is not None and not src:
        out["structure_source"] = "kde"

    if support is not None and support > 0:
        stop_px = round(support * (1.0 - buf), 4)
        # 止损须严格低于入场，否则回退百分比
        if stop_px < entry:
            out["stop_price"] = stop_px
            out["stop_basis"] = (
                "weak_structure_support" if str(out.get("structure_source") or "").startswith("weak_") else "structure_support"
            )
            out["structure_fallback"] = False
            out["fallback_reason"] = None
        else:
            out["stop_price"] = round(entry * (1.0 - fallback_stop_max / 100.0), 4)
            out["stop_basis"] = "pct_fallback_stop_above_entry"
            out["structure_fallback"] = True
            out["fallback_reason"] = "stop_above_entry"
    else:
        out["stop_price"] = round(entry * (1.0 - fallback_stop_max / 100.0), 4)
        out["stop_basis"] = "pct_fallback_no_support"
        out["structure_fallback"] = True
        out["fallback_reason"] = "no_support"

    pct_target = round(entry * (1.0 + float(target_pct)), 4)
    if resist is not None and resist > entry * (1.0 + min_up):
        out["target_price"] = round(resist, 4)
        out["target_basis"] = (
            "weak_structure_resistance"
            if str(out.get("structure_source") or "").startswith("weak_")
            else "structure_resistance"
        )
    else:
        out["target_price"] = pct_target
        out["target_basis"] = "pct_target" if resist is None else "pct_target_low_upside"

    return out


def step_structure_fallback_protection(
    *,
    entry_price: float,
    peak_high: float,
    last_close: float,
    stop_price: Optional[float],
    armed: bool,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    全路径浮盈保护（原 P1，已扩展出回退路径）：
    浮盈达 arm_pct（默认约 +6.5%）后抬止损至 max(原止损, 入场价, 峰值×(1-trail))。
    兼容旧键 structure_fallback_*；优先读 structure_protect_*。
    """
    cfg = cfg or {}
    enabled = cfg.get("structure_protect_enabled")
    if enabled is None:
        enabled = cfg.get("structure_fallback_protect_enabled")
    if enabled is None:
        enabled = True

    def _pct(primary: str, legacy: str, default: float) -> float:
        for key in (primary, legacy):
            try:
                raw = cfg.get(key)
                if raw is not None:
                    return float(raw)
            except (TypeError, ValueError):
                continue
        return default

    arm_pct = _pct("structure_protect_arm_pct", "structure_fallback_arm_pct", 0.065)
    trail = _pct(
        "structure_protect_trail_drawdown_pct",
        "structure_fallback_trail_drawdown_pct",
        0.04,
    )
    if trail < 0:
        trail = 0.0

    entry = float(entry_price)
    peak = float(peak_high) if peak_high is not None else entry
    cl = float(last_close)
    try:
        cur_stop = float(stop_price) if stop_price is not None else entry * 0.9
    except (TypeError, ValueError):
        cur_stop = entry * 0.9

    if not enabled or entry <= 0:
        return {
            "armed": bool(armed),
            "stop_price": cur_stop,
            "exit_reason": None,
            "protect_basis": None,
        }

    peak_gain = peak / entry - 1.0 if entry else 0.0
    new_armed = bool(armed) or peak_gain >= arm_pct
    new_stop = cur_stop
    protect_basis = None
    if new_armed:
        be_stop = entry
        trail_stop = peak * (1.0 - trail) if peak > 0 else entry
        new_stop = max(cur_stop, be_stop, trail_stop)
        protect_basis = "fallback_trail" if trail_stop >= be_stop else "breakeven"

    exit_reason = None
    if new_armed and cl <= new_stop:
        # 触及抬升后的止损：区分保本 / 回撤
        if cl >= entry * 0.999 or new_stop >= entry * 0.999:
            exit_reason = "fallback_trail" if (peak * (1.0 - trail)) >= entry else "breakeven_stop"
        else:
            exit_reason = "price_stop"

    return {
        "armed": new_armed,
        "stop_price": round(new_stop, 4),
        "exit_reason": exit_reason,
        "protect_basis": protect_basis,
    }


# 别名：全路径保护
step_structure_protect = step_structure_fallback_protection


def evaluate_structure_exit_rules(
    *,
    entry_price: float,
    last_close: float,
    last_high: Optional[float] = None,
    stop_price: Optional[float] = None,
    target_price: Optional[float] = None,
    target_basis: Optional[str] = None,
    stop_basis: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    结构出场判定（持仓第 2 根 K 起逐日调用）：
    - 收盘 ≤ 止损 → structure_stop（百分比回退则为 price_stop；弱结构为 structure_stop）
    - 最高价 ≥ 止盈 → structure_target / pct_target
    同日优先止损。
    """
    if entry_price <= 0:
        return None
    cl = float(last_close)
    hi = float(last_high) if last_high is not None else cl
    pnl_pct = (cl - entry_price) / entry_price * 100.0
    sb = str(stop_basis or "")

    if stop_price is not None:
        try:
            sp = float(stop_price)
        except (TypeError, ValueError):
            sp = None
        if sp is not None and cl <= sp:
            if sb.startswith("pct_fallback"):
                reason = "price_stop"
            elif sb in ("breakeven", "fallback_trail"):
                reason = "breakeven_stop" if sb == "breakeven" else "fallback_trail"
            else:
                reason = "structure_stop"
            return {
                "exit_reason": reason,
                "pnl_pct": round(pnl_pct, 2),
                "stop_price": sp,
            }

    if target_price is not None:
        try:
            tp = float(target_price)
        except (TypeError, ValueError):
            tp = None
        if tp is not None and hi >= tp:
            tb = str(target_basis or "")
            if tb.startswith("pct_target"):
                reason = "pct_target"
            elif "weak_" in tb:
                reason = "structure_target"
            else:
                reason = "structure_target"
            return {
                "exit_reason": reason,
                "pnl_pct": round(pnl_pct, 2),
                "target_price": tp,
            }
    return None


def evaluate_exit_rules(
    *,
    entry_price: float,
    closes: list,
    peak_price: float,
    cfg: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    卖出纪律（供回测）：
    - 价格止损：亏损达 stop_loss_pct
    - 时间止损：连续下跌 N 日，且浮亏 ≥ time_stop_min_loss_pct（默认 4%）
    - 回撤止盈：涨幅达警惕区（默认 8%）后，自高点回撤 trailing_drawdown_pct
    closes: 持仓以来收盘价序列（时间正序，含最新）。
    """
    risk = cfg.get("risk") or {}
    if entry_price <= 0 or not closes:
        return None
    last = float(closes[-1])
    pnl_pct = (last - entry_price) / entry_price * 100.0

    stop_max = float(risk.get("stop_loss_pct_max") or 10)
    if pnl_pct <= -stop_max:
        return {"exit_reason": "price_stop", "pnl_pct": round(pnl_pct, 2)}

    down_days = int(risk.get("time_stop_down_days") or 3)
    try:
        min_loss = float(risk.get("time_stop_min_loss_pct") if risk.get("time_stop_min_loss_pct") is not None else 4.0)
    except (TypeError, ValueError):
        min_loss = 4.0
    if len(closes) >= down_days + 1:
        streak = 0
        for i in range(len(closes) - 1, 0, -1):
            if float(closes[i]) < float(closes[i - 1]):
                streak += 1
            else:
                break
        if streak >= down_days and (min_loss <= 0 or pnl_pct <= -min_loss):
            return {"exit_reason": "time_stop", "pnl_pct": round(pnl_pct, 2), "down_days": streak}

    alert_min = float(risk.get("take_profit_alert_pct_min") or 8)
    trail = float(risk.get("trailing_drawdown_pct") or 5)
    peak = max(float(peak_price), max(float(c) for c in closes))
    gain_from_entry = (peak - entry_price) / entry_price * 100.0
    if gain_from_entry >= alert_min and peak > 0:
        dd = (peak - last) / peak * 100.0
        if dd >= trail:
            return {
                "exit_reason": "trailing_take_profit",
                "pnl_pct": round(pnl_pct, 2),
                "peak_drawdown_pct": round(dd, 2),
            }
    return None
