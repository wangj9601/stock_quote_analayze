# -*- coding: utf-8 -*-
"""个股代码归一化与市场判定（A 股 6 位 / 港股 5 位）。

约定：纯数字代码按位数缺省分流——5 位（可含前导零如 00700）为港股，
6 位为 A 股。与 levels / 形态识别等分析接口口径一致。
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Tuple


def strip_exchange_prefix(raw: Any) -> str:
    """去掉 SH/SZ/BJ/HK 前缀，保留数字主体。"""
    s = str(raw or "").strip()
    if not s:
        return ""
    upper = s.upper()
    for prefix in ("SH", "SZ", "BJ", "HK"):
        if upper.startswith(prefix) and len(s) > len(prefix):
            return s[len(prefix) :].strip()
    return s


def normalize_equity_code(raw: Any) -> str:
    """
    归一化个股代码：港股补齐 5 位，A 股补齐 6 位。

    - ``700`` / ``0700`` → ``00700``
    - ``00700`` → ``00700``
    - ``600519`` → ``600519``
    - ``SH600519`` → ``600519``
    """
    s = strip_exchange_prefix(raw)
    if not s:
        return ""
    if not s.isdigit():
        return str(raw or "").strip()
    if len(s) <= 5:
        return s.zfill(5)
    return s.zfill(6)


def is_hk_equity_code(raw: Any) -> bool:
    """纯数字且归一化后为 5 位 → 港股。"""
    code = normalize_equity_code(raw)
    return bool(code) and code.isdigit() and len(code) == 5


def is_cn_equity_code(raw: Any) -> bool:
    """纯数字且归一化后为 6 位 → A 股。"""
    code = normalize_equity_code(raw)
    return bool(code) and code.isdigit() and len(code) == 6


def infer_market_type(raw: Any) -> str:
    """由代码位数推断市场：``HK`` / ``CN``；无法判断时返回空串。"""
    code = normalize_equity_code(raw)
    if not code or not code.isdigit():
        return ""
    if len(code) == 5:
        return "HK"
    if len(code) == 6:
        return "CN"
    return ""


def quotes_table_for_code(raw: Any) -> str:
    """日 K 表名：港股 ``historical_quotes_hk``，否则 ``historical_quotes``。"""
    if is_hk_equity_code(raw):
        return "historical_quotes_hk"
    return "historical_quotes"


def partition_codes_by_market(
    codes: Optional[Sequence[Any]],
) -> Tuple[List[str], List[str]]:
    """将代码列表拆成 (cn_codes, hk_codes)，各自已归一化并去重保序。"""
    cn: List[str] = []
    hk: List[str] = []
    seen_cn = set()
    seen_hk = set()
    for raw in codes or []:
        code = normalize_equity_code(raw)
        if not code or not code.isdigit():
            continue
        if len(code) == 5:
            if code not in seen_hk:
                seen_hk.add(code)
                hk.append(code)
        elif len(code) == 6:
            if code not in seen_cn:
                seen_cn.add(code)
                cn.append(code)
    return cn, hk
