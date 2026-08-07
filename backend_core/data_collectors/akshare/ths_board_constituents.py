"""
同花顺行业/概念板块成分股采集（akshare 已移除 cons_ths，自建 HTML 分页抓取）。

行业：http://q.10jqka.com.cn/thshy/detail/code/{code}/
概念：http://q.10jqka.com.cn/gn/detail/code/{code}/
翻页：.../field/199112/order/desc/page/{page}/
"""
from __future__ import annotations

import re
import time
from functools import lru_cache
from typing import List, Literal, Optional, Tuple

import py_mini_racer
import requests
from bs4 import BeautifulSoup

from akshare.datasets import get_ths_js

from backend_core.data_collectors.akshare.industry_board_constituents_ak import (
    normalize_stock_code,
)

ThsBoardKind = Literal["industry", "concept"]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"
)
_FIELD = "199112"


def _ths_js_content() -> str:
    path = get_ths_js("ths.js")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _ths_headers(referer: str) -> dict:
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(_ths_js_content())
    v_code = js_code.call("v")
    return {
        "User-Agent": _UA,
        "Cookie": f"v={v_code}",
        "hexin-v": v_code,
        "Referer": referer,
    }


def _detail_base(kind: ThsBoardKind, code: str) -> str:
    code = str(code).strip()
    if kind == "industry":
        return f"http://q.10jqka.com.cn/thshy/detail/code/{code}/"
    return f"http://q.10jqka.com.cn/gn/detail/code/{code}/"


def _page_url(kind: ThsBoardKind, code: str, page: int) -> str:
    base = _detail_base(kind, code)
    if page <= 1:
        return base
    return f"{base}field/{_FIELD}/order/desc/page/{page}/"


def _parse_cons_table(html: str) -> Tuple[List[Tuple[str, str]], Optional[int]]:
    """从详情/翻页 HTML 解析成分股与总页数。"""
    soup = BeautifulSoup(html, "lxml")
    page_info = soup.find("span", class_="page_info")
    total_pages: Optional[int] = None
    if page_info and page_info.text and "/" in page_info.text:
        try:
            total_pages = int(page_info.text.strip().split("/")[-1])
        except ValueError:
            total_pages = None

    table = soup.find("table")
    if table is None:
        return [], total_pages

    rows = table.find_all("tr")
    if not rows:
        return [], total_pages

    header_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    code_idx = next((i for i, h in enumerate(header_cells) if "代码" in h), None)
    name_idx = next((i for i, h in enumerate(header_cells) if h in ("名称", "股票简称", "简称")), None)
    if code_idx is None:
        # 无表头时：序号、代码、名称…
        code_idx, name_idx = 1, 2

    out: List[Tuple[str, str]] = []
    for tr in rows[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) <= code_idx:
            continue
        code = normalize_stock_code(cells[code_idx])
        if not code:
            continue
        name = ""
        if name_idx is not None and len(cells) > name_idx:
            name = cells[name_idx]
        out.append((code, name))
    return out, total_pages


@lru_cache(maxsize=2)
def _name_to_code_map(kind: ThsBoardKind) -> dict:
    """name -> ths code。"""
    if kind == "industry":
        import akshare as ak

        df = ak.stock_board_industry_name_ths()
    else:
        import akshare as ak

        df = ak.stock_board_concept_name_ths()
    mapping: dict = {}
    for _, row in df.iterrows():
        name = str(row.get("name") or "").strip()
        code = str(row.get("code") or "").strip()
        if name and code:
            mapping[name] = code
    return mapping


def resolve_ths_board_code(
    board_code: str,
    board_name: Optional[str] = None,
    *,
    kind: ThsBoardKind = "industry",
) -> str:
    """将库中板码/板名解析为同花顺数字板码。"""
    raw = (board_code or "").strip()
    if re.fullmatch(r"\d{4,8}", raw):
        return raw
    name = (board_name or "").strip() or raw
    mapping = _name_to_code_map(kind)
    if name in mapping:
        return mapping[name]
    if raw in mapping:
        return mapping[raw]
    raise ValueError(f"无法解析同花顺{('行业' if kind == 'industry' else '概念')}板码: {board_code}/{board_name}")


def fetch_ths_board_constituents(
    board_code: str,
    board_name: Optional[str] = None,
    *,
    kind: ThsBoardKind = "industry",
    interval_sec: float = 0.35,
    max_retries: int = 2,
) -> List[Tuple[str, str]]:
    """拉取同花顺板块全部成分股 [(stock_code, stock_name), ...]。"""
    ths_code = resolve_ths_board_code(board_code, board_name, kind=kind)
    referer = _detail_base(kind, ths_code)
    last_err: Optional[Exception] = None
    html = ""
    for attempt in range(max_retries + 1):
        try:
            r = requests.get(referer, headers=_ths_headers(referer), timeout=20)
            r.raise_for_status()
            html = r.text
            break
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(interval_sec * 2)
    else:
        raise last_err  # type: ignore[misc]

    first, total_pages = _parse_cons_table(html)
    if not first and not total_pages:
        raise RuntimeError(f"同花顺成分页无表格: {kind}/{ths_code}")

    all_rows = list(first)
    pages = total_pages or 1
    for page in range(2, pages + 1):
        time.sleep(interval_sec)
        url = _page_url(kind, ths_code, page)
        page_html = ""
        for attempt in range(max_retries + 1):
            try:
                r = requests.get(url, headers=_ths_headers(referer), timeout=20)
                r.raise_for_status()
                page_html = r.text
                break
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    time.sleep(interval_sec * 2)
        else:
            raise last_err  # type: ignore[misc]
        rows, _ = _parse_cons_table(page_html)
        all_rows.extend(rows)

    # 去重保序
    seen = set()
    uniq: List[Tuple[str, str]] = []
    for code, name in all_rows:
        if code in seen:
            continue
        seen.add(code)
        uniq.append((code, name))
    return uniq
