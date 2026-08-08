"""行业板块 AKShare 返回列名归一化（兼容东方财富新旧列名、同花顺兜底）。"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

# 中文源列名（按优先级） -> 英文字段名
INDUSTRY_FIELD_SOURCES: Dict[str, List[str]] = {
    "board_code": ["板块代码"],
    "board_name": ["板块名称"],
    "latest_price": ["最新价"],
    "change_amount": ["涨跌额"],
    "change_percent": ["涨跌幅"],
    "total_market_value": ["总市值"],
    "volume": ["成交量"],
    "amount": ["成交额"],
    "turnover_rate": ["换手率"],
    "up_count": ["上涨家数"],
    "down_count": ["下跌家数"],
    "leading_stock_name": ["领涨股票", "领涨股"],
    "leading_stock_change_percent": [
        "领涨股票-涨跌幅",
        "领涨股涨跌幅",
        "领涨股-涨跌幅",
    ],
    "leading_stock_code": ["领涨股代码"],
}


def pick_source_column(df: pd.DataFrame, sources: List[str]) -> Optional[str]:
    for name in sources:
        if name in df.columns:
            return name
    return None


def industry_board_to_english_df(df: pd.DataFrame) -> pd.DataFrame:
    """将接口 DataFrame 转为统一英文字段列（缺失列不创建）。"""
    if df is None or df.empty:
        return pd.DataFrame()
    data: Dict[str, pd.Series] = {}
    for en, sources in INDUSTRY_FIELD_SOURCES.items():
        cn = pick_source_column(df, sources)
        if cn is not None:
            data[en] = df[cn]
    return pd.DataFrame(data)


def normalize_ths_industry_df(df: pd.DataFrame) -> pd.DataFrame:
    """同花顺 summary 接口列名对齐为东方财富风格，便于统一映射。

    注意：同花顺一览的「均价」是成分股均价，不是板块指数点位；
    东财 ``最新价`` 才是行业板指数。故不把「均价」映射为「最新价」，
    避免入库/展示成错误的「最新价」。
    """
    rename_map = {
        "板块": "板块名称",
        "总成交量": "成交量",
        "总成交额": "成交额",
        "领涨股-涨跌幅": "领涨股涨跌幅",
        "领涨股票-涨跌幅": "领涨股票-涨跌幅",
    }
    out = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "板块代码" not in out.columns and "板块名称" in out.columns:
        out["板块代码"] = out["板块名称"]
    # summary 无板块指数列：显式置空，禁止误用均价
    out["最新价"] = None
    for col in ("涨跌额", "总市值", "换手率", "领涨股代码"):
        if col not in out.columns:
            out[col] = None
    return out


def enrich_leading_stock_codes(
    df: pd.DataFrame, name_to_code: Dict[str, str]
) -> pd.DataFrame:
    """用 stock_basic_info 名称表补全 leading_stock_code。"""
    if df.empty or "leading_stock_name" not in df.columns:
        return df
    out = df.copy()
    if "leading_stock_code" not in out.columns:
        out["leading_stock_code"] = None
    for idx, row in out.iterrows():
        existing = row.get("leading_stock_code")
        if existing is not None and not pd.isna(existing) and str(existing).strip():
            continue
        name = row.get("leading_stock_name")
        if name is None or pd.isna(name):
            continue
        key = str(name).strip()
        if not key:
            continue
        code = name_to_code.get(key)
        if code:
            out.at[idx, "leading_stock_code"] = code
    return out
