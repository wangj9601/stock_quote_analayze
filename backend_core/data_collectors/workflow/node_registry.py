"""采集流程节点注册表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from backend_core.data_collectors.workflow.adapters import (
    exec_cn_annual,
    exec_cn_historical,
    exec_cn_index_realtime,
    exec_cn_index_historical,
    exec_cn_industry_board,
    exec_cn_board_historical,
    exec_cn_industry_constituents,
    exec_cn_monthly,
    exec_cn_quarterly,
    exec_cn_realtime,
    exec_cn_semiannual,
    exec_cn_turnover,
    exec_cn_weekly,
    exec_etf_historical,
    exec_etf_realtime,
    exec_gms_cn,
    exec_gms_hk,
    exec_hk_annual,
    exec_hk_historical,
    exec_hk_index_historical,
    exec_hk_index_realtime,
    exec_hk_monthly,
    exec_hk_quarterly,
    exec_hk_realtime,
    exec_hk_semiannual,
    exec_hk_weekly,
    exec_market_news,
    exec_rpe_cn,
    exec_fina_indicator_cn,
    exec_index_daily_cn,
    exec_rs_rating_cn,
    exec_sbbr_cn,
    exec_stock_shares,
    exec_triple_volume_scan,
    exec_urt_cn,
    exec_urt_hk,
    exec_watchlist_history,
)
from backend_core.data_collectors.workflow.adapters.api_nodes import (
    exec_cn_historical_akshare,
    exec_cn_realtime_api,
    exec_noop_indicators,
)
from backend_core.data_collectors.workflow.context import NodeResult, WorkflowContext

Executor = Callable[[WorkflowContext], NodeResult]


@dataclass
class CollectionNodeDef:
    key: str
    name: str
    category: str  # cn / hk / etf / agg / strategy / news / api / maintain
    executor: Executor
    param_schema: Dict[str, Any] = field(default_factory=dict)
    supports_scheduled: bool = True
    default_params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


_EMPTY_SCHEMA: Dict[str, Any] = {"type": "object", "properties": {}}

_DATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "start_date": {"type": "string", "title": "开始日期", "format": "date"},
        "end_date": {"type": "string", "title": "结束日期", "format": "date"},
        "stock_codes": {
            "type": "string",
            "title": "股票代码（可选，每行或逗号分隔）",
        },
        "force_update": {"type": "boolean", "title": "强制更新", "default": False},
        "full_collection_mode": {"type": "boolean", "title": "全量模式", "default": False},
        "indicators": {
            "type": "array",
            "title": "技术指标",
            "items": {"type": "string", "enum": ["MA", "MACD", "KDJ", "RSI", "BOLL", "MAVOL"]},
        },
    },
}


def _n(
    key: str,
    name: str,
    category: str,
    executor: Executor,
    *,
    supports_scheduled: bool = True,
    param_schema: Optional[Dict[str, Any]] = None,
    description: str = "",
) -> CollectionNodeDef:
    return CollectionNodeDef(
        key=key,
        name=name,
        category=category,
        executor=executor,
        param_schema=param_schema or _EMPTY_SCHEMA,
        supports_scheduled=supports_scheduled,
        description=description,
    )


NODE_DEFS: List[CollectionNodeDef] = [
    # A股
    _n("cn_realtime", "A股实时行情", "cn", exec_cn_realtime, description="AkShare A股实时"),
    _n("cn_historical", "A股日K（实时表/Tushare）", "cn", exec_cn_historical),
    _n("cn_index_realtime", "A股指数实时", "cn", exec_cn_index_realtime),
    _n("cn_index_historical", "A股指数历史归档", "cn", exec_cn_index_historical),
    _n("cn_industry_board", "行业板块实时", "cn", exec_cn_industry_board),
    _n("cn_board_historical", "同花顺板块历史归档", "cn", exec_cn_board_historical),
    _n("cn_industry_constituents", "行业板块成分股", "maintain", exec_cn_industry_constituents),
    _n("cn_turnover", "历史换手率", "cn", exec_cn_turnover),
    # 港股
    _n("hk_realtime", "港股实时行情", "hk", exec_hk_realtime),
    _n("hk_historical", "港股日K", "hk", exec_hk_historical),
    _n("hk_index_realtime", "港股指数实时", "hk", exec_hk_index_realtime),
    _n("hk_index_historical", "港股指数历史归档", "hk", exec_hk_index_historical),
    # ETF
    _n("etf_realtime", "ETF实时", "etf", exec_etf_realtime),
    _n("etf_historical", "ETF历史", "etf", exec_etf_historical),
    # 聚合
    _n("cn_weekly", "A股周K生成", "agg", exec_cn_weekly),
    _n("cn_monthly", "A股月K生成", "agg", exec_cn_monthly),
    _n("cn_quarterly", "A股季K生成", "agg", exec_cn_quarterly),
    _n("cn_semiannual", "A股半年K生成", "agg", exec_cn_semiannual),
    _n("cn_annual", "A股年K生成", "agg", exec_cn_annual),
    _n("hk_weekly", "港股周K生成", "agg", exec_hk_weekly),
    _n("hk_monthly", "港股月K生成", "agg", exec_hk_monthly),
    _n("hk_quarterly", "港股季K生成", "agg", exec_hk_quarterly),
    _n("hk_semiannual", "港股半年K生成", "agg", exec_hk_semiannual),
    _n("hk_annual", "港股年K生成", "agg", exec_hk_annual),
    # 策略
    _n("gms_signals_cn", "GMS信号预计算(A股)", "strategy", exec_gms_cn),
    _n("gms_signals_hk", "GMS信号预计算(港股)", "strategy", exec_gms_hk),
    _n("urt_signals_cn", "URT信号预计算(A股)", "strategy", exec_urt_cn),
    _n("urt_signals_hk", "URT信号预计算(港股)", "strategy", exec_urt_hk),
    _n("sbbr_signals_cn", "SBBR信号预计算(A股)", "strategy", exec_sbbr_cn),
    _n("rpe_signals_cn", "RPE信号预计算(A股)", "strategy", exec_rpe_cn),
    _n("rs_rating_cn", "A股相对强度RS预计算", "strategy", exec_rs_rating_cn),
    _n("triple_volume_scan", "3倍量爆量扫描", "strategy", exec_triple_volume_scan),
    _n(
        "fina_indicator_cn",
        "A股财务指标采集",
        "cn",
        exec_fina_indicator_cn,
        description="Tushare/AkShare fina → stock_fina_indicator（CAN SLIM C/A，可回退）",
    ),
    _n(
        "index_daily_cn",
        "A股指数日线采集",
        "cn",
        exec_index_daily_cn,
        description="AkShare/Tushare → index_historical_quotes（CAN SLIM M，默认优先 AkShare）",
    ),
    # 维护/新闻
    _n("stock_shares_update", "股本同步", "maintain", exec_stock_shares),
    _n("market_news", "市场新闻采集", "news", exec_market_news),
    _n("watchlist_history", "自选股历史采集", "cn", exec_watchlist_history),
    # API 型（偏手动）
    _n(
        "cn_historical_akshare",
        "A股历史(AkShare按需)",
        "api",
        exec_cn_historical_akshare,
        supports_scheduled=False,
        param_schema=_DATE_SCHEMA,
        description="带日期/股票参数的管理端历史采集",
    ),
    _n(
        "cn_realtime_api",
        "A股实时(按需节点)",
        "api",
        exec_cn_realtime_api,
        supports_scheduled=True,
    ),
    _n(
        "cn_indicators",
        "技术指标占位",
        "api",
        exec_noop_indicators,
        supports_scheduled=False,
        param_schema={
            "type": "object",
            "properties": {
                "indicators": {
                    "type": "array",
                    "title": "技术指标",
                    "items": {
                        "type": "string",
                        "enum": ["MA", "MACD", "KDJ", "RSI", "BOLL", "MAVOL"],
                    },
                }
            },
        },
    ),
]

_BY_KEY: Dict[str, CollectionNodeDef] = {n.key: n for n in NODE_DEFS}


def get_node(key: str) -> Optional[CollectionNodeDef]:
    return _BY_KEY.get(key)


def list_node_defs() -> List[CollectionNodeDef]:
    return list(NODE_DEFS)


def list_nodes_meta() -> List[Dict[str, Any]]:
    """供前端节点库展示（不含 executor）。"""
    return [
        {
            "key": n.key,
            "name": n.name,
            "category": n.category,
            "param_schema": n.param_schema,
            "supports_scheduled": n.supports_scheduled,
            "default_params": n.default_params,
            "description": n.description,
        }
        for n in NODE_DEFS
    ]
