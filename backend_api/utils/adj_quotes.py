"""不复权行情 + 复权因子 → 查询/内存层现算前复权。

因子来源（本期）：AkShare 新浪 `stock_zh_a_daily(adjust=\"qfq-factor\")`。
公式：P_qfq = P_raw * f_t / f_T（f_T 为序列最新因子日；volume/amount 不乘）。
因子按日对齐时对缺口做 forward-fill（沿用上一有效因子至下一事件前）。
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SOURCE_AKSHARE_SINA_QFQ = "akshare_sina_qfq"
DEFAULT_FACTOR_MAX_AGE_DAYS = 5


class AdjQuotesError(Exception):
    """前复权现算/因子拉取业务错误（可直接展示给用户）。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def normalize_a_share_code(code: str) -> str:
    s = str(code or "").strip().upper()
    if s.startswith(("SH", "SZ")) and len(s) > 2:
        s = s[2:]
    return s


def to_sina_symbol(code: str) -> str:
    """A 股 6 位代码 → 新浪 symbol（sh600519 / sz000001）。"""
    c = normalize_a_share_code(code)
    if not c.isdigit() or len(c) != 6:
        raise AdjQuotesError(f"仅支持 A 股 6 位代码获取复权因子，当前：{code}")
    if c.startswith(("5", "6", "9")):
        return f"sh{c}"
    return f"sz{c}"


def _parse_trade_date(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    if " " in s:
        s = s.split(" ", 1)[0]
    if len(s) == 8 and s.isdigit():
        s = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _bar_date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def fetch_sina_qfq_factors(code: str) -> List[Dict[str, Any]]:
    """调用 AkShare 新浪接口拉取前复权因子序列。"""
    import akshare as ak

    symbol = to_sina_symbol(code)
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, adjust="qfq-factor")
            if df is None or getattr(df, "empty", True):
                raise AdjQuotesError(f"新浪未返回复权因子（{symbol}）")
            rows: List[Dict[str, Any]] = []
            # 列名可能是 date / qfq_factor
            cols = {str(c).lower(): c for c in df.columns}
            date_col = cols.get("date") or list(df.columns)[0]
            factor_col = (
                cols.get("qfq_factor")
                or cols.get("adj_factor")
                or cols.get("factor")
                or list(df.columns)[1]
            )
            for _, r in df.iterrows():
                td = _parse_trade_date(r.get(date_col))
                if td is None:
                    continue
                try:
                    f = float(r.get(factor_col))
                except (TypeError, ValueError):
                    continue
                if f <= 0:
                    continue
                rows.append(
                    {
                        "code": normalize_a_share_code(code),
                        "trade_date": td,
                        "adj_factor": f,
                        "source": SOURCE_AKSHARE_SINA_QFQ,
                    }
                )
            if not rows:
                raise AdjQuotesError(f"新浪复权因子解析为空（{symbol}）")
            rows.sort(key=lambda x: x["trade_date"])
            return rows
        except AdjQuotesError:
            raise
        except Exception as e:
            last_err = e
            sleep_s = (attempt + 1) * 1.5 + random.uniform(0.2, 0.8)
            logger.warning(
                "拉取新浪 qfq-factor 失败 %s attempt=%s: %s", symbol, attempt + 1, e
            )
            time.sleep(sleep_s)
    raise AdjQuotesError(f"获取复权因子失败：{last_err}")


def upsert_adj_factors(
    db: Session,
    rows: Sequence[Dict[str, Any]],
    *,
    source: str = SOURCE_AKSHARE_SINA_QFQ,
) -> int:
    """PostgreSQL UPSERT 写入 stock_adj_factor。"""
    if not rows:
        return 0
    now = datetime.now()
    n = 0
    sql = text(
        """
        INSERT INTO stock_adj_factor (code, trade_date, adj_factor, source, updated_at)
        VALUES (:code, :trade_date, :adj_factor, :source, :updated_at)
        ON CONFLICT (code, trade_date) DO UPDATE SET
            adj_factor = EXCLUDED.adj_factor,
            source = EXCLUDED.source,
            updated_at = EXCLUDED.updated_at
        """
    )
    for r in rows:
        code = normalize_a_share_code(str(r.get("code") or ""))
        td = r.get("trade_date")
        if isinstance(td, str):
            td = _parse_trade_date(td)
        if not code or not isinstance(td, date):
            continue
        try:
            f = float(r.get("adj_factor"))
        except (TypeError, ValueError):
            continue
        if f <= 0:
            continue
        db.execute(
            sql,
            {
                "code": code,
                "trade_date": td,
                "adj_factor": f,
                "source": str(r.get("source") or source),
                "updated_at": now,
            },
        )
        n += 1
    db.commit()
    return n


