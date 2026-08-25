"""API 型节点：带日期/股票参数的按需采集（供手动流程使用）。"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend_core.data_collectors.workflow.context import NodeResult, WorkflowContext

logger = logging.getLogger(__name__)


def _parse_codes(params: dict) -> Optional[List[str]]:
    raw = params.get("stock_codes")
    if raw is None:
        return None
    if isinstance(raw, list):
        return [str(c).strip() for c in raw if str(c).strip()]
    text = str(raw).strip()
    if not text:
        return None
    parts = []
    for line in text.replace(",", "\n").splitlines():
        c = line.strip()
        if c:
            parts.append(c)
    return parts or None


def exec_cn_historical_akshare(ctx: WorkflowContext) -> NodeResult:
    """通过 AkShare 采集 A 股历史（可指定日期与股票）。"""
    ctx.merge_dates_from_params()
    try:
        from backend_api.database import SessionLocal
        from backend_api.stock.data_collection_api import AkshareDataCollector

        db = SessionLocal()
        try:
            collector = AkshareDataCollector(db)
            codes = _parse_codes(ctx.node_params) or _parse_codes(ctx.params)
            indicators = ctx.node_params.get("indicators") or ctx.params.get("indicators")
            force_update = bool(
                ctx.node_params.get("force_update") or ctx.params.get("force_update")
            )
            full_mode = bool(
                ctx.node_params.get("full_collection_mode")
                or ctx.params.get("full_collection_mode")
            )
            result = collector.collect_historical_data(
                start_date=ctx.start_date,
                end_date=ctx.end_date,
                stock_codes=codes,
                full_collection_mode=full_mode,
                force_update=force_update,
                indicators=indicators,
                market="CN",
            )
            return NodeResult.ok("AkShare A股历史采集完成", data={"result": result})
        finally:
            db.close()
    except Exception as e:
        logger.exception("cn_historical_akshare 失败")
        return NodeResult.fail(str(e), "AkShare A股历史采集失败")


def exec_cn_realtime_api(ctx: WorkflowContext) -> NodeResult:
    """按需 A 股实时采集（单股或全量参数）。"""
    try:
        from backend_core.config.config import DATA_COLLECTORS
        from backend_core.data_collectors.akshare.realtime import AkshareRealtimeQuoteCollector

        collector = AkshareRealtimeQuoteCollector(DATA_COLLECTORS.get("akshare", {}))
        ok = collector.collect_quotes()
        if ok:
            return NodeResult.ok("A股实时(API节点)完成")
        return NodeResult.fail("采集返回失败", "A股实时(API节点)失败")
    except Exception as e:
        logger.exception("cn_realtime_api 失败")
        return NodeResult.fail(str(e))


def exec_noop_indicators(ctx: WorkflowContext) -> NodeResult:
    """占位：指标计算可由历史采集节点的 indicators 参数完成。"""
    indicators = ctx.node_params.get("indicators") or ctx.params.get("indicators") or []
    return NodeResult.ok(
        "指标节点占位完成（请在历史采集节点配置 indicators）",
        data={"indicators": indicators},
    )
