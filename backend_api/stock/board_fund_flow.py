# -*- coding: utf-8 -*-
"""板块资金流向 API：读库日序列 + 手动触发采集。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend_api.database import get_db
from backend_api.utils.board_code_source import DEFAULT_BOARD_CODE_SOURCE

router = APIRouter(prefix="/api/board_fund_flow", tags=["board_fund_flow"])


def collect_board_fund_flow_daily(*args, **kwargs):
    from backend_core.data_collectors.akshare.board_fund_flow_daily import (
        collect_board_fund_flow_daily as _fn,
    )
    return _fn(*args, **kwargs)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@router.get("/daily")
async def get_board_fund_flow_daily(
    board_code: str = Query(..., description="板块代码"),
    board_kind: str = Query("industry", description="industry | concept"),
    board_code_source: str = Query(
        DEFAULT_BOARD_CODE_SOURCE, description="默认 tonghuashun"
    ),
    days: int = Query(20, ge=1, le=120, description="最近 N 个交易日"),
    db: Session = Depends(get_db),
):
    """查询单板近 N 日资金流（升序）。金额单位：元。"""
    kind = (board_kind or "industry").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 应为 industry 或 concept"},
            status_code=400,
        )
    code = str(board_code or "").strip()
    if not code:
        return JSONResponse(
            {"success": False, "message": "缺少 board_code"}, status_code=400
        )
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip() or DEFAULT_BOARD_CODE_SOURCE

    try:
        rows = db.execute(
            text(
                """
                SELECT trade_date, board_name, change_percent,
                       inflow_amount, outflow_amount, main_net_inflow,
                       main_net_inflow_pct,
                       super_large_net_inflow, large_net_inflow,
                       mid_net_inflow, small_net_inflow,
                       source, em_board_code
                FROM board_fund_flow_daily
                WHERE board_kind = :kind
                  AND board_code_source = :src
                  AND board_code = :code
                ORDER BY trade_date DESC
                LIMIT :lim
                """
            ),
            {"kind": kind, "src": src, "code": code, "lim": int(days)},
        ).mappings().all()

        series_desc: List[Dict[str, Any]] = []
        for r in rows:
            td = r["trade_date"]
            if hasattr(td, "isoformat"):
                td_s = td.isoformat()
            else:
                td_s = str(td)[:10]
            series_desc.append(
                {
                    "trade_date": td_s,
                    "board_name": r["board_name"],
                    "change_percent": _safe_float(r["change_percent"]),
                    "inflow_amount": _safe_float(r["inflow_amount"]),
                    "outflow_amount": _safe_float(r["outflow_amount"]),
                    "main_net_inflow": _safe_float(r["main_net_inflow"]),
                    "main_net_inflow_pct": _safe_float(r["main_net_inflow_pct"]),
                    "super_large_net_inflow": _safe_float(r["super_large_net_inflow"]),
                    "large_net_inflow": _safe_float(r["large_net_inflow"]),
                    "mid_net_inflow": _safe_float(r["mid_net_inflow"]),
                    "small_net_inflow": _safe_float(r["small_net_inflow"]),
                    "source": r["source"],
                    "em_board_code": r["em_board_code"],
                }
            )
        series_asc = list(reversed(series_desc))
        latest = series_asc[-1] if series_asc else None
        return {
            "success": True,
            "data": {
                "board_kind": kind,
                "board_code": code,
                "board_code_source": src,
                "days_requested": days,
                "series_source": "board_fund_flow_daily",
                "latest": latest,
                "series": series_asc,
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询板块资金流失败: {e}"},
            status_code=500,
        )


@router.get("/today")
async def get_board_fund_flow_today(
    board_kind: Optional[str] = Query(None, description="industry | concept；空=全部"),
    board_code_source: str = Query(DEFAULT_BOARD_CODE_SOURCE),
    trade_date: Optional[str] = Query(None, description="YYYY-MM-DD，默认最新有数据日"),
    db: Session = Depends(get_db),
):
    """当日（或指定日）全表板块资金流。"""
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip() or DEFAULT_BOARD_CODE_SOURCE
    kind = (board_kind or "").strip().lower() or None
    if kind and kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 应为 industry 或 concept"},
            status_code=400,
        )
    td = None
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
            td = trade_date
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )
    try:
        if not td:
            row = db.execute(
                text(
                    """
                    SELECT MAX(trade_date) FROM board_fund_flow_daily
                    WHERE board_code_source = :src
                    """
                ),
                {"src": src},
            ).scalar()
            if row is None:
                return {
                    "success": True,
                    "data": {"trade_date": None, "items": [], "count": 0},
                }
            td = row.isoformat() if hasattr(row, "isoformat") else str(row)[:10]

        params: Dict[str, Any] = {"src": src, "td": td}
        kind_sql = ""
        if kind:
            kind_sql = "AND board_kind = :kind"
            params["kind"] = kind
        rows = db.execute(
            text(
                f"""
                SELECT board_kind, board_code, board_name, trade_date,
                       change_percent, inflow_amount, outflow_amount,
                       main_net_inflow, source
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND trade_date = CAST(:td AS date)
                  {kind_sql}
                ORDER BY main_net_inflow DESC NULLS LAST
                """
            ),
            params,
        ).mappings().all()
        items = []
        for r in rows:
            items.append(
                {
                    "board_kind": r["board_kind"],
                    "board_code": r["board_code"],
                    "board_name": r["board_name"],
                    "trade_date": td,
                    "change_percent": _safe_float(r["change_percent"]),
                    "inflow_amount": _safe_float(r["inflow_amount"]),
                    "outflow_amount": _safe_float(r["outflow_amount"]),
                    "main_net_inflow": _safe_float(r["main_net_inflow"]),
                    "source": r["source"],
                }
            )
        return {
            "success": True,
            "data": {"trade_date": td, "items": items, "count": len(items)},
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询失败: {e}"}, status_code=500
        )


# 日/周/月：交易日窗口（近 N 个有资金流数据的交易日）
_BOARD_FUND_FLOW_RANK_PERIODS = {
    "day": {"days": 1, "label": "日"},
    "week": {"days": 5, "label": "周"},
    "month": {"days": 20, "label": "月"},
}


@router.get("/rank")
async def get_board_fund_flow_rank(
    period: str = Query("day", description="day|week|month（近1/5/20 个交易日净流入合计）"),
    board_kind: str = Query(..., description="industry | concept"),
    board_code_source: str = Query(DEFAULT_BOARD_CODE_SOURCE),
    trade_date: Optional[str] = Query(
        None, description="锚定交易日 YYYY-MM-DD；默认取库内最新日"
    ),
    db: Session = Depends(get_db),
):
    """
    板块资金流向趋势跟踪：按日/周/月汇总主力净流入，全板升序返回（弱→强）。
    数据源：board_fund_flow_daily。
    """
    key = (period or "day").strip().lower()
    meta = _BOARD_FUND_FLOW_RANK_PERIODS.get(key)
    if not meta:
        return JSONResponse(
            {"success": False, "message": "period 应为 day / week / month"},
            status_code=400,
        )
    kind = (board_kind or "").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 应为 industry 或 concept"},
            status_code=400,
        )
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip() or DEFAULT_BOARD_CODE_SOURCE
    n_days = int(meta["days"])
    anchor = None
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
            anchor = trade_date
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )

    def _empty(end: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": True,
            "data": {
                "period": key,
                "period_label": meta["label"],
                "board_kind": kind,
                "board_code_source": src,
                "trade_days": n_days,
                "start_date": None,
                "end_date": end,
                "items": [],
                "count": 0,
            },
        }

    try:
        if not anchor:
            latest = db.execute(
                text(
                    """
                    SELECT MAX(trade_date) FROM board_fund_flow_daily
                    WHERE board_code_source = :src
                      AND board_kind = :kind
                    """
                ),
                {"src": src, "kind": kind},
            ).scalar()
            if latest is None:
                return _empty()
            anchor = (
                latest.isoformat()[:10]
                if hasattr(latest, "isoformat")
                else str(latest)[:10]
            )

        date_rows = db.execute(
            text(
                """
                SELECT DISTINCT trade_date
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND board_kind = :kind
                  AND trade_date <= CAST(:anchor AS date)
                ORDER BY trade_date DESC
                LIMIT :n_days
                """
            ),
            {"src": src, "kind": kind, "anchor": anchor, "n_days": n_days},
        ).fetchall()
        trade_dates = [
            (r[0].isoformat()[:10] if hasattr(r[0], "isoformat") else str(r[0])[:10])
            for r in date_rows
            if r and r[0] is not None
        ]
        if not trade_dates:
            return _empty(anchor)

        start_date = min(trade_dates)
        end_date = max(trade_dates)
        rows = db.execute(
            text(
                """
                SELECT
                    board_kind,
                    board_code,
                    (array_agg(board_name ORDER BY trade_date DESC))[1] AS board_name,
                    SUM(main_net_inflow) AS main_net_inflow,
                    SUM(inflow_amount) AS inflow_amount,
                    SUM(outflow_amount) AS outflow_amount,
                    COUNT(*)::int AS days_count
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND board_kind = :kind
                  AND trade_date >= CAST(:start_d AS date)
                  AND trade_date <= CAST(:end_d AS date)
                GROUP BY board_kind, board_code
                HAVING SUM(main_net_inflow) IS NOT NULL
                ORDER BY SUM(main_net_inflow) ASC NULLS LAST
                """
            ),
            {
                "src": src,
                "kind": kind,
                "start_d": start_date,
                "end_d": end_date,
            },
        ).mappings().all()

        items: List[Dict[str, Any]] = []
        for r in rows:
            items.append(
                {
                    "board_kind": r["board_kind"],
                    "board_code": r["board_code"],
                    "board_name": r["board_name"],
                    "trade_date": end_date,
                    "change_percent": None,
                    "inflow_amount": _safe_float(r["inflow_amount"]),
                    "outflow_amount": _safe_float(r["outflow_amount"]),
                    "main_net_inflow": _safe_float(r["main_net_inflow"]),
                    "days_count": int(r["days_count"] or 0),
                    "source": None,
                }
            )
        return {
            "success": True,
            "data": {
                "period": key,
                "period_label": meta["label"],
                "board_kind": kind,
                "board_code_source": src,
                "trade_days": n_days,
                "start_date": start_date,
                "end_date": end_date,
                "items": items,
                "count": len(items),
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询板块资金流排名失败: {e}"},
            status_code=500,
        )


# 趋势图交易日窗口：日/周/月分别拉长，避免「日」只有 1 点无法看趋势
_BOARD_FUND_FLOW_TREND_DAYS = {
    "day": 20,
    "week": 40,
    "month": 60,
}


def _iso_date(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


@router.get("/trend_series")
async def get_board_fund_flow_trend_series(
    period: str = Query("day", description="day|week|month → 趋势窗口 20/40/60 交易日"),
    board_kind: str = Query(..., description="industry | concept"),
    board_code_source: str = Query(DEFAULT_BOARD_CODE_SOURCE),
    trade_date: Optional[str] = Query(
        None, description="锚定交易日 YYYY-MM-DD；默认取库内最新日"
    ),
    top_n: int = Query(5, ge=1, le=10, description="叠加展示的净流入最强板块数"),
    db: Session = Depends(get_db),
):
    """
    板块资金流向趋势序列：全板按日合计净流入/流入/流出 + TopN 板块日序列。
    数据源：board_fund_flow_daily。
    """
    key = (period or "day").strip().lower()
    trend_days = _BOARD_FUND_FLOW_TREND_DAYS.get(key)
    period_meta = _BOARD_FUND_FLOW_RANK_PERIODS.get(key)
    if trend_days is None or period_meta is None:
        return JSONResponse(
            {"success": False, "message": "period 应为 day / week / month"},
            status_code=400,
        )
    kind = (board_kind or "").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 应为 industry | concept"},
            status_code=400,
        )
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip() or DEFAULT_BOARD_CODE_SOURCE
    anchor = None
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
            anchor = trade_date
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )

    def _empty(end: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": True,
            "data": {
                "period": key,
                "period_label": period_meta["label"],
                "board_kind": kind,
                "board_code_source": src,
                "trend_days": int(trend_days),
                "start_date": None,
                "end_date": end,
                "dates": [],
                "aggregate": {
                    "main_net_inflow": [],
                    "inflow_amount": [],
                    "outflow_amount": [],
                },
                "top_entities": [],
            },
        }

    try:
        if not anchor:
            latest = db.execute(
                text(
                    """
                    SELECT MAX(trade_date) FROM board_fund_flow_daily
                    WHERE board_code_source = :src
                      AND board_kind = :kind
                    """
                ),
                {"src": src, "kind": kind},
            ).scalar()
            if latest is None:
                return _empty()
            anchor = _iso_date(latest)

        date_rows = db.execute(
            text(
                """
                SELECT DISTINCT trade_date
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND board_kind = :kind
                  AND trade_date <= CAST(:anchor AS date)
                ORDER BY trade_date DESC
                LIMIT :n_days
                """
            ),
            {"src": src, "kind": kind, "anchor": anchor, "n_days": int(trend_days)},
        ).fetchall()
        trade_dates_desc = [
            _iso_date(r[0]) for r in date_rows if r and r[0] is not None
        ]
        if not trade_dates_desc:
            return _empty(anchor)

        dates = list(reversed(trade_dates_desc))
        start_date = dates[0]
        end_date = dates[-1]

        agg_rows = db.execute(
            text(
                """
                SELECT
                    trade_date,
                    SUM(main_net_inflow) AS main_net_inflow,
                    SUM(inflow_amount) AS inflow_amount,
                    SUM(outflow_amount) AS outflow_amount
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND board_kind = :kind
                  AND trade_date >= CAST(:start_d AS date)
                  AND trade_date <= CAST(:end_d AS date)
                GROUP BY trade_date
                ORDER BY trade_date ASC
                """
            ),
            {"src": src, "kind": kind, "start_d": start_date, "end_d": end_date},
        ).mappings().all()
        agg_by_date = {
            _iso_date(r["trade_date"]): {
                "main_net_inflow": _safe_float(r["main_net_inflow"]),
                "inflow_amount": _safe_float(r["inflow_amount"]),
                "outflow_amount": _safe_float(r["outflow_amount"]),
            }
            for r in agg_rows
        }

        top_rows = db.execute(
            text(
                """
                SELECT
                    board_code,
                    (array_agg(board_name ORDER BY trade_date DESC))[1] AS board_name,
                    SUM(main_net_inflow) AS window_net
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND board_kind = :kind
                  AND trade_date >= CAST(:start_d AS date)
                  AND trade_date <= CAST(:end_d AS date)
                GROUP BY board_code
                HAVING SUM(main_net_inflow) IS NOT NULL
                ORDER BY SUM(main_net_inflow) DESC NULLS LAST
                LIMIT :top_n
                """
            ),
            {
                "src": src,
                "kind": kind,
                "start_d": start_date,
                "end_d": end_date,
                "top_n": int(top_n),
            },
        ).mappings().all()

        top_codes = [str(r["board_code"]) for r in top_rows if r.get("board_code")]
        series_by_code: Dict[str, Dict[str, Optional[float]]] = {
            c: {} for c in top_codes
        }
        if top_codes:
            daily_sql = text(
                """
                SELECT board_code, trade_date, main_net_inflow
                FROM board_fund_flow_daily
                WHERE board_code_source = :src
                  AND board_kind = :kind
                  AND trade_date >= CAST(:start_d AS date)
                  AND trade_date <= CAST(:end_d AS date)
                  AND board_code IN :codes
                """
            ).bindparams(bindparam("codes", expanding=True))
            daily_rows = db.execute(
                daily_sql,
                {
                    "src": src,
                    "kind": kind,
                    "start_d": start_date,
                    "end_d": end_date,
                    "codes": top_codes,
                },
            ).mappings().all()
            for r in daily_rows:
                code = str(r["board_code"])
                if code not in series_by_code:
                    continue
                series_by_code[code][_iso_date(r["trade_date"])] = _safe_float(
                    r["main_net_inflow"]
                )

        top_entities: List[Dict[str, Any]] = []
        for r in top_rows:
            code = str(r["board_code"])
            by_date = series_by_code.get(code, {})
            top_entities.append(
                {
                    "board_code": code,
                    "board_name": r["board_name"],
                    "window_net": _safe_float(r["window_net"]),
                    "main_net_inflow": [by_date.get(d) for d in dates],
                }
            )

        return {
            "success": True,
            "data": {
                "period": key,
                "period_label": period_meta["label"],
                "board_kind": kind,
                "board_code_source": src,
                "trend_days": int(trend_days),
                "start_date": start_date,
                "end_date": end_date,
                "dates": dates,
                "aggregate": {
                    "main_net_inflow": [
                        (agg_by_date.get(d) or {}).get("main_net_inflow") for d in dates
                    ],
                    "inflow_amount": [
                        (agg_by_date.get(d) or {}).get("inflow_amount") for d in dates
                    ],
                    "outflow_amount": [
                        (agg_by_date.get(d) or {}).get("outflow_amount") for d in dates
                    ],
                },
                "top_entities": top_entities,
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询板块资金流趋势失败: {e}"},
            status_code=500,
        )


def _resolve_constituent_board_code(
    db: Session,
    *,
    board_kind: str,
    board_code: str,
    board_code_source: str,
) -> Dict[str, Any]:
    """
    解析同花顺板块对应的成分股表 board_code。
    优先使用本板码下已有成分；否则经 industry_board_code_map 映射到东财板码。
    """
    kind = board_kind
    code = board_code
    src = board_code_source
    cons_table = (
        "industry_board_constituents"
        if kind == "industry"
        else "concept_board_constituents"
    )
    basic_table = (
        "industry_board_basic_info"
        if kind == "industry"
        else "concept_board_basic_info"
    )

    board_name = None
    name_row = db.execute(
        text(
            f"""
            SELECT board_name
            FROM {basic_table}
            WHERE TRIM(board_code) = :code
              AND COALESCE(NULLIF(TRIM(board_code_source), ''), :src) = :src
            LIMIT 1
            """
        ),
        {"code": code, "src": src},
    ).fetchone()
    if name_row and name_row[0]:
        board_name = str(name_row[0]).strip()
    if not board_name:
        flow_name = db.execute(
            text(
                """
                SELECT board_name
                FROM board_fund_flow_daily
                WHERE board_kind = :kind
                  AND board_code_source = :src
                  AND board_code = :code
                ORDER BY trade_date DESC
                LIMIT 1
                """
            ),
            {"kind": kind, "src": src, "code": code},
        ).scalar()
        if flow_name:
            board_name = str(flow_name).strip()

    has_direct = db.execute(
        text(
            f"""
            SELECT 1 FROM {cons_table}
            WHERE board_code = :code
            LIMIT 1
            """
        ),
        {"code": code},
    ).fetchone()
    if has_direct:
        return {
            "board_code": code,
            "cons_board_code": code,
            "board_name": board_name or code,
            "mapped_em_board_code": None,
        }

    mapped = db.execute(
        text(
            """
            SELECT em_board_code
            FROM industry_board_code_map
            WHERE board_kind = :kind
              AND ths_board_code = :code
              AND is_active IS TRUE
            LIMIT 1
            """
        ),
        {"kind": kind, "code": code},
    ).scalar()
    em_code = str(mapped).strip() if mapped else None
    cons_code = em_code or code
    return {
        "board_code": code,
        "cons_board_code": cons_code,
        "board_name": board_name or code,
        "mapped_em_board_code": em_code,
    }


@router.get("/constituents")
async def get_board_constituent_fund_flow(
    board_code: str = Query(..., description="板块代码（同花顺口径）"),
    board_kind: str = Query(..., description="industry | concept"),
    period: str = Query("day", description="day|week|month（近1/5/20 个交易日净流入合计）"),
    board_code_source: str = Query(DEFAULT_BOARD_CODE_SOURCE),
    trade_date: Optional[str] = Query(
        None, description="锚定交易日 YYYY-MM-DD；默认取个股资金流库内最新日"
    ),
    db: Session = Depends(get_db),
):
    """
    板块内成分股资金流向（同花顺）：成分表 × stock_fund_flow_daily 按日/周/月汇总。
    返回按净流入升序（弱→强），金额单位：元。
    """
    key = (period or "day").strip().lower()
    meta = _BOARD_FUND_FLOW_RANK_PERIODS.get(key)
    if not meta:
        return JSONResponse(
            {"success": False, "message": "period 应为 day / week / month"},
            status_code=400,
        )
    kind = (board_kind or "").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 应为 industry 或 concept"},
            status_code=400,
        )
    code = str(board_code or "").strip()
    if not code:
        return JSONResponse(
            {"success": False, "message": "缺少 board_code"}, status_code=400
        )
    src = str(board_code_source or DEFAULT_BOARD_CODE_SOURCE).strip() or DEFAULT_BOARD_CODE_SOURCE
    n_days = int(meta["days"])
    anchor = None
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
            anchor = trade_date
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )

    cons_table = (
        "industry_board_constituents"
        if kind == "industry"
        else "concept_board_constituents"
    )

    def _empty(
        *,
        end: Optional[str] = None,
        board_name: Optional[str] = None,
        cons_board_code: Optional[str] = None,
        mapped_em: Optional[str] = None,
        member_count: int = 0,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "period": key,
            "period_label": meta["label"],
            "board_kind": kind,
            "board_code": code,
            "board_code_source": src,
            "board_name": board_name,
            "cons_board_code": cons_board_code,
            "mapped_em_board_code": mapped_em,
            "trade_days": n_days,
            "start_date": None,
            "end_date": end,
            "member_count": member_count,
            "items": [],
            "count": 0,
            "source": "ths",
        }
        if message:
            payload["message"] = message
        return {"success": True, "data": payload}

    try:
        resolved = _resolve_constituent_board_code(
            db, board_kind=kind, board_code=code, board_code_source=src
        )
        cons_code = resolved["cons_board_code"]
        board_name = resolved["board_name"]
        mapped_em = resolved["mapped_em_board_code"]

        member_count = int(
            db.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM {cons_table}
                    WHERE board_code = :cons_code
                    """
                ),
                {"cons_code": cons_code},
            ).scalar()
            or 0
        )
        if member_count <= 0:
            return _empty(
                board_name=board_name,
                cons_board_code=cons_code,
                mapped_em=mapped_em,
                member_count=0,
                message="该板块暂无成分股（请先同步同花顺成分股）",
            )

        if not anchor:
            latest = db.execute(
                text("SELECT MAX(trade_date) FROM stock_fund_flow_daily")
            ).scalar()
            if latest is None:
                return _empty(
                    board_name=board_name,
                    cons_board_code=cons_code,
                    mapped_em=mapped_em,
                    member_count=member_count,
                    message="暂无个股资金流（请先日采同花顺资金流向）",
                )
            anchor = (
                latest.isoformat()[:10]
                if hasattr(latest, "isoformat")
                else str(latest)[:10]
            )

        # stock_fund_flow_daily.trade_date 为 varchar(YYYY-MM-DD)，须字符串比较（勿 CAST date）
        date_rows = db.execute(
            text(
                """
                SELECT DISTINCT trade_date
                FROM stock_fund_flow_daily
                WHERE trade_date <= :anchor
                ORDER BY trade_date DESC
                LIMIT :n_days
                """
            ),
            {"anchor": anchor, "n_days": n_days},
        ).fetchall()
        trade_dates = [
            (r[0].isoformat()[:10] if hasattr(r[0], "isoformat") else str(r[0])[:10])
            for r in date_rows
            if r and r[0] is not None
        ]
        if not trade_dates:
            return _empty(
                end=anchor,
                board_name=board_name,
                cons_board_code=cons_code,
                mapped_em=mapped_em,
                member_count=member_count,
                message="锚定日附近无个股资金流数据",
            )

        start_date = min(trade_dates)
        end_date = max(trade_dates)
        rows = db.execute(
            text(
                f"""
                SELECT
                    c.stock_code AS code,
                    COALESCE(
                        (array_agg(f.name ORDER BY f.trade_date DESC)
                            FILTER (WHERE f.name IS NOT NULL AND TRIM(f.name) <> ''))[1],
                        NULLIF(TRIM(MAX(c.stock_name)), ''),
                        c.stock_code
                    ) AS name,
                    SUM(f.net_amount) AS net_amount,
                    SUM(f.inflow_amount) AS inflow_amount,
                    SUM(f.outflow_amount) AS outflow_amount,
                    SUM(f.turnover_amount) AS turnover_amount,
                    COUNT(f.trade_date)::int AS days_count,
                    (array_agg(f.change_percent ORDER BY f.trade_date DESC)
                        FILTER (WHERE f.change_percent IS NOT NULL))[1] AS change_percent
                FROM {cons_table} c
                LEFT JOIN stock_fund_flow_daily f
                  ON f.code = c.stock_code
                 AND f.trade_date >= :start_d
                 AND f.trade_date <= :end_d
                WHERE c.board_code = :cons_code
                GROUP BY c.stock_code
                ORDER BY SUM(f.net_amount) ASC NULLS LAST, c.stock_code
                """
            ),
            {
                "cons_code": cons_code,
                "start_d": start_date,
                "end_d": end_date,
            },
        ).mappings().all()

        items: List[Dict[str, Any]] = []
        for r in rows:
            items.append(
                {
                    "code": str(r["code"] or "").strip(),
                    "name": str(r["name"] or r["code"] or "").strip(),
                    "net_amount": _safe_float(r["net_amount"]),
                    "inflow_amount": _safe_float(r["inflow_amount"]),
                    "outflow_amount": _safe_float(r["outflow_amount"]),
                    "turnover_amount": _safe_float(r["turnover_amount"]),
                    "change_percent": _safe_float(r["change_percent"]),
                    "days_count": int(r["days_count"] or 0),
                }
            )

        return {
            "success": True,
            "data": {
                "period": key,
                "period_label": meta["label"],
                "board_kind": kind,
                "board_code": code,
                "board_code_source": src,
                "board_name": board_name,
                "cons_board_code": cons_code,
                "mapped_em_board_code": mapped_em,
                "trade_days": n_days,
                "start_date": start_date,
                "end_date": end_date,
                "member_count": member_count,
                "items": items,
                "count": len(items),
                "source": "ths",
            },
        }
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": f"查询板块成分股资金流失败: {e}"},
            status_code=500,
        )


@router.post("/daily/collect")
async def trigger_board_fund_flow_collect(
    background_tasks: BackgroundTasks,
    trade_date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD，默认今天"),
    sync: bool = Query(False, description="true 则同步执行"),
):
    """触发板块资金流日采。"""
    if trade_date:
        try:
            datetime.strptime(trade_date, "%Y-%m-%d")
        except ValueError:
            return JSONResponse(
                {"success": False, "message": "trade_date 格式应为 YYYY-MM-DD"},
                status_code=400,
            )
    if sync:
        try:
            result = collect_board_fund_flow_daily(trade_date=trade_date)
            return {"success": True, "data": result}
        except Exception as e:
            return JSONResponse(
                {"success": False, "message": f"采集失败: {e}"}, status_code=500
            )
    background_tasks.add_task(collect_board_fund_flow_daily, trade_date)
    return {
        "success": True,
        "message": "板块资金流采集已在后台启动",
        "data": {"trade_date": trade_date or datetime.now().strftime("%Y-%m-%d")},
    }