def load_adj_factors_from_db(db: Session, code: str) -> List[Tuple[date, float]]:
    code_n = normalize_a_share_code(code)
    rows = db.execute(
        text(
            """
            SELECT trade_date, adj_factor
            FROM stock_adj_factor
            WHERE code = :code
            ORDER BY trade_date ASC
            """
        ),
        {"code": code_n},
    ).fetchall()
    out: List[Tuple[date, float]] = []
    for r in rows:
        td = r[0]
        if isinstance(td, datetime):
            td = td.date()
        if not isinstance(td, date):
            td = _parse_trade_date(td)
        if td is None:
            continue
        try:
            f = float(r[1])
        except (TypeError, ValueError):
            continue
        if f > 0:
            out.append((td, f))
    return out


def _latest_factor_meta(
    db: Session, code: str
) -> Tuple[Optional[date], Optional[datetime], Optional[str]]:
    row = db.execute(
        text(
            """
            SELECT trade_date, updated_at, source
            FROM stock_adj_factor
            WHERE code = :code
            ORDER BY trade_date DESC
            LIMIT 1
            """
        ),
        {"code": normalize_a_share_code(code)},
    ).fetchone()
    if not row:
        return None, None, None
    td = row[0]
    if isinstance(td, datetime):
        td = td.date()
    elif not isinstance(td, date):
        td = _parse_trade_date(td)
    upd = row[1]
    if isinstance(upd, str):
        try:
            upd = datetime.fromisoformat(upd)
        except ValueError:
            upd = None
    return td, upd if isinstance(upd, datetime) else None, row[2]


def ensure_adj_factors(
    db: Session,
    code: str,
    *,
    max_age_days: int = DEFAULT_FACTOR_MAX_AGE_DAYS,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """确保库内有较新的前复权因子；不足则拉新浪并 UPSERT。

    返回：{ factors: [(date,f),...], factor_fetched: bool, source, adj_factor_asof }
    """
    code_n = normalize_a_share_code(code)
    if not code_n.isdigit() or len(code_n) != 6:
        raise AdjQuotesError("前复权计算目前仅支持 A 股（6 位代码），港股暂不支持")

    latest_td, updated_at, source = _latest_factor_meta(db, code_n)
    fresh = False
    if latest_td is not None and not force_refresh:
        # 以因子最新交易日距今天数判断新鲜度
        age = (date.today() - latest_td).days
        fresh = age <= max(0, int(max_age_days))

    factor_fetched = False
    if not fresh:
        rows = fetch_sina_qfq_factors(code_n)
        upsert_adj_factors(db, rows, source=SOURCE_AKSHARE_SINA_QFQ)
        factor_fetched = True
        source = SOURCE_AKSHARE_SINA_QFQ

    factors = load_adj_factors_from_db(db, code_n)
    if not factors:
        raise AdjQuotesError("复权因子为空，无法按前复权计算")
    asof = factors[-1][0]
    return {
        "factors": factors,
        "factor_fetched": factor_fetched,
        "source": source or SOURCE_AKSHARE_SINA_QFQ,
        "adj_factor_asof": _bar_date_str(asof),
    }


def apply_qfq_to_bars(
    bars: Sequence[Dict[str, Any]],
    factors: Sequence[Tuple[date, float]],
) -> List[Dict[str, Any]]:
    """将不复权 bars 现算为前复权（OHLC 乘 f_t/f_T；volume/amount 不变）。

    因子按日期升序，对 bar 日期 forward-fill；
    若某 bar 早于全部因子日，则使用首个因子（与「以最新为锚的前复权」常见处理一致，
    避免整段失败；若完全无因子则抛错）。
    """
    if not bars:
        return []
    if not factors:
        raise AdjQuotesError("缺少复权因子，无法现算前复权价格")

    factors_sorted = sorted(factors, key=lambda x: x[0])
    f_T = float(factors_sorted[-1][1])
    if f_T <= 0:
        raise AdjQuotesError("锚定复权因子无效")

    # 指针式 forward-fill
    fi = 0
    last_f: Optional[float] = None
    # 若第一根 bar 早于首个因子，先用首因子
    first_f = float(factors_sorted[0][1])

    out: List[Dict[str, Any]] = []
    for bar in bars:
        bd = _parse_trade_date(bar.get("date"))
        if bd is None:
            out.append(dict(bar))
            continue
        while fi < len(factors_sorted) and factors_sorted[fi][0] <= bd:
            last_f = float(factors_sorted[fi][1])
            fi += 1
        f_t = last_f if last_f is not None else first_f
        if f_t <= 0:
            raise AdjQuotesError(f"{_bar_date_str(bd)} 复权因子无效")
        scale = f_t / f_T
        nb = dict(bar)
        for key in ("open", "high", "low", "close", "pre_close"):
            if key not in nb or nb[key] is None:
                continue
            try:
                nb[key] = round(float(nb[key]) * scale, 6)
            except (TypeError, ValueError):
                pass
        nb["price_adjust"] = "qfq"
        nb["adj_scale"] = scale
        out.append(nb)
    return out
