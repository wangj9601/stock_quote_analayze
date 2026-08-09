# -*- coding: utf-8 -*-
"""板块多策略信号聚合：行业/概念板 × GMS/URT/SBBR/RPE + 买卖建议。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.analysis.classic_levels import (
    OHLC_LOOKBACK,
    attach_reference_levels_batch,
)
from backend_core.analysis.trade_advice import build_trade_advice

logger = logging.getLogger(__name__)

STRATEGY_KEYS = ("gms", "urt", "sbbr", "rpe")


def _norm_code(c: Any) -> str:
    return str(c or "").strip()


def load_board_member_codes(
    db: Session,
    *,
    board_kind: str,
    board_code: str,
) -> Tuple[List[str], Dict[str, str]]:
    """返回 (codes, {code: name})。"""
    from backend_core.strategies.rpe.data_loader import RPEDataLoader

    kind = "concept" if (board_kind or "").strip().lower() == "concept" else "industry"
    members = RPEDataLoader(db).load_board_members(board_code, board_kind=kind) or []
    codes: List[str] = []
    names: Dict[str, str] = {}
    for m in members:
        code = _norm_code(m.get("code") or m.get("stock_code"))
        if not code:
            continue
        codes.append(code)
        names[code] = str(m.get("name") or m.get("stock_name") or "")
    return codes, names


def batch_load_ohlc_bars(
    db: Session,
    codes: Sequence[str],
    *,
    lookback: int = OHLC_LOOKBACK,
) -> Dict[str, List[Dict[str, Any]]]:
    """批量取 A 股日线近 lookback 根 high/low/close/volume（按 code 截断）。"""
    codes = [_norm_code(c) for c in codes if _norm_code(c)]
    if not codes:
        return {}
    # 多取余量再截断
    fetch_n = max(int(lookback) * 2, int(lookback) + 10)
    try:
        sql = text(
            """
            SELECT code, trade_date, high, low, close, volume
            FROM (
                SELECT code,
                       date AS trade_date,
                       high, low, close, volume,
                       ROW_NUMBER() OVER (PARTITION BY code ORDER BY date DESC) AS rn
                FROM historical_quotes
                WHERE code IN :codes
                  AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
            ) t
            WHERE rn <= :lim
            ORDER BY code, trade_date
            """
        ).bindparams(bindparam("codes", expanding=True))
        rows = db.execute(sql, {"codes": codes, "lim": fetch_n}).fetchall()
    except Exception as e:
        logger.warning("batch_load_ohlc_bars failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {}

    by: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        code = _norm_code(r[0])
        d = r[1]
        if hasattr(d, "strftime"):
            ds = d.strftime("%Y-%m-%d")
        else:
            ds = str(d)[:10]
        by.setdefault(code, []).append(
            {
                "date": ds,
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5] if len(r) > 5 else None,
            }
        )
    # 已按 date ASC；保留末 lookback
    out: Dict[str, List[Dict[str, Any]]] = {}
    for code, bars in by.items():
        out[code] = bars[-int(lookback) :] if len(bars) > lookback else bars
    return out


def _filter_gms(
    items: List[Dict[str, Any]],
    *,
    min_score: float = 0.0,
) -> List[Dict[str, Any]]:
    """左/右买点，或总分 ≥ min_score（与选股「有信号/达标」展示对齐；min_score=0 时仅买点）。"""
    thr = float(min_score or 0.0)
    out = []
    for r in items or []:
        if r.get("left_buy_signal") or r.get("right_buy_signal"):
            out.append(r)
            continue
        bt = str(r.get("buy_type") or "")
        if bt in ("左侧", "右侧"):
            out.append(r)
            continue
        if thr > 0:
            try:
                sc = float(r.get("score_total"))
            except (TypeError, ValueError):
                sc = None
            if sc is not None and sc >= thr:
                out.append(r)
    return out


def _filter_urt(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in (items or []) if r.get("buy_signal")]


def _filter_sbbr(
    items: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entry, watch = [], []
    for r in items or []:
        if r.get("entry_signal"):
            entry.append(r)
        elif r.get("bottom_matched"):
            watch.append(r)
    return entry, watch


def _filter_rpe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in items or []:
        if r.get("entry_signal") or r.get("watch_only"):
            out.append(r)
            continue
        sig = str(r.get("signal_type") or "").lower()
        if sig in ("catch_up", "lead"):
            out.append(r)
    return out


def _run_gms(db: Session, codes: List[str]) -> List[Dict[str, Any]]:
    from backend_core.strategies.gms.board_resonance import (
        enrich_results_with_board_resonance,
    )
    from backend_core.strategies.gms.frontend_interface import GMSFrontendInterface

    iface = GMSFrontendInterface(db)
    rows = iface.get_selection_results(
        stock_pool=list(codes), market="cn", trace_only=False
    )
    if isinstance(rows, tuple):
        rows = rows[0]
    rows = list(rows or [])
    try:
        enrich_results_with_board_resonance(db, rows, config=iface.config)
    except Exception as e:
        logger.debug("gms board resonance enrich skip: %s", e)
    # 选股默认常按买点展示；同时保留总分达配置 min_score / 接口 min_score 的标的
    min_sc = float(getattr(iface, "min_score", 0) or 0)
    cfg_sc = (iface.config or {}).get("min_score") if isinstance(iface.config, dict) else None
    if cfg_sc is not None:
        try:
            min_sc = max(min_sc, float(cfg_sc))
        except (TypeError, ValueError):
            pass
    return _filter_gms(rows, min_score=min_sc)


def _run_urt(db: Session, codes: List[str]) -> List[Dict[str, Any]]:
    from backend_core.strategies.urt.frontend_interface import URTFrontendInterface

    result = URTFrontendInterface.screen(
        db,
        scope="watchlist",
        stock_codes=list(codes),
        limit=max(len(codes), 50),
        prefer_cache=True,
        force_realtime=False,
    )
    rows = (result or {}).get("data") if isinstance(result, dict) else result
    return _filter_urt(list(rows or []))


def _run_sbbr(db: Session, codes: List[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    from backend_core.strategies.sbbr.strategy_engine import SBBRStrategyEngine

    engine = SBBRStrategyEngine(db_session=db)
    rows = engine.screen(
        codes=list(codes),
        require_entry=False,
        require_size=False,
        require_bottom=False,
        max_results=max(len(codes), 100),
    )
    return _filter_sbbr(list(rows or []))


def _run_rpe(
    db: Session,
    *,
    board_code: Optional[str] = None,
    board_codes: Optional[Sequence[str]] = None,
    board_kind: str,
) -> List[Dict[str, Any]]:
    from backend_core.strategies.rpe.frontend_interface import RPEFrontendInterface

    codes_list = [
        _norm_code(c)
        for c in (list(board_codes) if board_codes else ([board_code] if board_code else []))
        if c
    ]
    codes_list = [c for c in codes_list if c]
    if not codes_list:
        return []
    result = RPEFrontendInterface.get_selection_results(
        db=db,
        scope="industry_board" if board_kind == "industry" else "concept_board",
        board_codes=codes_list,
        board_kind=board_kind,
        max_results=max(500, min(5000, len(codes_list) * 20)),
    )
    rows = (result or {}).get("data") if isinstance(result, dict) else result
    return _filter_rpe(list(rows or []))


def _item_code(row: Dict[str, Any]) -> str:
    return _norm_code(row.get("code") or row.get("stock_code") or row.get("symbol"))


def _enrich_items(
    strategy: str,
    items: List[Dict[str, Any]],
    *,
    names: Dict[str, str],
    ref_by_code: Dict[str, Dict[str, Any]],
    role_by_code: Optional[Dict[str, Any]] = None,
    last_close_by_code: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    closes = last_close_by_code or {}
    out = []
    for raw in items:
        row = dict(raw)
        code = _item_code(row)
        if code and not row.get("name"):
            row["name"] = names.get(code) or row.get("stock_name")
        if role_by_code and code in role_by_code:
            row["role_tags"] = role_by_code[code]
        ref = ref_by_code.get(code)
        lc = closes.get(code)
        if lc is None and isinstance(ref, dict) and ref.get("last_close") is not None:
            try:
                lc = float(ref["last_close"])
            except (TypeError, ValueError):
                lc = None
        if lc is None:
            for k in ("close", "latest_price", "price", "last_close"):
                if row.get(k) is not None:
                    try:
                        lc = float(row[k])
                        break
                    except (TypeError, ValueError):
                        pass
        if lc is not None:
            row["last_close"] = round(float(lc), 2)
        row["trade_advice"] = build_trade_advice(strategy, row, reference_levels=ref)
        out.append(row)
    return out


def _role_tag_map(db: Session, board_kind: str, board_code: str) -> Dict[str, Any]:
    try:
        from backend_core.board_roles.service import (
            extract_leader_mid_from_payload,
            fetch_board_roles_payload,
        )

        kind = "concept" if board_kind == "concept" else "industry"
        payload = fetch_board_roles_payload(
            db,
            board_type=kind,
            board_code=board_code,
            board_code_source="tonghuashun",
        )
        extracted = extract_leader_mid_from_payload(payload or {})
        m: Dict[str, Any] = {}
        for x in extracted.get("leaders") or []:
            c = _norm_code(x.get("code") or x.get("stock_code"))
            if c:
                m[c] = [{"id": "leader", "label": "龙头"}]
        for x in extracted.get("mids") or []:
            c = _norm_code(x.get("code") or x.get("stock_code"))
            if c:
                tags = list(m.get(c) or [])
                tags.append({"id": "mid", "label": "中军"})
                m[c] = tags
        return m
    except Exception as e:
        logger.debug("role tags skip: %s", e)
        return {}


def collect_board_signals(
    db: Session,
    *,
    board_kind: str,
    board_code: str,
    board_code_source: str = "tonghuashun",
    strategies: Optional[Sequence[str]] = None,
    board_name: Optional[str] = None,
) -> Dict[str, Any]:
    kind = "concept" if (board_kind or "").strip().lower() == "concept" else "industry"
    code = _norm_code(board_code)
    wanted = [
        s.strip().lower()
        for s in (strategies or STRATEGY_KEYS)
        if s and s.strip().lower() in STRATEGY_KEYS
    ]
    if not wanted:
        wanted = list(STRATEGY_KEYS)

    # 板详情
    board_meta: Dict[str, Any] = {
        "board_code": code,
        "board_name": board_name or code,
        "board_kind": kind,
        "board_code_source": board_code_source,
    }
    try:
        from backend_api.utils.industry_board_query import (
            fetch_concept_board_detail,
            fetch_industry_board_detail,
        )

        detail_fn = (
            fetch_concept_board_detail if kind == "concept" else fetch_industry_board_detail
        )
        detail = detail_fn(
            db,
            code,
            board_code_source=board_code_source,
            board_name=board_name,
            include_roles=True,
            compute_slope_if_missing=True,
        )
        if detail:
            board_meta.update(
                {
                    "board_name": detail.get("board_name") or board_meta["board_name"],
                    "sector_slope": detail.get("sector_slope"),
                    "board_env": detail.get("board_env"),
                    "board_env_label": detail.get("board_env_label"),
                    "board_weak": detail.get("board_weak"),
                    "board_strong": detail.get("board_strong"),
                    "stock_count": detail.get("stock_count") or detail.get("member_count"),
                    "leaders": detail.get("leaders") or [],
                    "mids": detail.get("mids") or [],
                }
            )
    except Exception as e:
        logger.warning("board detail load failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

    codes, names = load_board_member_codes(db, board_kind=kind, board_code=code)
    role_map = _role_tag_map(db, kind, code)

    errors: Dict[str, str] = {}
    raw: Dict[str, Any] = {}

    def _safe(name: str, fn):
        try:
            return name, fn(), None
        except Exception as e:
            logger.exception("board signal strategy %s failed", name)
            return name, None, str(e)

    # 串行更稳（共享 Session）；板内成分通常可接受
    if "gms" in wanted and codes:
        n, r, err = _safe("gms", lambda: _run_gms(db, codes))
        if err:
            errors[n] = err
            raw[n] = []
        else:
            raw[n] = r or []
    if "urt" in wanted and codes:
        n, r, err = _safe("urt", lambda: _run_urt(db, codes))
        if err:
            errors[n] = err
            raw[n] = []
        else:
            raw[n] = r or []
    if "sbbr" in wanted and codes:
        n, r, err = _safe("sbbr", lambda: _run_sbbr(db, codes))
        if err:
            errors[n] = err
            raw["sbbr_entry"] = []
            raw["sbbr_watch"] = []
        else:
            entry, watch = r or ([], [])
            raw["sbbr_entry"] = entry
            raw["sbbr_watch"] = watch
    if "rpe" in wanted:
        n, r, err = _safe("rpe", lambda: _run_rpe(db, board_code=code, board_kind=kind))
        if err:
            errors[n] = err
            raw[n] = []
        else:
            raw[n] = r or []

    # 命中代码批量 Fib/Pivot
    hit_codes: List[str] = []
    for key in ("gms", "urt", "rpe"):
        for row in raw.get(key) or []:
            c = _item_code(row)
            if c:
                hit_codes.append(c)
    for row in (raw.get("sbbr_entry") or []) + (raw.get("sbbr_watch") or []):
        c = _item_code(row)
        if c:
            hit_codes.append(c)
    hit_codes = sorted(set(hit_codes))
    bars = batch_load_ohlc_bars(db, hit_codes, lookback=OHLC_LOOKBACK)
    last_closes = {
        c: float(bars[c][-1]["close"])
        for c in bars
        if bars[c] and bars[c][-1].get("close") is not None
    }
    kde_by: Dict[str, Dict[str, Any]] = {}
    for key in ("gms", "urt", "rpe"):
        for row in raw.get(key) or []:
            c = _item_code(row)
            if not c or c in kde_by:
                continue
            st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
            kde_by[c] = {
                "support": row.get("nearest_support") or st.get("nearest_support"),
                "resistance": row.get("nearest_resistance") or st.get("nearest_resistance"),
                "supports": row.get("supports") or st.get("supports"),
                "resistances": row.get("resistances") or st.get("resistances"),
            }
    for row in (raw.get("sbbr_entry") or []) + (raw.get("sbbr_watch") or []):
        c = _item_code(row)
        if not c or c in kde_by:
            continue
        st = row.get("structure") if isinstance(row.get("structure"), dict) else {}
        kde_by[c] = {
            "support": row.get("nearest_support") or st.get("nearest_support"),
            "resistance": row.get("nearest_resistance") or st.get("nearest_resistance"),
            "supports": row.get("supports") or st.get("supports"),
            "resistances": row.get("resistances") or st.get("resistances"),
        }
    ref_by = attach_reference_levels_batch(
        bars, last_close_by_code=last_closes, kde_by_code=kde_by
    )

    enrich_kw = dict(
        names=names,
        ref_by_code=ref_by,
        role_by_code=role_map,
        last_close_by_code=last_closes,
    )
    strategies_out: Dict[str, Any] = {}
    if "gms" in wanted:
        items = _enrich_items("gms", raw.get("gms") or [], **enrich_kw)
        strategies_out["gms"] = {"total": len(items), "items": items}
    if "urt" in wanted:
        items = _enrich_items("urt", raw.get("urt") or [], **enrich_kw)
        strategies_out["urt"] = {"total": len(items), "items": items}
    if "sbbr" in wanted:
        entry = _enrich_items("sbbr", raw.get("sbbr_entry") or [], **enrich_kw)
        watch = _enrich_items("sbbr", raw.get("sbbr_watch") or [], **enrich_kw)
        strategies_out["sbbr"] = {
            "total": len(entry),
            "items": entry,
            "watch_total": len(watch),
            "watch_items": watch,
        }
    if "rpe" in wanted:
        items = _enrich_items("rpe", raw.get("rpe") or [], **enrich_kw)
        strategies_out["rpe"] = {"total": len(items), "items": items}

    return {
        "board": board_meta,
        "member_count": len(codes),
        "strategies": strategies_out,
        "errors": errors,
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _hit_index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """code → 命中行（后者覆盖前者）。"""
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows or []:
        c = _item_code(r)
        if c:
            out[c] = r
    return out


def _slim_reference_levels(ref: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """列表展示用精简 reference_levels（去掉 bins/zigzag 大数组）。"""
    if not isinstance(ref, dict):
        return None
    vp = ref.get("volume_profile") if isinstance(ref.get("volume_profile"), dict) else {}
    cam = ref.get("camarilla") if isinstance(ref.get("camarilla"), dict) else {}
    atrp = ref.get("atr_pivot") if isinstance(ref.get("atr_pivot"), dict) else {}
    fib = ref.get("fibonacci") if isinstance(ref.get("fibonacci"), dict) else {}
    conf = ref.get("confluence_zones") if isinstance(ref.get("confluence_zones"), dict) else {}
    return {
        "ok": bool(ref.get("ok")),
        "last_close": ref.get("last_close"),
        "nearest_fib_support": ref.get("nearest_fib_support"),
        "nearest_fib_resistance": ref.get("nearest_fib_resistance"),
        "nearest_pivot_support": ref.get("nearest_pivot_support"),
        "nearest_pivot_resistance": ref.get("nearest_pivot_resistance"),
        "nearest_cam_support": ref.get("nearest_cam_support") or cam.get("nearest_support"),
        "nearest_cam_resistance": ref.get("nearest_cam_resistance")
        or cam.get("nearest_resistance"),
        "nearest_vp_support": ref.get("nearest_vp_support") or vp.get("nearest_support"),
        "nearest_vp_resistance": ref.get("nearest_vp_resistance")
        or vp.get("nearest_resistance"),
        "nearest_confluence_support": ref.get("nearest_confluence_support"),
        "nearest_confluence_resistance": ref.get("nearest_confluence_resistance"),
        "volume_profile": {
            "ok": bool(vp.get("ok")),
            "poc": vp.get("poc"),
            "val": vp.get("val"),
            "vah": vp.get("vah"),
            "nearest_support": vp.get("nearest_support"),
            "nearest_resistance": vp.get("nearest_resistance"),
        },
        "camarilla": {
            "nearest_support": cam.get("nearest_support"),
            "nearest_resistance": cam.get("nearest_resistance"),
            "R1": cam.get("R1"),
            "S1": cam.get("S1"),
        },
        "atr_pivot": {
            "atr": atrp.get("atr"),
            "R1": atrp.get("R1"),
            "S1": atrp.get("S1"),
        },
        "fibonacci": {
            "anchor_method": fib.get("anchor_method"),
            "swing_high": fib.get("swing_high"),
            "swing_low": fib.get("swing_low"),
            "swing_high_date": fib.get("swing_high_date"),
            "swing_low_date": fib.get("swing_low_date"),
            "direction": fib.get("direction"),
            "bar_span": fib.get("bar_span"),
        },
        "confluence_zones": {
            "ok": bool(conf.get("ok")),
            "nearest_support_zone": conf.get("nearest_support_zone"),
            "nearest_resistance_zone": conf.get("nearest_resistance_zone"),
        },
    }


def _levels_for_codes(
    db: Session,
    codes: Sequence[str],
) -> Dict[str, Dict[str, Any]]:
    """批量：收盘价 + KDE 最近支撑/压力 + Fib/Cam/VP/共振参考价。"""
    uniq = sorted({_norm_code(c) for c in codes if _norm_code(c)})
    if not uniq:
        return {}
    # KDE 初始回看约 250；经典/共振用同窗
    lb = max(OHLC_LOOKBACK, 260)
    bars_by = batch_load_ohlc_bars(db, uniq, lookback=lb)
    last_closes: Dict[str, float] = {}
    kde_by: Dict[str, Dict[str, Any]] = {}
    try:
        from backend_core.strategies.gms.structure_levels import compute_structure_levels
    except Exception:
        compute_structure_levels = None  # type: ignore

    # 多票时限制 KDE 扩窗，控制「全部」查询耗时
    kde_cfg = {
        "kde_lookback_days": 250,
        "kde_lookback_initial": 250,
        "kde_lookback_step": 250,
        "kde_lookback_max": 250 if len(uniq) > 40 else 500,
        "kde_base_factor": 1.0,
        "kde_grid_points": 160 if len(uniq) > 40 else 200,
    }

    for c, bars in bars_by.items():
        if not bars:
            continue
        try:
            lc = float(bars[-1]["close"])
        except (TypeError, ValueError, KeyError):
            continue
        if lc <= 0:
            continue
        last_closes[c] = round(lc, 2)
        if compute_structure_levels is None:
            continue
        try:
            bars_desc = list(reversed(bars))
            st = compute_structure_levels(bars_desc, kde_cfg, price=lc)
            kde_by[c] = {
                "support": st.get("nearest_support"),
                "resistance": st.get("nearest_resistance"),
                "supports": st.get("support_levels") or [],
                "resistances": st.get("resistance_levels") or [],
                "kde_ok": st.get("kde_ok"),
                "kde_reason": st.get("kde_reason"),
            }
        except Exception as e:
            logger.debug("kde for %s skip: %s", c, e)

    ref_by = attach_reference_levels_batch(
        bars_by, last_close_by_code=last_closes, kde_by_code=kde_by
    )
    out: Dict[str, Dict[str, Any]] = {}
    for c in uniq:
        kde = kde_by.get(c) or {}
        ref = _slim_reference_levels(ref_by.get(c))
        out[c] = {
            "last_close": last_closes.get(c),
            "kde_support": kde.get("support"),
            "kde_resistance": kde.get("resistance"),
            "kde_ok": kde.get("kde_ok"),
            "reference_levels": ref,
        }
    return out


def _strategy_hit_cell(
    strategy: str,
    row: Optional[Dict[str, Any]],
    *,
    watch_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """单策略命中单元格。"""
    kind = (strategy or "").strip().lower()
    if kind == "sbbr":
        if row:
            return {
                "hit": True,
                "kind": "entry",
                "label": "入场",
                "detail": row,
            }
        if watch_row:
            return {
                "hit": True,
                "kind": "watch",
                "label": "筑底",
                "detail": watch_row,
            }
        return {"hit": False, "kind": None, "label": "--", "detail": None}
    if not row:
        return {"hit": False, "kind": None, "label": "--", "detail": None}
    if kind == "gms":
        label = row.get("buy_type") or (
            "左侧" if row.get("left_buy_signal") else "右侧" if row.get("right_buy_signal") else "GMS"
        )
        return {"hit": True, "kind": "signal", "label": str(label), "detail": row}
    if kind == "urt":
        return {"hit": True, "kind": "buy", "label": "买点", "detail": row}
    if kind == "rpe":
        sig = str(row.get("signal_type") or "").lower()
        if row.get("watch_only") or sig == "lead":
            label = "领涨观察"
        elif row.get("entry_signal") or sig == "catch_up":
            label = "补涨"
        else:
            label = sig or "RPE"
        return {"hit": True, "kind": sig or "signal", "label": label, "detail": row}
    return {"hit": True, "kind": "signal", "label": kind.upper(), "detail": row}


def _is_all_boards_code(board_code: Any) -> bool:
    s = str(board_code or "").strip().lower()
    return s in ("all", "*", "__all__", "全部")


def _list_boards_for_kind(
    db: Session,
    *,
    board_kind: str,
    board_code_source: str = "tonghuashun",
) -> List[Dict[str, Any]]:
    """列出行业/概念板目录（同花顺默认）。"""
    kind = "concept" if board_kind == "concept" else "industry"
    src = board_code_source or "tonghuashun"
    if kind == "concept":
        from backend_api.utils.industry_board_query import fetch_concept_board_catalog

        rows = fetch_concept_board_catalog(db, board_code_source=src) or []
    else:
        from backend_api.utils.industry_board_query import fetch_industry_board_catalog

        rows = fetch_industry_board_catalog(db, board_code_source=src) or []
    out: List[Dict[str, Any]] = []
    for b in rows:
        if not isinstance(b, dict):
            continue
        bc = _norm_code(b.get("board_code"))
        if not bc:
            continue
        out.append(
            {
                "board_code": bc,
                "board_name": b.get("board_name") or bc,
                "board_code_source": b.get("board_code_source") or src,
            }
        )
    return out


def _merge_role_row(
    by_code: Dict[str, Dict[str, Any]],
    x: Dict[str, Any],
    *,
    board_code: str,
    board_name: str,
) -> None:
    """跨板合并角色股：龙头优先于中军，并累计所属板块。"""
    c = _norm_code(x.get("code"))
    if not c:
        return
    board_tag = {
        "board_code": board_code,
        "board_name": board_name,
        "board_role": x.get("board_role"),
        "board_role_label": x.get("board_role_label"),
    }
    prev = by_code.get(c)
    if prev is None:
        row = dict(x)
        row["code"] = c
        row["boards"] = [board_tag]
        by_code[c] = row
        return
    boards = list(prev.get("boards") or [])
    if not any(b.get("board_code") == board_code for b in boards):
        boards.append(board_tag)
    prev["boards"] = boards
    # 龙头覆盖中军展示角色
    if prev.get("board_role") != "leader" and x.get("board_role") == "leader":
        for k in (
            "board_role",
            "board_role_label",
            "board_role_score",
            "role_reason",
            "name",
            "change_percent",
        ):
            if x.get(k) is not None:
                prev[k] = x.get(k)


def collect_leader_mid_strategy_hits(
    db: Session,
    *,
    board_kind: str,
    board_code: str = "",
    board_codes: Optional[Sequence[str]] = None,
    board_code_source: str = "tonghuashun",
    board_name: Optional[str] = None,
    strategies: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """板块龙头+中军子集 × 四策略是否命中（不跑全成分）。

    - board_codes：多板代码列表（优先）
    - board_code=all / __all__ / 全部：该类型下全部板块
    - 否则单板 board_code
    """
    kind = "concept" if (board_kind or "").strip().lower() == "concept" else "industry"
    multi_codes = [
        _norm_code(c)
        for c in (board_codes or [])
        if c and not _is_all_boards_code(c)
    ]
    # 去重保序
    seen_bc: set = set()
    multi_codes = [c for c in multi_codes if c and not (c in seen_bc or seen_bc.add(c))]
    all_mode = (not multi_codes) and _is_all_boards_code(board_code)
    multi_mode = bool(multi_codes) or all_mode
    code = (
        "all"
        if all_mode
        else (",".join(multi_codes) if len(multi_codes) > 1 else (multi_codes[0] if multi_codes else _norm_code(board_code)))
    )
    wanted = [
        s.strip().lower()
        for s in (strategies or STRATEGY_KEYS)
        if s and s.strip().lower() in STRATEGY_KEYS
    ]
    if not wanted:
        wanted = list(STRATEGY_KEYS)

    from backend_core.board_roles.service import (
        extract_leader_mid_from_payload,
        fetch_board_roles_payload,
    )

    if all_mode:
        display_name = "全部"
    elif len(multi_codes) > 1:
        display_name = f"已选 {len(multi_codes)} 个板块"
    elif multi_codes:
        display_name = board_name or multi_codes[0]
    else:
        display_name = board_name or code

    board_meta: Dict[str, Any] = {
        "board_code": code,
        "board_name": display_name,
        "board_kind": kind,
        "board_code_source": board_code_source,
        "all_boards": all_mode,
        "multi_boards": multi_mode,
        "selected_board_codes": list(multi_codes) if multi_codes else ([] if all_mode else [code]),
        "board_count": 0,
        "leaders": [],
        "mids": [],
        "board_change_percent_est": None,
    }
    role_by_code: Dict[str, Dict[str, Any]] = {}
    rpe_board_codes: List[str] = []
    leader_n = 0
    mid_n = 0

    def _ingest_extracted(extracted: Dict[str, Any], *, bc: str, bn: str) -> None:
        nonlocal leader_n, mid_n
        leaders = list(extracted.get("leaders") or [])
        mids = list(extracted.get("mids") or [])
        leader_n += len(leaders)
        mid_n += len(mids)
        for x in leaders + mids:
            _merge_role_row(role_by_code, x, board_code=bc, board_name=bn)

    try:
        if multi_mode:
            if all_mode:
                boards = _list_boards_for_kind(
                    db,
                    board_kind=kind,
                    board_code_source=board_code_source or "tonghuashun",
                )
            else:
                # 多选：按代码拉取；名称尽量用目录补齐
                catalog = {
                    b["board_code"]: b
                    for b in _list_boards_for_kind(
                        db,
                        board_kind=kind,
                        board_code_source=board_code_source or "tonghuashun",
                    )
                }
                boards = []
                for bc in multi_codes:
                    meta_b = catalog.get(bc) or {}
                    boards.append(
                        {
                            "board_code": bc,
                            "board_name": meta_b.get("board_name") or bc,
                            "board_code_source": meta_b.get("board_code_source")
                            or board_code_source
                            or "tonghuashun",
                        }
                    )
            board_meta["board_count"] = len(boards)
            board_meta["selected_board_codes"] = [b["board_code"] for b in boards]
            for b in boards:
                bc = b["board_code"]
                bn = str(b.get("board_name") or bc)
                try:
                    payload = fetch_board_roles_payload(
                        db,
                        board_type=kind,
                        board_code=bc,
                        board_code_source=b.get("board_code_source")
                        or board_code_source
                        or "tonghuashun",
                    )
                    if not payload:
                        continue
                    extracted = extract_leader_mid_from_payload(payload)
                    if extracted.get("leaders") or extracted.get("mids"):
                        rpe_board_codes.append(bc)
                    _ingest_extracted(extracted, bc=bc, bn=bn)
                except Exception as e:
                    logger.debug("leader/mid skip board %s: %s", bc, e)
                    try:
                        db.rollback()
                    except Exception:
                        pass
            board_meta["leaders"] = [
                x for x in role_by_code.values() if x.get("board_role") == "leader"
            ]
            board_meta["mids"] = [
                x for x in role_by_code.values() if x.get("board_role") == "mid"
            ]
            if len(boards) == 1 and not all_mode:
                board_meta["board_name"] = boards[0].get("board_name") or boards[0]["board_code"]
                board_meta["board_code"] = boards[0]["board_code"]
        else:
            payload = fetch_board_roles_payload(
                db,
                board_type=kind,
                board_code=code,
                board_code_source=board_code_source or "tonghuashun",
                board_name=board_name,
            )
            extracted = extract_leader_mid_from_payload(payload or {})
            leaders = list(extracted.get("leaders") or [])
            mids = list(extracted.get("mids") or [])
            board_meta.update(
                {
                    "board_code": extracted.get("board_code") or code,
                    "board_name": extracted.get("board_name") or board_meta["board_name"],
                    "board_code_source": extracted.get("board_code_source")
                    or board_code_source,
                    "board_change_percent_est": extracted.get(
                        "board_change_percent_est"
                    ),
                    "board_count": 1,
                    "selected_board_codes": [
                        extracted.get("board_code") or code
                    ],
                    "leaders": leaders,
                    "mids": mids,
                }
            )
            bn = str(board_meta["board_name"])
            bc = str(board_meta["board_code"])
            rpe_board_codes = [bc]
            _ingest_extracted(extracted, bc=bc, bn=bn)
            leader_n = len(leaders)
            mid_n = len(mids)
    except Exception as e:
        logger.warning("leader/mid roles load failed: %s", e)
        try:
            db.rollback()
        except Exception:
            pass

    # 龙头在前、中军在后
    role_rows = sorted(
        role_by_code.values(),
        key=lambda x: (
            0 if x.get("board_role") == "leader" else 1,
            -float(x.get("board_role_score") or 0),
            str(x.get("code") or ""),
        ),
    )
    codes = [_norm_code(x.get("code")) for x in role_rows if x.get("code")]
    names = {
        _norm_code(x.get("code")): str(x.get("name") or "")
        for x in role_rows
        if x.get("code")
    }
    code_set = set(codes)

    errors: Dict[str, str] = {}
    hit_maps: Dict[str, Dict[str, Dict[str, Any]]] = {
        "gms": {},
        "urt": {},
        "sbbr_entry": {},
        "sbbr_watch": {},
        "rpe": {},
    }

    def _safe(name: str, fn):
        try:
            return name, fn(), None
        except Exception as e:
            logger.exception("leader-mid strategy %s failed", name)
            return name, None, str(e)

    if codes:
        if "gms" in wanted:
            n, r, err = _safe("gms", lambda: _run_gms(db, codes))
            if err:
                errors[n] = err
            else:
                hit_maps["gms"] = _hit_index(r or [])
        if "urt" in wanted:
            n, r, err = _safe("urt", lambda: _run_urt(db, codes))
            if err:
                errors[n] = err
            else:
                hit_maps["urt"] = _hit_index(r or [])
        if "sbbr" in wanted:
            n, r, err = _safe("sbbr", lambda: _run_sbbr(db, codes))
            if err:
                errors[n] = err
            else:
                entry, watch = r or ([], [])
                hit_maps["sbbr_entry"] = _hit_index(entry)
                hit_maps["sbbr_watch"] = _hit_index(watch)
        if "rpe" in wanted:
            boards_for_rpe = rpe_board_codes or ([code] if not all_mode else [])
            n, r, err = _safe(
                "rpe",
                lambda: _run_rpe(
                    db, board_codes=boards_for_rpe, board_kind=kind
                ),
            )
            if err:
                errors[n] = err
            else:
                hit_maps["rpe"] = {
                    c: row
                    for c, row in _hit_index(r or []).items()
                    if c in code_set
                }

    levels_by: Dict[str, Dict[str, Any]] = {}
    if codes:
        n, r, err = _safe("levels", lambda: _levels_for_codes(db, codes))
        if err:
            errors[n] = err
        else:
            levels_by = r or {}

    items: List[Dict[str, Any]] = []
    for x in role_rows:
        c = _norm_code(x.get("code"))
        hits: Dict[str, Any] = {}
        if "gms" in wanted:
            hits["gms"] = _strategy_hit_cell("gms", hit_maps["gms"].get(c))
        if "urt" in wanted:
            hits["urt"] = _strategy_hit_cell("urt", hit_maps["urt"].get(c))
        if "sbbr" in wanted:
            hits["sbbr"] = _strategy_hit_cell(
                "sbbr",
                hit_maps["sbbr_entry"].get(c),
                watch_row=hit_maps["sbbr_watch"].get(c),
            )
        if "rpe" in wanted:
            hits["rpe"] = _strategy_hit_cell("rpe", hit_maps["rpe"].get(c))
        any_hit = any(bool((hits.get(k) or {}).get("hit")) for k in hits)
        boards = list(x.get("boards") or [])
        lv = levels_by.get(c) or {}
        items.append(
            {
                "code": c,
                "name": names.get(c) or x.get("name") or "",
                "board_role": x.get("board_role"),
                "board_role_label": x.get("board_role_label"),
                "board_role_score": x.get("board_role_score"),
                "change_percent": x.get("change_percent"),
                "role_reason": x.get("role_reason") or "",
                "boards": boards,
                "board_labels": "、".join(
                    str(b.get("board_name") or b.get("board_code") or "")
                    for b in boards
                    if b
                ),
                "last_close": lv.get("last_close"),
                "kde_support": lv.get("kde_support"),
                "kde_resistance": lv.get("kde_resistance"),
                "kde_ok": lv.get("kde_ok"),
                "reference_levels": lv.get("reference_levels"),
                "hits": hits,
                "any_hit": any_hit,
                "hit_count": sum(1 for k in hits if (hits.get(k) or {}).get("hit")),
            }
        )

    return {
        "board": board_meta,
        "role_count": len(items),
        "leader_count": leader_n if all_mode else len(board_meta.get("leaders") or []),
        "mid_count": mid_n if all_mode else len(board_meta.get("mids") or []),
        "strategies": list(wanted),
        "items": items,
        "errors": errors,
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
