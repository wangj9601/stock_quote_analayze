# -*- coding: utf-8 -*-
"""LDS：带动性三维、身份分、右侧 watch_ready（纯函数，可单测）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _cfg_section(cfg: Optional[Dict[str, Any]], key: str) -> Dict[str, Any]:
    return dict((cfg or {}).get(key) or {})


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def score_follow(
    zt_n: int,
    up_ratio: float,
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    d = _cfg_section(cfg, "drive") if cfg and "drive" in (cfg or {}) else dict(cfg or {})
    zt_full = max(1, int(d.get("follow_zt_full") or 3))
    up_full = float(d.get("follow_up_ratio_full") if d.get("follow_up_ratio_full") is not None else 0.60)
    zt_part = _clamp(100.0 * float(zt_n) / float(zt_full))
    up_part = _clamp(100.0 * float(up_ratio) / max(up_full, 1e-6))
    return round(max(zt_part, up_part), 2)


def score_sync(
    stock_chg: float,
    board_median_chg: Optional[float],
    *,
    had_bomb_weak_board: bool = False,
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    """个股与板中位同步；炸板后板未走弱则扣分。"""
    if board_median_chg is None:
        return 50.0
    bm = float(board_median_chg)
    sc = float(stock_chg)
    if sc > 0 and bm > 0:
        base = 70.0 + min(30.0, bm * 5.0)
    elif sc > 5 and bm <= 0:
        base = 15.0
    elif sc > 0 and bm <= 0:
        base = 35.0
    elif sc <= 0 and bm > 0:
        base = 40.0
    else:
        base = 45.0
    if had_bomb_weak_board:
        base -= 35.0
    return round(_clamp(base), 2)


def score_role_component(board_role_score: Optional[float], market_leader_score: Optional[float] = None) -> float:
    if board_role_score is not None:
        return round(_clamp(float(board_role_score)), 2)
    if market_leader_score is not None:
        # market_leader 原始分常 >100，压缩到 0～100
        return round(_clamp(float(market_leader_score) / 6.0), 2)
    return 40.0


def score_drive(
    follow_a: float,
    sync_b: float,
    role_c: float,
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    d = _cfg_section(cfg, "drive") if cfg and "drive" in (cfg or {}) else dict(cfg or {})
    wa = float(d.get("w_follow") if d.get("w_follow") is not None else 0.40)
    wb = float(d.get("w_sync") if d.get("w_sync") is not None else 0.35)
    wc = float(d.get("w_role") if d.get("w_role") is not None else 0.25)
    return round(_clamp(wa * follow_a + wb * sync_b + wc * role_c), 2)


def score_recog(
    *,
    height_pctile: float = 50.0,
    seal_yi: float = 0.0,
    change_percent: float = 0.0,
) -> float:
    seal_part = _clamp(float(seal_yi) * 8.0)
    chg_part = _clamp(abs(float(change_percent)) * 5.0)
    return round(_clamp(0.55 * float(height_pctile) + 0.25 * seal_part + 0.20 * chg_part), 2)


def score_liquidity(*, amount_pctile: float = 50.0, mv_yi: float = 0.0) -> float:
    mv_bonus = 10.0 if float(mv_yi) >= 50 else (5.0 if float(mv_yi) >= 30 else 0.0)
    return round(_clamp(0.9 * float(amount_pctile) + mv_bonus), 2)


def score_identity(
    recog: float,
    drive: float,
    liq: float,
    cfg: Optional[Dict[str, Any]] = None,
) -> float:
    ident = _cfg_section(cfg, "identity") if cfg and "identity" in (cfg or {}) else dict(cfg or {})
    wr = float(ident.get("w_recog") if ident.get("w_recog") is not None else 0.35)
    wd = float(ident.get("w_drive") if ident.get("w_drive") is not None else 0.45)
    wl = float(ident.get("w_liq") if ident.get("w_liq") is not None else 0.20)
    return round(_clamp(wr * recog + wd * drive + wl * liq), 2)


def evaluate_watch_ready(cand: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None) -> tuple[bool, List[str]]:
    watch = _cfg_section(cfg, "watch")
    reasons: List[str] = []
    checks: List[bool] = []

    if bool(watch.get("enable_diverge", True)):
        ok = bool(cand.get("had_diverge"))
        checks.append(ok)
        reasons.append("分歧确认" if ok else "缺情绪分歧")
    if bool(watch.get("enable_inflow", True)):
        net = cand.get("net_inflow_yi")
        vol_r = _f(cand.get("vol_ratio_actual"), 0.0)
        need = float(watch.get("vol_ratio") if watch.get("vol_ratio") is not None else 1.5)
        ok = (net is not None and float(net) > 0) or vol_r >= need
        checks.append(ok)
        reasons.append("资金承接" if ok else "资金承接不足")
    if bool(watch.get("enable_mainline", True)):
        ok = bool(cand.get("on_mainline"))
        checks.append(ok)
        reasons.append("主线仍在" if ok else "脱离主线")

    if not checks:
        return True, ["右侧条件未启用"]
    return all(checks), reasons


def evaluate_candidate(
    cand: Dict[str, Any],
    *,
    cfg: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """对单条候选打分；不通过身份/孤板返回 None。"""
    full = cfg or {}
    identity_cfg = _cfg_section(full, "identity")

    min_mv = float(identity_cfg.get("min_mv_yi") if identity_cfg.get("min_mv_yi") is not None else 30.0)
    if _f(cand.get("mv_yi"), 0.0) < min_mv:
        return None

    drive_sec = _cfg_section(full, "drive")
    follow_a = score_follow(
        int(cand.get("zt_n") or 0),
        _f(cand.get("up_ratio"), 0.0),
        drive_sec or full,
    )
    sync_b = score_sync(
        _f(cand.get("change_percent"), 0.0),
        cand.get("board_median_chg"),
        had_bomb_weak_board=bool(cand.get("had_bomb_weak_board")),
        cfg=_cfg_section(full, "drive") or full,
    )
    role_c = score_role_component(
        cand.get("board_role_score"),
        cand.get("market_leader_score"),
    )
    drive = score_drive(follow_a, sync_b, role_c, full)

    lonely_min = float(identity_cfg.get("lonely_min") if identity_cfg.get("lonely_min") is not None else 35.0)
    if drive < lonely_min:
        return None

    recog = score_recog(
        height_pctile=_f(cand.get("height_pctile"), 50.0),
        seal_yi=_f(cand.get("seal_yi"), 0.0),
        change_percent=_f(cand.get("change_percent"), 0.0),
    )
    liq = score_liquidity(
        amount_pctile=_f(cand.get("amount_pctile"), 50.0),
        mv_yi=_f(cand.get("mv_yi"), 0.0),
    )
    identity = score_identity(recog, drive, liq, full)
    identity_min = float(identity_cfg.get("identity_min") if identity_cfg.get("identity_min") is not None else 55.0)
    if identity < identity_min:
        return None

    watch_ok, watch_reasons = evaluate_watch_ready(cand, full)
    identity_reasons = [
        f"带动 {drive:.0f}（跟风{follow_a:.0f}/同步{sync_b:.0f}/角色{role_c:.0f}）",
        f"辨识 {recog:.0f}",
        f"流动性 {liq:.0f}",
    ]
    if cand.get("is_height_stock"):
        identity_reasons.append("当日最高板（非硬门槛）")

    return {
        "status": "hit",
        "code": str(cand.get("code") or ""),
        "name": str(cand.get("name") or cand.get("code") or ""),
        "role": str(cand.get("role") or "board_leader"),
        "board_code": str(cand.get("board_code") or ""),
        "board_name": str(cand.get("board_name") or ""),
        "identity_score": identity,
        "drive_score": drive,
        "watch_ready": bool(watch_ok),
        "is_lonely": False,
        "is_primary": bool(cand.get("is_primary", True)),
        "same_as_height": bool(cand.get("is_height_stock")),
        "board_count": cand.get("board_count"),
        "identity_reasons": identity_reasons,
        "watch_reasons": watch_reasons,
        "detail": {
            "follow_a": follow_a,
            "sync_b": sync_b,
            "role_c": role_c,
            "recog": recog,
            "liq": liq,
            "zt_n": cand.get("zt_n"),
            "up_ratio": cand.get("up_ratio"),
            "board_median_chg": cand.get("board_median_chg"),
        },
    }


def _primary_rank(row: Dict[str, Any]) -> tuple:
    """排序键：总龙优先，再身份分、带动分。"""
    role_rank = 0 if str(row.get("role") or "") == "market_leader" else 1
    return (
        role_rank,
        -_f(row.get("identity_score"), 0.0),
        -_f(row.get("drive_score"), 0.0),
        -int(bool(row.get("watch_ready"))),
    )


def merge_hits_by_code(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """试算/展示按 code 合并：一行一只票，多板汇总到 board_name / detail.boards。"""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        code = str(r.get("code") or "").strip()
        if not code:
            continue
        if code not in groups:
            groups[code] = []
            order.append(code)
        groups[code].append(dict(r))

    merged: List[Dict[str, Any]] = []
    for code in order:
        group = groups[code]
        group.sort(key=_primary_rank)
        primary = dict(group[0])
        boards: List[Dict[str, Any]] = []
        names: List[str] = []
        seen_board: set = set()
        watch_ok = False
        same_height = False
        roles = set()
        for g in group:
            roles.add(str(g.get("role") or ""))
            if g.get("watch_ready"):
                watch_ok = True
            if g.get("same_as_height"):
                same_height = True
            bcode = str(g.get("board_code") or "").strip()
            bname = str(g.get("board_name") or "").strip()
            key = bcode or bname
            if key and key not in seen_board:
                seen_board.add(key)
                boards.append(
                    {
                        "board_code": bcode,
                        "board_name": bname,
                        "role": g.get("role"),
                        "identity_score": g.get("identity_score"),
                        "drive_score": g.get("drive_score"),
                    }
                )
                if bname:
                    names.append(bname)

        primary["watch_ready"] = watch_ok
        primary["same_as_height"] = same_height
        if "market_leader" in roles:
            primary["role"] = "market_leader"
            # 总龙兼板龙时 board_code 置空，板块名保留汇总
            primary["board_code"] = ""
        elif boards:
            primary["board_code"] = str(boards[0].get("board_code") or "")
        if names:
            # 主展示：第一块为最高分对应板，其余追加
            primary_name = str(primary.get("board_name") or "").strip()
            rest = [n for n in names if n != primary_name]
            if primary_name:
                label = primary_name + ("（主）" if rest else "")
                if rest:
                    label = label + " · " + " · ".join(rest)
                primary["board_name"] = label
            else:
                primary["board_name"] = " · ".join(names)
        detail = dict(primary.get("detail") or {})
        detail["boards"] = boards
        detail["merged_from"] = len(group)
        if "market_leader" in roles and "board_leader" in roles:
            detail["role_note"] = "总龙兼板龙"
        primary["detail"] = detail
        merged.append(primary)

    merged.sort(key=_primary_rank)
    return merged
