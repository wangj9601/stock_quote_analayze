"""板块成分股 Excel/CSV 导入解析（含东财 Table.xls 制表符文本）。"""

from __future__ import annotations

import csv
import re
from io import BytesIO, StringIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from backend_api.models import StockBasicInfo

CODE_ALIASES = {"stock_code", "code", "股票代码", "代码", "证券代码"}
NAME_ALIASES = {"stock_name", "name", "股票名称", "名称", "证券名称"}
BOARD_CODE_ALIASES = {"board_code", "板块代码", "板块编码", "板块"}
BOARD_NAME_ALIASES = {"board_name", "板块名称", "板块名"}

_OLE_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# 东财导出名称后缀：优刻得-W、云从科技-UW、云天励飞-U 等，库中通常仅存简称
_EASTMONEY_NAME_SUFFIX = re.compile(r"-[A-Z]+$")


def _pick_col(columns: List[str], aliases: set[str]) -> Optional[str]:
    for c in columns:
        key = str(c).strip().lower()
        if key in {a.lower() for a in aliases}:
            return c
        if str(c).strip() in aliases:
            return c
    return None


def _is_blank_cell(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    s = str(val).strip()
    return not s or s.lower() == "nan"


def _cell_str(val: Any) -> str:
    if _is_blank_cell(val):
        return ""
    return str(val).strip()


def _normalize_import_code(raw: str) -> str:
    s = str(raw or "").strip().upper()
    while s and s[0].isalpha():
        s = s[1:]
    if "." in s:
        s = s.split(".")[0]
    if s.isdigit() and len(s) < 6:
        s = s.zfill(6)
    return s


def _load_dataframe(filename: str, content: bytes) -> Optional[pd.DataFrame]:
    """读取表格：真 xlsx/xls 或东财等导出的伪 xls（GBK/UTF-8 制表符/逗号文本）。"""
    low = (filename or "").lower()

    if low.endswith(".xlsx"):
        return pd.read_excel(BytesIO(content), dtype=str, engine="openpyxl")

    if low.endswith(".xls"):
        if content[:8] == _OLE_XLS_MAGIC:
            try:
                return pd.read_excel(BytesIO(content), dtype=str, engine="xlrd")
            except Exception:
                pass
        df = _read_text_table(content)
        if df is not None:
            return df
        try:
            return pd.read_excel(BytesIO(content), dtype=str, engine="xlrd")
        except Exception:
            return None

    if low.endswith(".csv"):
        df = _read_text_table(content)
        if df is not None:
            return df

    return None


def _normalize_text_line_endings(text: str) -> str:
    """东财 Table.xls 等导出常用 \\r 换行，pandas 需规范为 \\n。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read_text_table(content: bytes) -> Optional[pd.DataFrame]:
    for enc in ("utf-8-sig", "gbk", "cp936", "gb18030"):
        try:
            text = content.decode(enc)
        except UnicodeDecodeError:
            continue
        if not text.strip():
            continue
        text = _normalize_text_line_endings(text)
        first_line = text.splitlines()[0] if text else ""
        sep = "\t" if first_line.count("\t") >= max(first_line.count(","), 1) else ","
        try:
            df = pd.read_csv(StringIO(text), sep=sep, dtype=str, engine="python")
        except Exception:
            continue
        if df is not None and not df.empty:
            return df
    return None


def parse_constituents_file(filename: str, content: bytes) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    解析导入文件，返回 (有效行, 错误/跳过行)。
    行内 stock_code 可为空：仅含 stock_name 时由 resolve_rows_stock_codes 反查代码。
    """
    low = (filename or "").lower()
    if not (low.endswith(".csv") or low.endswith(".xlsx") or low.endswith(".xls")):
        return [], [{"row_no": 0, "message": "仅支持 .csv / .xlsx / .xls 文件"}]

    df = _load_dataframe(filename, content)
    if df is None:
        return [], [{"row_no": 0, "message": "无法解析文件，请确认格式为 Excel 或东财导出的 Table.xls（制表符文本）"}]
    if df.empty:
        return [], [{"row_no": 0, "message": "文件无数据"}]

    df.columns = [str(c).strip() for c in df.columns]
    code_col = _pick_col(list(df.columns), CODE_ALIASES)
    name_col = _pick_col(list(df.columns), NAME_ALIASES)
    if not code_col and not name_col:
        return [], [{"row_no": 0, "message": "缺少股票代码列或名称列（代码/名称/stock_code/stock_name）"}]

    rows: List[Dict[str, str]] = []
    issues: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        stock_name = _cell_str(row.get(name_col)) if name_col else ""
        stock_code = _cell_str(row.get(code_col)) if code_col else ""

        if not stock_code and not stock_name:
            continue

        dedupe_key = stock_code if stock_code else f"name:{stock_name}"
        if dedupe_key in seen_keys:
            issues.append({
                "row_no": row_no,
                "stock_code": stock_code or None,
                "stock_name": stock_name or None,
                "message": "文件内重复记录，已跳过",
            })
            continue
        seen_keys.add(dedupe_key)
        rows.append({"stock_code": stock_code, "stock_name": stock_name})

    if not rows:
        issues.append({"row_no": 0, "message": "未解析到有效股票代码或名称"})
    return rows, issues


def _normalize_import_board_code(raw: str) -> str:
    s = str(raw or "").strip().upper()
    return s.lstrip("'").lstrip("’").strip()


def parse_all_constituents_file(
    filename: str,
    content: bytes,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    解析全量成分股导入文件，返回 (有效行, 错误/跳过行)。
    每行需含板块代码；股票代码/名称至少其一。
    """
    low = (filename or "").lower()
    if not (low.endswith(".csv") or low.endswith(".xlsx") or low.endswith(".xls")):
        return [], [{"row_no": 0, "message": "仅支持 .csv / .xlsx / .xls 文件"}]

    df = _load_dataframe(filename, content)
    if df is None:
        return [], [{"row_no": 0, "message": "无法解析文件，请使用全量模板或先导出全部成分股"}]
    if df.empty:
        return [], [{"row_no": 0, "message": "文件无数据"}]

    df.columns = [str(c).strip() for c in df.columns]
    board_col = _pick_col(list(df.columns), BOARD_CODE_ALIASES)
    board_name_col = _pick_col(list(df.columns), BOARD_NAME_ALIASES)
    code_col = _pick_col(list(df.columns), CODE_ALIASES)
    name_col = _pick_col(list(df.columns), NAME_ALIASES)
    if not board_col:
        return [], [{"row_no": 0, "message": "缺少板块代码列（board_code/板块代码/板块）"}]
    if not code_col and not name_col:
        return [], [{"row_no": 0, "message": "缺少股票代码列或名称列"}]

    rows: List[Dict[str, str]] = []
    issues: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    for idx, row in df.iterrows():
        row_no = int(idx) + 2
        board_code = _normalize_import_board_code(_cell_str(row.get(board_col)))
        board_name = _cell_str(row.get(board_name_col)) if board_name_col else ""
        stock_name = _cell_str(row.get(name_col)) if name_col else ""
        stock_code = _cell_str(row.get(code_col)) if code_col else ""

        if not board_code:
            issues.append({"row_no": row_no, "message": "板块代码为空，已跳过"})
            continue
        if not stock_code and not stock_name:
            continue

        dedupe_key = f"{board_code}|{stock_code or f'name:{stock_name}'}"
        if dedupe_key in seen_keys:
            issues.append({
                "row_no": row_no,
                "board_code": board_code,
                "stock_code": stock_code or None,
                "stock_name": stock_name or None,
                "message": "文件内重复记录，已跳过",
            })
            continue
        seen_keys.add(dedupe_key)
        rows.append({
            "board_code": board_code,
            "board_name": board_name,
            "stock_code": stock_code,
            "stock_name": stock_name,
        })

    if not rows:
        issues.append({"row_no": 0, "message": "未解析到有效成分股记录"})
    return rows, issues


def _normalize_eastmoney_stock_name(name: str) -> str:
    """去掉东财名称后缀（-W/-UW/-U 等），便于与 stock_basic_info 简称匹配。"""
    s = (name or "").strip()
    return _EASTMONEY_NAME_SUFFIX.sub("", s)


def _code_match_priority(code: str) -> int:
    """同名多代码时按板块优先级择优，数值越小越优先。"""
    if not code or not code.isdigit():
        return 999
    if code.startswith(("688", "689")):
        return 1
    if code.startswith(("300", "301")):
        return 2
    if code.startswith(("000", "001", "002", "003")):
        return 3
    if code.startswith(("600", "601", "603", "605")):
        return 4
    if code.startswith("920"):
        return 5
    if code.startswith(("43", "83", "87", "88")):
        return 6
    return 50


def _pick_best_code(codes: List[str]) -> Tuple[Optional[str], List[str]]:
    """从多个候选代码中按交易所优先级选取；同优先级并列则视为歧义。"""
    uniq = sorted({c for c in codes if c})
    if not uniq:
        return None, []
    if len(uniq) == 1:
        return uniq[0], uniq
    ranked = sorted(uniq, key=lambda c: (_code_match_priority(c), c))
    best_pri = _code_match_priority(ranked[0])
    top = [c for c in ranked if _code_match_priority(c) == best_pri]
    if len(top) == 1:
        return top[0], uniq
    return None, uniq


def _build_name_to_codes(
    db: Session,
    names: List[str],
) -> Dict[str, List[str]]:
    """批量查询名称（含东财去后缀变体）到代码列表。"""
    name_to_codes: Dict[str, List[str]] = {}
    if not names:
        return name_to_codes

    db_rows = (
        db.query(StockBasicInfo.code, StockBasicInfo.name)
        .filter(StockBasicInfo.name.in_(names))
        .all()
    )
    canonical: Dict[str, List[str]] = {}
    for code, name in db_rows:
        n = str(name or "").strip()
        c = _normalize_import_code(str(code or ""))
        if not n or not c:
            continue
        canonical.setdefault(n, []).append(c)

    for raw in names:
        keys = {raw}
        norm = _normalize_eastmoney_stock_name(raw)
        if norm:
            keys.add(norm)
        merged: List[str] = []
        seen: set[str] = set()
        for k in keys:
            for c in canonical.get(k, []):
                if c not in seen:
                    seen.add(c)
                    merged.append(c)
        if merged:
            name_to_codes[raw] = merged
    return name_to_codes


def resolve_rows_stock_codes(
    db: Session,
    rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    对仅有名称的行，从 stock_basic_info 匹配名称获取代码。
    支持东财名称去后缀（-W/-UW/-U）；同名多代码时按板块优先级择优。
    已有代码的行原样保留（并规范化 6 位代码）。
    """
    raw_names = sorted({
        (r.get("stock_name") or "").strip()
        for r in rows
        if not (r.get("stock_code") or "").strip() and (r.get("stock_name") or "").strip()
    })
    lookup_names = sorted({
        n for raw in raw_names for n in (raw, _normalize_eastmoney_stock_name(raw)) if n
    })
    name_to_codes = _build_name_to_codes(db, lookup_names)
    # 导入行用原始名称查表，内部已合并去后缀命中结果
    row_name_to_codes: Dict[str, List[str]] = {}
    for raw in raw_names:
        keys = {raw}
        norm = _normalize_eastmoney_stock_name(raw)
        if norm:
            keys.add(norm)
        merged: List[str] = []
        seen: set[str] = set()
        for k in keys:
            for c in name_to_codes.get(k, []):
                if c not in seen:
                    seen.add(c)
                    merged.append(c)
        if merged:
            row_name_to_codes[raw] = merged

    resolved: List[Dict[str, str]] = []
    issues: List[Dict[str, Any]] = []
    seen_codes: set[str] = set()

    for i, r in enumerate(rows):
        row_no = i + 2
        stock_name = (r.get("stock_name") or "").strip()
        raw_code = (r.get("stock_code") or "").strip()
        code = _normalize_import_code(raw_code) if raw_code else ""

        if not code:
            matches = row_name_to_codes.get(stock_name, [])
            if not matches:
                issues.append({
                    "row_no": row_no,
                    "stock_name": stock_name,
                    "message": f"未在股票基本信息表找到名称「{stock_name}」",
                })
                continue
            picked, all_matches = _pick_best_code(matches)
            if not picked:
                issues.append({
                    "row_no": row_no,
                    "stock_name": stock_name,
                    "message": f"名称「{stock_name}」对应多只股票：{', '.join(all_matches)}",
                })
                continue
            code = picked

        if code in seen_codes:
            issues.append({
                "row_no": row_no,
                "stock_code": code,
                "stock_name": stock_name or None,
                "message": "解析后重复代码，已跳过",
            })
            continue
        seen_codes.add(code)
        resolved.append({"stock_code": code, "stock_name": stock_name})

    if not resolved and rows:
        issues.append({"row_no": 0, "message": "名称均未能在股票基本信息表中匹配到唯一代码"})
    return resolved, issues
