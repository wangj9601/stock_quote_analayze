# -*- coding: utf-8 -*-
"""板块多策略信号聚合：行业/概念板 × GMS/URT/SBBR/RPE + 买卖建议。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_core.analysis.classic_levels import (
    DEFAULT_LOOKBACK,
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
    lookback: int = DEFAULT_LOOKBACK,
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


def _run_rpe(db: Session, *, board_code: str, board_kind: str) -> List[Dict[str, Any]]:
    from backend_core.strategies.rpe.frontend_interface import RPEFrontendInterface

    result = RPEFrontendInterface.get_selection_results(
        db=db,
        scope="industry_board" if board_kind == "industry" else "concept_board",
        board_codes=[board_code],
        board_kind=board_kind,
        max_results=500,
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
    bars = batch_load_ohlc_bars(db, hit_codes, lookback=DEFAULT_LOOKBACK)
    last_closes = {
        c: float(bars[c][-1]["close"])
        for c in bars
        if bars[c] and bars[c][-1].get("close") is not None
    }
    ref_by = attach_reference_levels_batch(bars, last_close_by_code=last_closes)

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
