"""板块成分股 Excel/CSV 导入解析。"""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

CODE_ALIASES = {"stock_code", "code", "股票代码", "代码", "证券代码"}
NAME_ALIASES = {"stock_name", "name", "股票名称", "名称", "证券名称"}


def _pick_col(columns: List[str], aliases: set[str]) -> Optional[str]:
    for c in columns:
        key = str(c).strip().lower()
        if key in {a.lower() for a in aliases}:
            return c
        if str(c).strip() in aliases:
            return c
    return None


def parse_constituents_file(filename: str, content: bytes) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """解析导入文件，返回 (有效行, 错误行)。"""
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        df = pd.read_excel(BytesIO(content), dtype=str)
    elif name.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        df = pd.read_csv(StringIO(text), dtype=str)
    else:
        return [], [{"row_no": 0, "message": "仅支持 .csv / .xlsx 文件"}]

    if df is None or df.empty:
        return [], [{"row_no": 0, "message": "文件无数据"}]

    df.columns = [str(c).strip() for c in df.columns]
    code_col = _pick_col(list(df.columns), CODE_ALIASES)
    if not code_col:
        return [], [{"row_no": 0, "message": "缺少股票代码列（stock_code / 股票代码 / 代码）"}]
    name_col = _pick_col(list(df.columns), NAME_ALIASES)

    rows: List[Dict[str, str]] = []
    issues: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        raw_code = row.get(code_col)
        if raw_code is None or (isinstance(raw_code, float) and pd.isna(raw_code)):
            continue
        code = str(raw_code).strip()
        if not code or code.lower() == "nan":
            continue
        stock_name = ""
        if name_col and name_col in row.index:
            nv = row.get(name_col)
            if nv is not None and not (isinstance(nv, float) and pd.isna(nv)):
                stock_name = str(nv).strip()
        if code in seen:
            issues.append({"row_no": row_no, "stock_code": code, "message": "文件内重复代码，已跳过"})
            continue
        seen.add(code)
        rows.append({"stock_code": code, "stock_name": stock_name})
    if not rows:
        issues.append({"row_no": 0, "message": "未解析到有效股票代码"})
    return rows, issues
