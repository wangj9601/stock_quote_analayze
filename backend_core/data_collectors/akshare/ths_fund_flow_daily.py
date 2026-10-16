# -*- coding: utf-8 -*-
"""个股资金流日采：同花顺「即时」优先，免费页空表时用新浪资金流 → stock_fund_flow_daily。"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text

from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

_AMOUNT_RE = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*(亿|万)?\s*$",
    re.UNICODE,
)

_THS_PAGE_URL = (
    "http://data.10jqka.com.cn/funds/ggzjl/field/zdf/order/desc/page/{}/ajax/1/free/1/"
)
_THS_COUNT_URL = (
    "http://data.10jqka.com.cn/funds/ggzjl/field/code/order/desc/ajax/1/free/1/"
)
_SINA_MONEYFLOW_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "MoneyFlow.ssl_bkzj_ssggzj"
)
_SINA_PAGE_SIZE = 100
_SINA_MAX_PAGES = 120
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def parse_ths_amount(val: Any) -> Optional[float]:
    """将同花顺金额字符串（如 6.49亿 / 7588.54万）归一为元；纯数字视为已是元。"""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    s = str(val).strip().replace(",", "").replace("，", "")
    if not s or s in ("-", "--", "None", "nan", "NaN"):
        return None
    m = _AMOUNT_RE.match(s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "亿":
        return round(num * 1e8, 2)
    if unit == "万":
        return round(num * 1e4, 2)
    return num


def parse_ths_percent(val: Any) -> Optional[float]:
    """解析涨跌幅/换手率（可带 %）。"""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    s = str(val).strip().replace("%", "").replace(",", "")
    if not s or s in ("-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalize_ths_code(val: Any) -> Optional[str]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    if not s:
        return None
    if s.endswith(".0") and s.replace(".", "", 1).isdigit():
        s = s[:-2]
    if s.isdigit():
        return s.zfill(6)
    # 去掉市场前缀
    low = s.lower()
    for prefix in ("sh", "sz", "bj"):
        if low.startswith(prefix) and low[len(prefix) :].isdigit():
            return low[len(prefix) :].zfill(6)
    return s


def analyze_fund_flow_series(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    对按日期升序的流入/流出序列做简单变化分析。
    rows 元素需含 trade_date / inflow_amount / outflow_amount / net_amount。

    - *_sum：区间内逐日数值的代数和（含正负）
    - *_change：末日相对首日的差额（末日 − 首日），不是逐日变化之和
    """
    n = len(rows)
    if n == 0:
        return {
            "days": 0,
            "inflow_sum": None,
            "outflow_sum": None,
            "net_sum": None,
            "inflow_change": None,
            "outflow_change": None,
            "net_change": None,
            "first_date": None,
            "last_date": None,
        }

    def _f(v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    inflows = [_f(r.get("inflow_amount")) for r in rows]
    outflows = [_f(r.get("outflow_amount")) for r in rows]
    nets = [_f(r.get("net_amount")) for r in rows]

    def _sum(xs):
        vals = [x for x in xs if x is not None]
        return sum(vals) if vals else None

    first_in, last_in = inflows[0], inflows[-1]
    first_out, last_out = outflows[0], outflows[-1]
    first_net, last_net = nets[0], nets[-1]

    def _delta(a, b):
        if a is None or b is None:
            return None
        return b - a

    return {
        "days": n,
        "inflow_sum": _sum(inflows),
        "outflow_sum": _sum(outflows),
        "net_sum": _sum(nets),
        "inflow_change": _delta(first_in, last_in),
        "outflow_change": _delta(first_out, last_out),
        "net_change": _delta(first_net, last_net),
        "first_date": rows[0].get("trade_date"),
        "last_date": rows[-1].get("trade_date"),
        "latest_inflow": last_in,
        "latest_outflow": last_out,
        "latest_net": last_net,
    }


def _ths_headers() -> Dict[str, str]:
    import py_mini_racer
    from akshare.datasets import get_ths_js

    with open(get_ths_js("ths.js"), encoding="utf-8") as f:
        js = f.read()
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(js)
    v_code = ctx.call("v")
    return {
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "hexin-v": v_code,
        "Cookie": f"v={v_code}",
        "Host": "data.10jqka.com.cn",
        "Referer": "https://data.10jqka.com.cn/funds/ggzjl/",
        "User-Agent": _UA,
        "X-Requested-With": "XMLHttpRequest",
    }


def ths_page_count(html: str) -> Optional[int]:
    """解析 span.page_info（形如 1/103）。节点缺失时返回 None，不抛异常。"""
    soup = BeautifulSoup(html or "", "lxml")
    node = soup.find("span", attrs={"class": "page_info"})
    if node is None:
        return None
    raw = node.get_text(strip=True)
    if "/" not in raw:
        return None
    try:
        return int(raw.split("/")[-1])
    except ValueError:
        return None


def ths_html_to_frame(html: str) -> pd.DataFrame:
    """把一页资金流表格转成 DataFrame；空表返回空框。"""
    if not html or BeautifulSoup(html, "lxml").find("td") is None:
        return pd.DataFrame()
    try:
        tables = pd.read_html(StringIO(html))
    except ValueError:
        return pd.DataFrame()
    if not tables:
        return pd.DataFrame()
    df = tables[0]
    if df.empty:
        return df
    df.columns = [str(c).strip() for c in df.columns]
    return df


def fetch_ths_instant_dataframe(timeout: float = 20.0) -> pd.DataFrame:
    """抓同花顺即时资金流。免费接口只回空表壳时抛 RuntimeError。"""
    headers = _ths_headers()
    count_resp = requests.get(_THS_COUNT_URL, headers=headers, timeout=timeout)
    count_html = count_resp.content.decode("gbk", errors="replace")
    page_num = ths_page_count(count_html)
    if page_num is None:
        page_resp = requests.get(_THS_PAGE_URL.format(1), headers=headers, timeout=timeout)
        page_html = page_resp.content.decode("gbk", errors="replace")
        page_num = ths_page_count(page_html)
        frame = ths_html_to_frame(page_html)
        if page_num is None:
            if frame.empty:
                raise RuntimeError(
                    "同花顺个股资金流免费接口返回空表，缺少 page_info"
                )
            return frame
    frames: List[pd.DataFrame] = []
    for page in range(1, page_num + 1):
        headers = _ths_headers()
        resp = requests.get(_THS_PAGE_URL.format(page), headers=headers, timeout=timeout)
        html = resp.content.decode("gbk", errors="replace")
        frame = ths_html_to_frame(html)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise RuntimeError("同花顺个股资金流分页有页码但没有数据行")
    return pd.concat(frames, ignore_index=True)


def _sina_a_share(symbol: str) -> bool:
    s = str(symbol or "").strip().lower()
    if s.startswith("sh") and len(s) >= 8 and s[2] == "6":
        return True
    if s.startswith("sz") and len(s) >= 8 and s[2] in ("0", "3"):
        return True
    if s.startswith("bj") and len(s) >= 8:
        return True
    return False


def _sina_page(page: int, page_size: int, timeout: float) -> List[Dict[str, Any]]:
    resp = requests.get(
        _SINA_MONEYFLOW_URL,
        params={
            "page": page,
            "num": page_size,
            "sort": "netamount",
            "asc": 0,
            "bankuai": "",
            "shichang": "",
        },
        headers={"User-Agent": _UA, "Referer": "https://vip.stock.finance.sina.com.cn/"},
        timeout=timeout,
    )
    text = resp.content.decode("utf-8", errors="replace").strip()
    if not text or text == "null":
        return []
    data = json.loads(text)
    return data if isinstance(data, list) else []


def fetch_sina_moneyflow_records(
    page_size: int = _SINA_PAGE_SIZE,
    max_pages: int = _SINA_MAX_PAGES,
    timeout: float = 20.0,
    workers: int = 8,
) -> List[Dict[str, Any]]:
    """按页拉取新浪全市场资金流，直到空页。"""
    records: List[Dict[str, Any]] = []
    page = 1
    while page <= max_pages:
        batch = list(range(page, min(page + workers, max_pages + 1)))
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            parts = list(pool.map(lambda p: _sina_page(p, page_size, timeout), batch))
        stop = False
        for rows in parts:
            if not rows:
                stop = True
                break
            records.extend(rows)
            if len(rows) < page_size:
                stop = True
                break
        if stop:
            break
        page += workers
    return records


def sina_records_to_frame(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """新浪 in/out/net（元）对齐同花顺列名，只保留 A 股。"""
    rows: List[Dict[str, Any]] = []
    for rec in records:
        symbol = str(rec.get("symbol") or "")
        if not _sina_a_share(symbol):
            continue
        code = normalize_ths_code(symbol)
        if not code:
            continue
        change = rec.get("changeratio")
        try:
            change_pct = float(change) * 100.0 if change not in (None, "") else None
        except (TypeError, ValueError):
            change_pct = None
        rows.append(
            {
                "股票代码": code,
                "股票简称": rec.get("name"),
                "最新价": rec.get("trade"),
                "涨跌幅": change_pct,
                "流入资金": rec.get("inamount"),
                "流出资金": rec.get("outamount"),
                "净额": rec.get("netamount"),
                "成交额": rec.get("amount"),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["股票代码"], keep="first")


def fetch_sina_instant_dataframe() -> pd.DataFrame:
    frame = sina_records_to_frame(fetch_sina_moneyflow_records())
    if frame.empty:
        raise RuntimeError("新浪个股资金流返回空数据")
    return frame


class ThsFundFlowDailyCollector:
    """采集同花顺「即时」全市场流入/流出并 UPSERT 到 stock_fund_flow_daily。"""

    SOURCE = "ths"

    def __init__(self, trade_date: Optional[str] = None) -> None:
        self.trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
        self.logger = logger
        self.source = self.SOURCE

    def fetch_dataframe(self) -> pd.DataFrame:
        self.logger.info("抓取同花顺个股资金流即时页")
        try:
            df = fetch_ths_instant_dataframe()
            self.source = "ths"
        except Exception as exc:
            self.logger.warning("同花顺个股资金流不可用，改用新浪资金流: %s", exc)
            df = fetch_sina_instant_dataframe()
            self.source = "sina"
        if df is None or df.empty:
            raise RuntimeError("个股资金流返回空数据")
        return df

    def dataframe_to_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        col_map = {str(c).strip(): c for c in df.columns}

        def col(*names: str):
            for n in names:
                if n in col_map:
                    return col_map[n]
            return None

        c_code = col("股票代码", "代码")
        c_name = col("股票简称", "名称")
        c_price = col("最新价")
        c_chg = col("涨跌幅")
        c_tr = col("换手率")
        c_in = col("流入资金")
        c_out = col("流出资金")
        c_net = col("净额")
        c_amt = col("成交额")
        if c_code is None or c_in is None or c_out is None:
            raise RuntimeError(f"同花顺资金流缺少必要列: {list(df.columns)}")

        now = datetime.now()
        by_code: Dict[str, Dict[str, Any]] = {}
        for _, row in df.iterrows():
            code = normalize_ths_code(row.get(c_code))
            if not code:
                continue
            # 去重：同一 code 保留首次出现
            if code in by_code:
                continue
            by_code[code] = {
                "code": code,
                "trade_date": self.trade_date,
                "name": (str(row.get(c_name)).strip() if c_name and row.get(c_name) is not None else None),
                "inflow_amount": parse_ths_amount(row.get(c_in)),
                "outflow_amount": parse_ths_amount(row.get(c_out)),
                "net_amount": parse_ths_amount(row.get(c_net)) if c_net else None,
                "turnover_amount": parse_ths_amount(row.get(c_amt)) if c_amt else None,
                "change_percent": parse_ths_percent(row.get(c_chg)) if c_chg else None,
                "turnover_rate": parse_ths_percent(row.get(c_tr)) if c_tr else None,
                "current_price": parse_ths_amount(row.get(c_price)) if c_price else None,
                "source": self.source,
                "created_at": now,
                "updated_at": now,
            }
        return list(by_code.values())

    def upsert_rows(self, rows: List[Dict[str, Any]], batch_size: int = 500) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO stock_fund_flow_daily (
                code, trade_date, name, inflow_amount, outflow_amount, net_amount,
                turnover_amount, change_percent, turnover_rate, current_price,
                source, created_at, updated_at
            ) VALUES (
                :code, :trade_date, :name, :inflow_amount, :outflow_amount, :net_amount,
                :turnover_amount, :change_percent, :turnover_rate, :current_price,
                :source, :created_at, :updated_at
            )
            ON CONFLICT (code, trade_date) DO UPDATE SET
                name = EXCLUDED.name,
                inflow_amount = EXCLUDED.inflow_amount,
                outflow_amount = EXCLUDED.outflow_amount,
                net_amount = EXCLUDED.net_amount,
                turnover_amount = EXCLUDED.turnover_amount,
                change_percent = EXCLUDED.change_percent,
                turnover_rate = EXCLUDED.turnover_rate,
                current_price = EXCLUDED.current_price,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
            """
        )
        session = SessionLocal()
        written = 0
        try:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                session.execute(sql, chunk)
                session.commit()
                written += len(chunk)
            return written
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def sync_to_quote_tables(
        self, rows: List[Dict[str, Any]], batch_size: int = 500
    ) -> Dict[str, int]:
        """
        将资金流回写到实时表 / 历史表，避免统计时跨表关联。
        仅 UPDATE 已存在的 (code, date/trade_date) 行，不新建空行情。
        """
        if not rows:
            return {"realtime_updated": 0, "historical_updated": 0}

        # historical_quotes.date 在库中为 text（YYYY-MM-DD），勿 CAST 成 date，否则 text=date 报错
        hist_sql = text(
            """
            UPDATE historical_quotes
            SET inflow_amount = :inflow_amount,
                outflow_amount = :outflow_amount,
                net_amount = :net_amount
            WHERE code = :code AND date = :trade_date
            """
        )
        rt_sql = text(
            """
            UPDATE stock_realtime_quote
            SET inflow_amount = :inflow_amount,
                outflow_amount = :outflow_amount,
                net_amount = :net_amount
            WHERE code = :code AND trade_date = :trade_date
            """
        )
        session = SessionLocal()
        hist_n = 0
        rt_n = 0
        try:
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                params = [
                    {
                        "code": r["code"],
                        "trade_date": r["trade_date"],
                        "inflow_amount": r.get("inflow_amount"),
                        "outflow_amount": r.get("outflow_amount"),
                        "net_amount": r.get("net_amount"),
                    }
                    for r in chunk
                ]
                for p in params:
                    rh = session.execute(hist_sql, p)
                    hist_n += rh.rowcount or 0
                    rr = session.execute(rt_sql, p)
                    rt_n += rr.rowcount or 0
                session.commit()
            return {"realtime_updated": rt_n, "historical_updated": hist_n}
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def collect(self) -> Dict[str, Any]:
        df = self.fetch_dataframe()
        rows = self.dataframe_to_rows(df)
        written = self.upsert_rows(rows)
        synced = self.sync_to_quote_tables(rows)
        result = {
            "success": True,
            "trade_date": self.trade_date,
            "fetched": len(df),
            "unique": len(rows),
            "written": written,
            "realtime_updated": synced["realtime_updated"],
            "historical_updated": synced["historical_updated"],
            "source": self.source,
        }
        self.logger.info(
            "同花顺资金流日采完成 trade_date=%s fetched=%s unique=%s written=%s "
            "hist=%s realtime=%s",
            self.trade_date,
            result["fetched"],
            result["unique"],
            written,
            synced["historical_updated"],
            synced["realtime_updated"],
        )
        return result

def collect_ths_fund_flow_daily(trade_date: Optional[str] = None) -> Dict[str, Any]:
    return ThsFundFlowDailyCollector(trade_date=trade_date).collect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(collect_ths_fund_flow_daily())
