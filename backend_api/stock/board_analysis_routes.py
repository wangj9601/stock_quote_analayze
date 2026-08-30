# -*- coding: utf-8 -*-
"""分析频道：板块多策略信号聚合与一键加入观察。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user, get_current_user_optional
from backend_api.database import get_db
from backend_api.models import User
from backend_api.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["板块分析"])


class BoardObserveRequest(BaseModel):
    strategy: str = Field(..., description="gms|urt|sbbr|rpe")
    code: str = Field(..., min_length=1, max_length=20)
    name: Optional[str] = None
    market: Optional[str] = "CN"
    signal_date: Optional[str] = None
    note: Optional[str] = None
    snapshot: Optional[Dict[str, Any]] = None


class GmsStrategyWatchlistStockItem(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: Optional[str] = None
    market: Optional[str] = "CN"
    role: Optional[str] = Field(None, description="leader|mid，仅备注用")


class GmsStrategyWatchlistAddRequest(BaseModel):
    """分析频道：将板块龙头/中军写入 GMS 策略观察股（gms_strategy_version_stocks）。"""

    stocks: List[GmsStrategyWatchlistStockItem] = Field(
        ..., min_length=1, max_length=50, description="待加入股票，最多 50 只"
    )
    remark: Optional[str] = Field(None, description="写入观察股备注；默认分析频道口径")
    board_code: Optional[str] = None
    board_name: Optional[str] = None


_GMS_WATCHLIST_PERMS = (
    "channel.analyze.tab.board.btn.gms_watchlist",
    "channel.analyze.tab.leader_mid.btn.gms_watchlist",
    # 兼容已有「加入交易观察」权限（交易观察侧已会同步策略观察股）
    "channel.analyze.tab.board.btn.observe",
)


def _require_gms_strategy_watchlist_perm(db: Session, user: User) -> None:
    from backend_api.permissions import get_effective_permission_codes

    codes = set(get_effective_permission_codes(db, user))
    if not codes.intersection(_GMS_WATCHLIST_PERMS):
        raise HTTPException(
            status_code=403,
            detail="无权限加入 GMS 策略观察股",
        )


def _parse_strategies(raw: Optional[str]) -> List[str]:
    if not raw or not str(raw).strip():
        return ["gms", "urt", "sbbr", "rpe"]
    parts = [p.strip().lower() for p in str(raw).split(",") if p.strip()]
    allowed = {"gms", "urt", "sbbr", "rpe"}
    out = [p for p in parts if p in allowed]
    return out or ["gms", "urt", "sbbr", "rpe"]


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _norm_code(code: str) -> str:
    c = str(code or "").strip()
    if c.isdigit() and len(c) <= 6:
        return c.zfill(6)
    return c


@router.get("/board-signals")
def get_board_signals(
    board_kind: str = Query(..., description="industry | concept"),
    board_code: Optional[str] = Query(
        None, description="单板代码；与 board_codes 二选一"
    ),
    board_codes: Optional[str] = Query(
        None, description="多板代码，逗号分隔；优先于 board_code"
    ),
    board_code_source: str = Query("tonghuashun"),
    board_name: Optional[str] = Query(None),
    strategies: Optional[str] = Query(
        None, description="逗号分隔：gms,urt,sbbr,rpe；默认全部"
    ),
    db: Session = Depends(get_db),
    _user: Optional[User] = Depends(get_current_user_optional),
):
    """按行业/概念板聚合四策略命中，并附买卖建议与 Fib/Pivot 参考价。

    支持 board_codes 多选（成分并集跑策略）。
    """
    kind = (board_kind or "").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 须为 industry 或 concept"},
            status_code=400,
        )
    codes_list = [
        p.strip()
        for p in str(board_codes or "").split(",")
        if p and str(p).strip()
    ]
    single = (board_code or "").strip()
    if not codes_list and not single:
        return JSONResponse(
            {"success": False, "message": "请提供 board_code 或 board_codes"},
            status_code=400,
        )
    try:
        from backend_core.analysis.board_signals import collect_board_signals

        data = collect_board_signals(
            db,
            board_kind=kind,
            board_code="" if codes_list else single,
            board_codes=codes_list or None,
            board_code_source=board_code_source,
            board_name=board_name,
            strategies=_parse_strategies(strategies),
        )
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("board-signals failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"板块分析失败: {e}"},
            status_code=500,
        )


@router.get("/rs-rating")
def get_rs_rating(
    code: Optional[str] = Query(None, description="股票代码或名称"),
    stock_code: Optional[str] = Query(None, description="同 code，兼容别名"),
    date: Optional[str] = Query(None, description="基准日 YYYY-MM-DD，可选"),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.stock_ai")),
):
    """个股 IBD 风格相对强度 RS Rating（读预计算表，不现算全市场）。"""
    raw = (code or stock_code or "").strip()
    if not raw:
        return JSONResponse(
            {"success": False, "message": "请提供股票代码或名称"},
            status_code=400,
        )
    try:
        from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier
        from backend_core.indicators.rs_rating.service import get_rs_rating_for_stock

        resolved = resolve_levels_stock_identifier(db, raw)
        status = resolved.get("status")
        if status == "ambiguous":
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "匹配到多只股票，请选择",
                    "candidates": resolved.get("candidates") or [],
                },
                status_code=400,
            )
        if status == "not_found" or not resolved.get("code"):
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "未找到匹配股票",
                },
                status_code=404,
            )
        # 港股暂不支持
        market = (resolved.get("market") or resolved.get("market_type") or "CN").upper()
        code_n = str(resolved["code"]).strip()
        if len(code_n) != 6 or not code_n.isdigit() or market == "HK":
            return JSONResponse(
                {
                    "success": False,
                    "message": "相对强度 RS Rating 暂仅支持 A 股",
                    "reason": "market_unsupported",
                },
                status_code=400,
            )
        result = get_rs_rating_for_stock(db, code_n, asof=date)
        if not result.get("success") and result.get("reason") == "not_found":
            return JSONResponse(
                {
                    "success": False,
                    "message": result.get("message") or "尚未预计算",
                    "reason": result.get("reason"),
                    "code": code_n,
                    "name": resolved.get("name"),
                    "data": None,
                },
                status_code=404,
            )
        data = result.get("data") or {}
        if resolved.get("name") and "name" not in data:
            data["name"] = resolved.get("name")
        return {
            "success": True,
            "message": result.get("message") or "ok",
            "reason": result.get("reason"),
            "data": data,
        }
    except Exception as e:
        logger.exception("rs-rating 查询失败: %s", e)
        return JSONResponse(
            {"success": False, "message": str(e)},
            status_code=500,
        )


@router.get("/rs-rating/history")
def get_rs_rating_history(
    code: Optional[str] = Query(None, description="股票代码或名称"),
    stock_code: Optional[str] = Query(None, description="同 code，兼容别名"),
    start_date: Optional[str] = Query(None, description="起始日 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日 YYYY-MM-DD"),
    limit: int = Query(120, ge=1, le=500, description="最多返回条数"),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.stock_ai")),
):
    """个股 RS Rating 历史序列（读预计算表，日期降序）。"""
    raw = (code or stock_code or "").strip()
    if not raw:
        return JSONResponse(
            {"success": False, "message": "请提供股票代码或名称"},
            status_code=400,
        )
    try:
        from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier
        from backend_core.indicators.rs_rating.service import list_rs_rating_history

        resolved = resolve_levels_stock_identifier(db, raw)
        status = resolved.get("status")
        if status == "ambiguous":
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "匹配到多只股票，请选择",
                    "candidates": resolved.get("candidates") or [],
                },
                status_code=400,
            )
        if status == "not_found" or not resolved.get("code"):
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "未找到匹配股票",
                },
                status_code=404,
            )
        code_n = str(resolved["code"]).strip()
        if len(code_n) != 6 or not code_n.isdigit():
            return JSONResponse(
                {
                    "success": False,
                    "message": "相对强度 RS Rating 暂仅支持 A 股",
                    "reason": "market_unsupported",
                },
                status_code=400,
            )
        result = list_rs_rating_history(
            db,
            code_n,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        if resolved.get("name") and not result.get("name"):
            result["name"] = resolved.get("name")
        return result
    except Exception as e:
        logger.exception("rs-rating history 查询失败: %s", e)
        return JSONResponse(
            {"success": False, "message": str(e)},
            status_code=500,
        )


class RsForcePrecomputeRequest(BaseModel):
    trade_date: Optional[str] = Field(
        None, description="单日 YYYY-MM-DD；缺省取行情最新交易日"
    )
    start_date: Optional[str] = Field(None, description="区间起点（需与 end_date 同用）")
    end_date: Optional[str] = Field(None, description="区间终点（需与 start_date 同用）")


@router.post("/rs-rating/precompute")
def post_rs_rating_force_precompute(
    body: RsForcePrecomputeRequest = Body(...),
    _perm: None = Depends(require_permission("channel.analyze.tab.stock_ai")),
):
    """强制重算指定交易日（或短区间）的全市场 RS 截面；异步任务。"""
    from backend_core.indicators.rs_rating.force_precompute import (
        resolve_force_trade_dates,
        start_precompute,
    )

    try:
        dates = resolve_force_trade_dates(
            trade_date=body.trade_date,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        task_id = start_precompute(dates)
        return {
            "success": True,
            "task_id": task_id,
            "trade_dates": dates,
            "message": (
                f"已启动全市场强制预计算（{len(dates)} 日）。"
                "RS 为截面排名，不可只算单票。"
            ),
        }
    except ValueError as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)
    except RuntimeError as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=409)
    except Exception as e:
        logger.exception("rs-rating force precompute 启动失败: %s", e)
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)


@router.get("/rs-rating/precompute/{task_id}")
def get_rs_rating_force_precompute(
    task_id: str,
    _perm: None = Depends(require_permission("channel.analyze.tab.stock_ai")),
):
    """查询强制预计算任务进度。"""
    from backend_core.indicators.rs_rating.force_precompute import get_task

    task = get_task(task_id)
    if not task:
        return JSONResponse(
            {"success": False, "message": "任务不存在或已过期"},
            status_code=404,
        )
    return {"success": True, "data": task}


@router.get("/multi-strategy-check")
def get_multi_strategy_check(
    code: Optional[str] = Query(None, description="股票代码或名称"),
    stock_code: Optional[str] = Query(None, description="同 code，兼容别名"),
    date: Optional[str] = Query(None, description="基准日 YYYY-MM-DD，可选"),
    strategies: Optional[str] = Query(
        None, description="逗号分隔：gms,urt,sbbr,rpe；默认全部"
    ),
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.stock_ai")),
):
    """个股四策略命中/得分聚合（对齐选股 scope=single 评估口径）。"""
    raw = (code or stock_code or "").strip()
    if not raw:
        return JSONResponse(
            {"success": False, "message": "请提供股票代码或名称"},
            status_code=400,
        )
    try:
        from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier
        from backend_core.analysis.stock_multi_strategy import (
            collect_stock_multi_strategy_check,
        )

        resolved = resolve_levels_stock_identifier(db, raw)
        status = resolved.get("status")
        if status == "ambiguous":
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "匹配到多只股票，请选择",
                    "candidates": resolved.get("candidates") or [],
                },
                status_code=400,
            )
        if status == "not_found" or not resolved.get("code"):
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "未找到匹配股票",
                    "candidates": [],
                },
                status_code=404,
            )
        data = collect_stock_multi_strategy_check(
            db,
            code=str(resolved["code"]),
            name=resolved.get("name") or "",
            date=date,
            strategies=_parse_strategies(strategies),
        )
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("multi-strategy-check failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"个股多策略分析失败: {e}"},
            status_code=500,
        )


class StockIntegratedTradePlanBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, description="股票代码")
    date: Optional[str] = Field(None, description="基准日 YYYY-MM-DD")
    snapshots: Optional[Dict[str, Any]] = Field(
        None,
        description="前端已拉取的分析快照：strategy/levels/pattern/swing/gann",
    )


@router.post("/stock-integrated-trade-plan")
def post_stock_integrated_trade_plan(
    body: StockIntegratedTradePlanBody,
    db: Session = Depends(get_db),
    _perm: None = Depends(require_permission("channel.analyze.tab.stock_ai")),
):
    """个股分析：整合四策略、结构位、形态、波段与江恩，输出短线/中长线交易策略。"""
    raw = (body.code or "").strip()
    if not raw:
        return JSONResponse(
            {"success": False, "message": "请提供股票代码"},
            status_code=400,
        )
    try:
        from backend_api.stock.stock_analysis_routes import resolve_levels_stock_identifier
        from backend_core.analysis.integrated_trade_plan import build_integrated_trade_plan
        from backend_core.analysis.stock_multi_strategy import collect_strategy_raw_rows

        resolved = resolve_levels_stock_identifier(db, raw)
        status = resolved.get("status")
        if status == "ambiguous":
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "匹配到多只股票，请选择",
                    "candidates": resolved.get("candidates") or [],
                },
                status_code=400,
            )
        if status == "not_found" or not resolved.get("code"):
            return JSONResponse(
                {
                    "success": False,
                    "message": resolved.get("message") or "未找到匹配股票",
                },
                status_code=404,
            )
        code_n = str(resolved["code"])
        trade_date = (str(body.date).strip()[:10] if body.date else None)

        snapshots = body.snapshots if isinstance(body.snapshots, dict) else {}
        strategy_pack = snapshots.get("strategy")
        if not isinstance(strategy_pack, dict) or not strategy_pack.get("summaries"):
            strategy_pack = collect_strategy_raw_rows(db, code=code_n, date=trade_date)

        ctx = {
            "meta": {
                "code": code_n,
                "name": resolved.get("name") or "",
                "trade_date": trade_date or strategy_pack.get("trade_date"),
            },
            "strategy_pack": strategy_pack,
            "levels": snapshots.get("levels"),
            "pattern": snapshots.get("pattern"),
            "swing": snapshots.get("swing"),
            "gann": snapshots.get("gann"),
        }
        plan = build_integrated_trade_plan(ctx)
        return {
            "success": True,
            "data": {
                "stock": {"code": code_n, "name": resolved.get("name") or ""},
                "trade_date": ctx["meta"].get("trade_date"),
                "plan": plan,
            },
        }
    except Exception as e:
        logger.exception("stock-integrated-trade-plan failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"综合交易策略合成失败: {e}"},
            status_code=500,
        )


@router.get("/leader-mid-signals")
def get_leader_mid_signals(
    board_kind: str = Query(..., description="industry | concept"),
    board_code: Optional[str] = Query(
        None, description="单板代码；all/全部=该类型下全部板块"
    ),
    board_codes: Optional[str] = Query(
        None, description="多板代码，逗号分隔；优先于 board_code"
    ),
    board_code_source: str = Query("tonghuashun"),
    board_name: Optional[str] = Query(None),
    strategies: Optional[str] = Query(
        None, description="逗号分隔：gms,urt,sbbr,rpe；默认全部"
    ),
    db: Session = Depends(get_db),
    _user: Optional[User] = Depends(get_current_user_optional),
):
    """板块龙头+中军在 GMS/URT/SBBR/RPE 上的命中矩阵。

    支持 board_codes 多选，或 board_code=all 汇总全部板块。
    """
    kind = (board_kind or "").strip().lower()
    if kind not in ("industry", "concept"):
        return JSONResponse(
            {"success": False, "message": "board_kind 须为 industry 或 concept"},
            status_code=400,
        )
    codes_list = [
        p.strip()
        for p in str(board_codes or "").split(",")
        if p and str(p).strip()
    ]
    single = (board_code or "").strip()
    if not codes_list and not single:
        return JSONResponse(
            {"success": False, "message": "请提供 board_code 或 board_codes"},
            status_code=400,
        )
    try:
        from backend_core.analysis.board_signals import collect_leader_mid_strategy_hits

        data = collect_leader_mid_strategy_hits(
            db,
            board_kind=kind,
            board_code="" if codes_list else single,
            board_codes=codes_list or None,
            board_code_source=board_code_source,
            board_name=board_name,
            strategies=_parse_strategies(strategies),
        )
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("leader-mid-signals failed")
        try:
            db.rollback()
        except Exception:
            pass
        return JSONResponse(
            {"success": False, "message": f"龙头中军分析失败: {e}"},
            status_code=500,
        )


@router.post("/board-signals/observe")
def add_board_signal_observe(
    body: BoardObserveRequest = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _perm: None = Depends(require_permission("channel.analyze.tab.board.btn.observe")),
):
    """一键加入对应策略交易观察池。"""
    strategy = (body.strategy or "").strip().lower()
    code = _norm_code(body.code)
    if not code:
        raise HTTPException(status_code=400, detail="股票代码无效")
    if strategy not in ("gms", "urt", "sbbr", "rpe"):
        raise HTTPException(status_code=400, detail="strategy 须为 gms/urt/sbbr/rpe")

    market = (body.market or "CN").strip().upper() or "CN"
    snap = dict(body.snapshot or {})
    if body.note:
        snap["analysis_note"] = body.note
    advice = snap.get("trade_advice") if isinstance(snap.get("trade_advice"), dict) else {}
    if advice.get("summary") and "analysis_note" not in snap:
        snap["analysis_note"] = advice.get("summary")

    sig_date = _parse_date(body.signal_date) or _parse_date(
        snap.get("search_date") or snap.get("signal_date") or snap.get("date")
    )
    if sig_date is None:
        sig_date = date.today()

    try:
        if strategy == "gms":
            return _add_gms(db, user, code, body.name, market, sig_date, snap)
        if strategy == "urt":
            return _add_urt(db, user, code, body.name, market, sig_date, snap)
        if strategy == "sbbr":
            return _add_sbbr(db, user, code, body.name, market, sig_date, snap)
        return _add_rpe(db, user, code, body.name, market, sig_date, snap)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("board observe failed")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"加入观察失败: {e}")


def _add_gms(db, user, code, name, market, sig_date, snap):
    from backend_api.gms_trade_observe_routes import attach_price_plan_to_snapshot
    from backend_api.services.gms_strategy_watchlist import ensure_gms_strategy_watchlist_stock
    from backend_api import trade_observe_service as svc

    ensure_gms_strategy_watchlist_stock(db, market=market, code=code, name=name)
    snapshot_with_plan = attach_price_plan_to_snapshot(
        db, snap, market=market, code=code, signal_date=sig_date
    )
    before_codes = set(svc.list_observe_codes(db, user.id, source=svc.SOURCE_GMS))
    row = svc.add_observe(
        db,
        user,
        source=svc.SOURCE_GMS,
        code=code,
        market=market,
        name=name,
        signal_date=sig_date,
        snapshot=snapshot_with_plan,
        extra={"key_focus_flag": False},
    )
    key = svc.code_key(market, code)
    duplicated = key in before_codes
    return {"success": True, "id": row.id, "duplicated": duplicated, "strategy": "gms"}


def _add_urt(db, user, code, name, market, sig_date, snap):
    from backend_api import trade_observe_service as svc

    before_codes = set(svc.list_observe_codes(db, user.id, source=svc.SOURCE_URT))
    row = svc.add_observe(
        db,
        user,
        source=svc.SOURCE_URT,
        code=code,
        market=market,
        name=name,
        signal_date=sig_date,
        snapshot=snap,
    )
    key = svc.code_key(market, code)
    duplicated = key in before_codes
    return {"success": True, "id": row.id, "duplicated": duplicated, "strategy": "urt"}


def _add_sbbr(db, user, code, name, market, sig_date, snap):
    from backend_api.models import SBBRTradeObserveStock

    existing = (
        db.query(SBBRTradeObserveStock)
        .filter(
            SBBRTradeObserveStock.user_id == user.id,
            SBBRTradeObserveStock.market == market,
            SBBRTradeObserveStock.code == code,
        )
        .first()
    )
    if existing:
        return {"success": True, "id": existing.id, "duplicated": True, "strategy": "sbbr"}
    row = SBBRTradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=name,
        signal_snapshot_json=snap,
        signal_date=sig_date,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "id": row.id, "strategy": "sbbr"}


def _add_rpe(db, user, code, name, market, sig_date, snap):
    from backend_api.models import RPETradeObserveStock
    from backend_api.rpe_routes import _ensure_rpe_trade_observe_schema

    _ensure_rpe_trade_observe_schema()
    existing = (
        db.query(RPETradeObserveStock)
        .filter(
            RPETradeObserveStock.user_id == user.id,
            RPETradeObserveStock.market == market,
            RPETradeObserveStock.code == code,
        )
        .first()
    )
    if existing:
        return {"success": True, "id": existing.id, "duplicated": True, "strategy": "rpe"}
    row = RPETradeObserveStock(
        user_id=user.id,
        market=market,
        code=code,
        name=name,
        signal_snapshot_json=snap,
        signal_date=sig_date,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "id": row.id, "strategy": "rpe"}


@router.post("/gms-strategy-watchlist/add")
def add_gms_strategy_watchlist_from_analysis(
    body: GmsStrategyWatchlistAddRequest = Body(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    将股票加入启用中的 GMS 策略观察股池（gms_strategy_version_stocks）。
    支持单只或多只；已存在则跳过，不另起存储。
    """
    _require_gms_strategy_watchlist_perm(db, user)
    from backend_api.services.gms_strategy_watchlist import (
        BOARD_ROLE_REMARK,
        add_gms_strategy_watchlist_stocks_batch,
    )

    remark = (body.remark or "").strip() or BOARD_ROLE_REMARK
    board_hint = (body.board_name or body.board_code or "").strip()
    if board_hint and BOARD_ROLE_REMARK in remark:
        remark = f"{BOARD_ROLE_REMARK}（{board_hint}）"

    stocks = [
        {
            "code": _norm_code(item.code),
            "name": item.name,
            "market": (item.market or "CN").strip().upper() or "CN",
            "role": item.role,
        }
        for item in body.stocks
    ]
    try:
        summary = add_gms_strategy_watchlist_stocks_batch(db, stocks, remark=remark)
        db.commit()
    except Exception as e:
        logger.exception("gms strategy watchlist add failed")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"加入 GMS 策略观察股失败: {e}")

    return {
        "success": True,
        "added": summary["added"],
        "skipped": summary["skipped"],
        "failed": summary["failed"],
        "total": summary["total"],
        "version_id": summary.get("version_id"),
        "items": summary["items"],
        "message": (
            f"新增 {summary['added']}，跳过 {summary['skipped']}，失败 {summary['failed']}"
        ),
    }
