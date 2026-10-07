# -*- coding: utf-8 -*-
"""环境间配置同步（本地 ↔ 生产）。

模块可细选到策略/表级；行情大数据量须带日期范围。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

MODULE_STRATEGY_CONFIGS = "strategy_configs"
MODULE_TRADE_OBSERVE = "trade_observe"
MODULE_STOCK_BASIC = "stock_basic"
MODULE_BOARD_DATA = "board_data"
MODULE_QUOTES = "quotes"
MODULE_FUND_FLOW = "fund_flow"
MODULE_COMPUTED_RESULTS = "computed_results"
MODULE_ADJ_FACTORS = "adj_factors"
MODULE_FINA_INDICATOR = "fina_indicator"
MODULE_PERMISSIONS_RESOURCES = "permissions_resources"

# —— 策略配置细项（与 strategy_configs.STRATEGY_TABLES 一致）——
RESOURCE_STRATEGY = [
    "gms_strategy_configs",
    "urt_strategy_configs",
    "rpe_strategy_configs",
    "sbbr_strategy_configs",
    "gms_runtime_config",
]

# —— 交易观察/正式细项（与 trade_observe items 键一致）——
RESOURCE_OBSERVE = [
    "gms_trade_observe_stocks",
    "gms_trade_observe_history",
    "gms_formal_trades",
    "urt_trade_observe_stocks",
    "urt_trade_observe_history",
    "urt_formal_trades",
    "rpe_trade_observe_stocks",
    "rpe_trade_observe_history",
    "rpe_formal_trades",
    "sbbr_trade_observe_stocks",
    "sbbr_formal_trades",
    "sbbr_reserve_box",
]

# —— 基础信息 ——
RESOURCE_BASIC = [
    "stock_basic_info",
    "stock_basic_info_hk",
]

# —— 板块 ——
RESOURCE_BOARD = [
    "industry_board_basic_info",
    "industry_board_constituents",
    "concept_board_basic_info",
    "concept_board_constituents",
    "index_board_basic_info",
    "index_board_constituents",
]

# —— 行情（须日期范围）——
RESOURCE_QUOTES = [
    "historical_quotes",
    "historical_quotes_hk",
]

# —— 个股资金流（须日期范围）——
RESOURCE_FUND_FLOW = [
    "stock_fund_flow_daily",
    "stock_fund_flow_daily_hk",
]

# —— 预计算 / 复盘结果（须日期范围；信号表建议先同步策略配置）——
RESOURCE_COMPUTED = [
    "rs_ratings",
    "gms_signal_trace",
    "urt_signal_trace",
    "csb_signal_trace",
    "sbbr_signal_trace",
    "rpe_signal_trace",
    "index_historical_quotes",
    "board_fund_flow_daily",
    "stock_zt_pool_daily",
    "market_daily_review",
    "market_daily_mainline_hits",
    "stock_recommend_brief",
]

# —— 复权因子（日期可选：不填=全库；填写则按 trade_date 过滤）——
RESOURCE_ADJ_FACTORS = [
    "stock_adj_factor",
]

# —— 财务指标（日期可选：不填=全库；填写则按报告期 end_date YYYYMMDD 过滤）——
RESOURCE_FINA = [
    "stock_fina_indicator",
]

# —— 权限与角色（不含用户及用户级覆盖）——
RESOURCE_PERMISSIONS = [
    "frontend_permissions",
    "frontend_roles",
    "role_permissions",
]

# 行情/资金流/预计算复盘必须带日期；复权因子/财务指标日期可选（不填全库）
DATE_RANGE_REQUIRED = (
    frozenset(RESOURCE_QUOTES)
    | frozenset(RESOURCE_FUND_FLOW)
    | frozenset(RESOURCE_COMPUTED)
)
DATE_RANGE_OPTIONAL = frozenset(RESOURCE_ADJ_FACTORS) | frozenset(RESOURCE_FINA)

ALL_RESOURCES = (
    RESOURCE_STRATEGY
    + RESOURCE_OBSERVE
    + RESOURCE_BASIC
    + RESOURCE_BOARD
    + RESOURCE_QUOTES
    + RESOURCE_FUND_FLOW
    + RESOURCE_COMPUTED
    + RESOURCE_ADJ_FACTORS
    + RESOURCE_FINA
    + RESOURCE_PERMISSIONS
)

# 未指定 modules 时的默认范围：不含基本信息/板块/行情（避免误拉大数据）
DEFAULT_RESOURCES = RESOURCE_STRATEGY + RESOURCE_OBSERVE

# bundle key → 细项资源（与 export_modules 产出的 bundles 键一致）
BUNDLE_RESOURCES: Dict[str, List[str]] = {
    MODULE_STRATEGY_CONFIGS: list(RESOURCE_STRATEGY),
    MODULE_TRADE_OBSERVE: list(RESOURCE_OBSERVE),
    MODULE_STOCK_BASIC: list(RESOURCE_BASIC),
    MODULE_BOARD_DATA: list(RESOURCE_BOARD),
    MODULE_QUOTES: list(RESOURCE_QUOTES),
    MODULE_FUND_FLOW: list(RESOURCE_FUND_FLOW),
    MODULE_COMPUTED_RESULTS: list(RESOURCE_COMPUTED),
    MODULE_ADJ_FACTORS: list(RESOURCE_ADJ_FACTORS),
    MODULE_FINA_INDICATOR: list(RESOURCE_FINA),
    MODULE_PERMISSIONS_RESOURCES: list(RESOURCE_PERMISSIONS),
}

GROUP_EXPAND: Dict[str, List[str]] = {
    MODULE_STRATEGY_CONFIGS: list(RESOURCE_STRATEGY),
    MODULE_TRADE_OBSERVE: list(RESOURCE_OBSERVE),
    # bundle 键别名：与 export/import 的 bundles 键对齐，避免只认细项名
    MODULE_STOCK_BASIC: list(RESOURCE_BASIC),
    MODULE_BOARD_DATA: list(RESOURCE_BOARD),
    MODULE_QUOTES: list(RESOURCE_QUOTES),
    MODULE_FUND_FLOW: list(RESOURCE_FUND_FLOW),
    MODULE_COMPUTED_RESULTS: list(RESOURCE_COMPUTED),
    MODULE_ADJ_FACTORS: list(RESOURCE_ADJ_FACTORS),
    MODULE_FINA_INDICATOR: list(RESOURCE_FINA),
    MODULE_PERMISSIONS_RESOURCES: list(RESOURCE_PERMISSIONS),
    "gms_config_all": [
        "gms_strategy_configs",
        "gms_runtime_config",
    ],
    "urt_config_all": ["urt_strategy_configs"],
    "rpe_config_all": ["rpe_strategy_configs"],
    "sbbr_config_all": ["sbbr_strategy_configs"],
    "gms_trade": [
        "gms_trade_observe_stocks",
        "gms_trade_observe_history",
        "gms_formal_trades",
    ],
    "urt_trade": [
        "urt_trade_observe_stocks",
        "urt_trade_observe_history",
        "urt_formal_trades",
    ],
    "rpe_trade": [
        "rpe_trade_observe_stocks",
        "rpe_trade_observe_history",
        "rpe_formal_trades",
    ],
    "sbbr_trade": [
        "sbbr_trade_observe_stocks",
        "sbbr_formal_trades",
        "sbbr_reserve_box",
    ],
    "basic_info": list(RESOURCE_BASIC),
    "board_info": list(RESOURCE_BOARD),
    # quotes / fund_flow / computed_results 已由 MODULE_* 覆盖
    "fund_info": list(RESOURCE_FUND_FLOW),
    "computed_info": list(RESOURCE_COMPUTED),
    "fina_info": list(RESOURCE_FINA),
    "permissions": list(RESOURCE_PERMISSIONS),
}

MODULE_CATALOG: List[Dict[str, Any]] = [
    {
        "group": "strategy",
        "name": "策略参数版本",
        "items": [
            {
                "code": "gms_strategy_configs",
                "name": "GMS 策略配置",
                "desc": "GMSStrategyConfig",
            },
            {
                "code": "gms_runtime_config",
                "name": "GMS 运行时配置",
                "desc": "GMSRuntimeConfig",
            },
            {
                "code": "urt_strategy_configs",
                "name": "URT 策略配置",
                "desc": "URTStrategyConfig",
            },
            {
                "code": "rpe_strategy_configs",
                "name": "RPE 策略配置",
                "desc": "RPEStrategyConfig",
            },
            {
                "code": "sbbr_strategy_configs",
                "name": "SBBR 策略配置",
                "desc": "SBBRStrategyConfig",
            },
        ],
    },
    {
        "group": "observe",
        "name": "交易观察 / 正式交易",
        "items": [
            {
                "code": "gms_trade_observe_stocks",
                "name": "GMS 观察股",
                "desc": "GmsTradeObserveStock",
            },
            {
                "code": "gms_trade_observe_history",
                "name": "GMS 观察历史",
                "desc": "GmsTradeObserveHistory",
            },
            {
                "code": "gms_formal_trades",
                "name": "GMS 正式交易",
                "desc": "GmsFormalTrade",
            },
            {
                "code": "urt_trade_observe_stocks",
                "name": "URT 观察股",
                "desc": "UrtTradeObserveStock",
            },
            {
                "code": "urt_trade_observe_history",
                "name": "URT 观察历史",
                "desc": "UrtTradeObserveHistory",
            },
            {
                "code": "urt_formal_trades",
                "name": "URT 正式交易",
                "desc": "UrtFormalTrade",
            },
            {
                "code": "rpe_trade_observe_stocks",
                "name": "RPE 观察股",
                "desc": "RPETradeObserveStock",
            },
            {
                "code": "rpe_trade_observe_history",
                "name": "RPE 观察历史",
                "desc": "RPETradeObserveHistory",
            },
            {
                "code": "rpe_formal_trades",
                "name": "RPE 正式交易",
                "desc": "RPEFormalTrade",
            },
            {
                "code": "sbbr_trade_observe_stocks",
                "name": "SBBR 观察股",
                "desc": "SBBRTradeObserveStock",
            },
            {
                "code": "sbbr_formal_trades",
                "name": "SBBR 正式交易",
                "desc": "SBBRFormalTrade",
            },
            {
                "code": "sbbr_reserve_box",
                "name": "SBBR 预留仓位",
                "desc": "SBBRReserveBox",
            },
        ],
    },
    {
        "group": "basic",
        "name": "股票基本信息",
        "items": [
            {
                "code": "stock_basic_info",
                "name": "A股基本信息",
                "desc": "StockBasicInfo 全表覆盖",
            },
            {
                "code": "stock_basic_info_hk",
                "name": "港股基本信息",
                "desc": "StockBasicInfoHK 全表覆盖",
            },
        ],
    },
    {
        "group": "board",
        "name": "板块信息",
        "items": [
            {
                "code": "industry_board_basic_info",
                "name": "行业板块基本信息",
                "desc": "industry_board_basic_info",
            },
            {
                "code": "industry_board_constituents",
                "name": "行业板块成分股",
                "desc": "industry_board_constituents",
            },
            {
                "code": "concept_board_basic_info",
                "name": "概念板块基本信息",
                "desc": "concept_board_basic_info",
            },
            {
                "code": "concept_board_constituents",
                "name": "概念板块成分股",
                "desc": "concept_board_constituents",
            },
            {
                "code": "index_board_basic_info",
                "name": "指数板块基本信息",
                "desc": "index_board_basic_info",
            },
            {
                "code": "index_board_constituents",
                "name": "指数板块成分股",
                "desc": "index_board_constituents",
            },
        ],
    },
    {
        "group": "quotes",
        "name": "行情数据（须指定日期范围）",
        "requires_date_range": True,
        "items": [
            {
                "code": "historical_quotes",
                "name": "A股历史行情",
                "desc": "HistoricalQuotes，按交易日区间",
                "requires_date_range": True,
            },
            {
                "code": "historical_quotes_hk",
                "name": "港股历史行情",
                "desc": "HistoricalQuotesHK，按交易日区间",
                "requires_date_range": True,
            },
        ],
    },
    {
        "group": "fund_flow",
        "name": "资金流数据（须指定日期范围）",
        "requires_date_range": True,
        "items": [
            {
                "code": "stock_fund_flow_daily",
                "name": "A股个股资金流",
                "desc": "stock_fund_flow_daily，按 trade_date 区间",
                "requires_date_range": True,
            },
            {
                "code": "stock_fund_flow_daily_hk",
                "name": "港股个股资金流",
                "desc": "stock_fund_flow_daily_hk，按 trade_date 区间",
                "requires_date_range": True,
            },
        ],
    },
    {
        "group": "computed",
        "name": "预计算与复盘（须指定日期范围）",
        "requires_date_range": True,
        "items": [
            {
                "code": "rs_ratings",
                "name": "A股相对强度RS",
                "desc": "rs_ratings；信号类建议先同步策略配置",
                "requires_date_range": True,
            },
            {
                "code": "gms_signal_trace",
                "name": "GMS信号预计算(A股)",
                "desc": "gms_signal_trace（CN）；按 config_name 对齐",
                "requires_date_range": True,
            },
            {
                "code": "urt_signal_trace",
                "name": "URT信号预计算",
                "desc": "urt_signal_trace；按 config_name 对齐",
                "requires_date_range": True,
            },
            {
                "code": "csb_signal_trace",
                "name": "CSB信号预计算(A股)",
                "desc": "csb_signal_trace；按 config_name 对齐",
                "requires_date_range": True,
            },
            {
                "code": "sbbr_signal_trace",
                "name": "SBBR信号预计算(A股)",
                "desc": "sbbr_signal_trace（CN）；按 config_name 对齐",
                "requires_date_range": True,
            },
            {
                "code": "rpe_signal_trace",
                "name": "RPE信号预计算(A股)",
                "desc": "rpe_signal_trace（CN）；按 config_name 对齐",
                "requires_date_range": True,
            },
            {
                "code": "index_historical_quotes",
                "name": "A股指数日线",
                "desc": "index_historical_quotes，按 trade_date",
                "requires_date_range": True,
            },
            {
                "code": "board_fund_flow_daily",
                "name": "板块资金流向历史",
                "desc": "board_fund_flow_daily，按 trade_date",
                "requires_date_range": True,
            },
            {
                "code": "stock_zt_pool_daily",
                "name": "东财涨停股池历史",
                "desc": "stock_zt_pool_daily，按 trade_date",
                "requires_date_range": True,
            },
            {
                "code": "stock_recommend_brief",
                "name": "个股推荐简报(日/周/月)",
                "desc": "stock_recommend_brief，按 asof_date",
                "requires_date_range": True,
            },
            {
                "code": "market_daily_review",
                "name": "每日复盘指标",
                "desc": "market_daily_review，按 trade_date",
                "requires_date_range": True,
            },
            {
                "code": "market_daily_mainline_hits",
                "name": "每日复盘主线命中",
                "desc": "market_daily_mainline_hits（建议与复盘指标同批）",
                "requires_date_range": True,
            },
        ],
    },
    {
        "group": "adj_factors",
        "name": "复权因子（日期可选，不填则全库）",
        "requires_date_range": False,
        "date_range_optional": True,
        "items": [
            {
                "code": "stock_adj_factor",
                "name": "复权因子（A股/港股）",
                "desc": "StockAdjFactor；A股6位/港股5位同表，按 source 隔离；不填日期=全表；填写则按 trade_date 区间（默认可跨约 11 年）",
                "requires_date_range": False,
                "date_range_optional": True,
            },
        ],
    },
    {
        "group": "fina",
        "name": "财务指标（日期可选，不填则全库）",
        "requires_date_range": False,
        "date_range_optional": True,
        "items": [
            {
                "code": "stock_fina_indicator",
                "name": "A股财务指标",
                "desc": "StockFinaIndicator（CAN SLIM C/A）；不填日期=全表；填写则按报告期 end_date（YYYYMMDD）落在区间内",
                "requires_date_range": False,
                "date_range_optional": True,
            },
        ],
    },
    {
        "group": "permissions",
        "name": "权限与角色",
        "items": [
            {
                "code": "frontend_permissions",
                "name": "权限资源树",
                "desc": "frontend_permissions 注册表/资源树（按 code upsert，不含用户级覆盖）",
            },
            {
                "code": "frontend_roles",
                "name": "角色定义",
                "desc": "frontend_roles（按 code upsert，不含用户-角色绑定）",
            },
            {
                "code": "role_permissions",
                "name": "角色-权限映射",
                "desc": "role_permissions；导入时按角色覆盖映射（建议与权限资源树一并勾选）",
            },
        ],
    },
]


def expand_modules(modules: Optional[Sequence[str]]) -> List[str]:
    """将组名/细项展开为细粒度资源列表（保序去重）。"""
    if not modules:
        return list(DEFAULT_RESOURCES)
    out: List[str] = []
    seen: Set[str] = set()
    for m in modules:
        m = str(m or "").strip()
        if not m:
            continue
        if m in GROUP_EXPAND:
            for code in GROUP_EXPAND[m]:
                if code not in seen:
                    seen.add(code)
                    out.append(code)
        elif m in ALL_RESOURCES:
            if m not in seen:
                seen.add(m)
                out.append(m)
        else:
            raise ValueError(f"未知同步模块: {m}")
    if not out:
        raise ValueError("请至少选择一个同步模块")
    return out


def split_resources(resources: Sequence[str]) -> Dict[str, List[str]]:
    """按类别拆分资源。"""
    return {
        "strategy": [r for r in resources if r in RESOURCE_STRATEGY],
        "observe": [r for r in resources if r in RESOURCE_OBSERVE],
        "basic": [r for r in resources if r in RESOURCE_BASIC],
        "board": [r for r in resources if r in RESOURCE_BOARD],
        "quotes": [r for r in resources if r in RESOURCE_QUOTES],
        "fund_flow": [r for r in resources if r in RESOURCE_FUND_FLOW],
        "computed": [r for r in resources if r in RESOURCE_COMPUTED],
        "adj_factors": [r for r in resources if r in RESOURCE_ADJ_FACTORS],
        "fina": [r for r in resources if r in RESOURCE_FINA],
        "permissions": [r for r in resources if r in RESOURCE_PERMISSIONS],
    }


def filter_modules_for_bundle(
    bundle_key: str, modules: Sequence[str]
) -> List[str]:
    """Push 分批时：只把属于该 bundle 的细项发给生产 import，避免跨类污染白名单校验。"""
    allowed = set(BUNDLE_RESOURCES.get(bundle_key) or [])
    if not allowed:
        return []
    return [m for m in modules if m in allowed]


def needs_date_range(resources: Sequence[str]) -> bool:
    return any(r in DATE_RANGE_REQUIRED for r in resources)


def allows_optional_date_range(resources: Sequence[str]) -> bool:
    return any(r in DATE_RANGE_OPTIONAL for r in resources)


def catalog_for_api() -> Dict[str, Any]:
    groups = []
    for g in MODULE_CATALOG:
        groups.append(
            {
                "group": g["group"],
                "group_name": g["name"],
                "name": g["name"],
                "requires_date_range": bool(g.get("requires_date_range")),
                "date_range_optional": bool(g.get("date_range_optional")),
                "items": g["items"],
            }
        )
    return {
        "groups": groups,
        "date_range_required": list(DATE_RANGE_REQUIRED),
        "date_range_optional": list(DATE_RANGE_OPTIONAL),
        "default_resources": list(DEFAULT_RESOURCES),
        "legacy_modules": [
            {
                "code": MODULE_STRATEGY_CONFIGS,
                "name": "策略参数版本（全部）",
                "desc": "展开为全部策略配置细项",
            },
            {
                "code": MODULE_TRADE_OBSERVE,
                "name": "交易观察（全部）",
                "desc": "展开为全部观察/正式交易细项",
            },
            {
                "code": "basic_info",
                "name": "股票基本信息（全部）",
                "desc": "A股+港股基本信息",
            },
            {
                "code": "board_info",
                "name": "板块信息（全部）",
                "desc": "行业/概念基本信息+成分股",
            },
            {
                "code": "quotes",
                "name": "行情（全部）",
                "desc": "A股+港股历史行情，须日期范围",
            },
            {
                "code": "fund_flow",
                "name": "资金流（全部）",
                "desc": "A股+港股个股资金流日表，须日期范围",
            },
            {
                "code": "computed_results",
                "name": "预计算与复盘（全部）",
                "desc": "RS/策略信号/指数日线/板块资金流/涨停池/复盘/简报，须日期范围",
            },
            {
                "code": "adj_factors",
                "name": "复权因子（全部）",
                "desc": "stock_adj_factor（A股/港股同表）；日期可选，不填则全库",
            },
            {
                "code": "fina_indicator",
                "name": "财务指标（全部）",
                "desc": "stock_fina_indicator；日期可选，不填则全库",
            },
            {
                "code": "permissions",
                "name": "权限与角色（全部）",
                "desc": "权限资源树+角色定义+角色-权限映射",
            },
        ],
        "all_resources": list(ALL_RESOURCES),
    }
