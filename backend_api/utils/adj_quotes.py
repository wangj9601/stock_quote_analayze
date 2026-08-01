"""不复权行情 + 复权因子 → 查询/内存层现算前复权。

因子来源：
  - 主源：AkShare 新浪 `stock_zh_a_daily(adjust=\"qfq-factor\")`
  - 备用：BaoStock `query_adjust_factor` → `foreAdjustFactor`

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
SOURCE_BAOSTOCK_QFQ = "baostock_qfq"
DEFAULT_FACTOR_MAX_AGE_DAYS = 5

FACTOR_SOURCE_AUTO = "auto"
FACTOR_SOURCE_SINA = "sina"
FACTOR_SOURCE_BAOSTOCK = "baostock"
FACTOR_SOURCE_CHOICES = (
    FACTOR_SOURCE_AUTO,
    FACTOR_SOURCE_SINA,
    FACTOR_SOURCE_BAOSTOCK,
)


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


def to_baostock_symbol(code: str) -> str:
    """A 股 6 位代码 → BaoStock symbol（sh.600519 / sz.000001）。"""
    sina = to_sina_symbol(code)
    return f"{sina[:2]}.{sina[2:]}"


def normalize_factor_source(raw: Any) -> str:
    s = str(raw or FACTOR_SOURCE_AUTO).strip().lower() or FACTOR_SOURCE_AUTO
    if s in ("akshare", "akshare_sina", "sina_qfq"):
        return FACTOR_SOURCE_SINA
    if s in ("bao", "baostock_qfq"):
        return FACTOR_SOURCE_BAOSTOCK
    if s not in FACTOR_SOURCE_CHOICES:
        raise AdjQuotesError(
            "factor_source 仅支持 auto / sina / baostock"
        )
    return s


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


def _is_valid_factor_trade_date(td: date) -> bool:
    """过滤新浪等源返回的 1900-01-01 占位无效日。"""
    return td is not None and td > date(1900, 1, 1)


def _factor_source_tag(factor_source: str) -> Optional[str]:
    """UI/参数 factor_source → 库内 source 标签；auto 返回 None。"""
    src = normalize_factor_source(factor_source)
    if src == FACTOR_SOURCE_SINA:
        return SOURCE_AKSHARE_SINA_QFQ
    if src == FACTOR_SOURCE_BAOSTOCK:
        return SOURCE_BAOSTOCK_QFQ
    return None


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
                if td is None or not _is_valid_factor_trade_date(td):
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
    raise AdjQuotesError(f"获取新浪复权因子失败：{last_err}")


def fetch_baostock_qfq_factors(
    code: str,
    *,
    start_date: str = "1990-01-01",
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """调用 BaoStock query_adjust_factor，取 foreAdjustFactor 作为前复权因子。"""
    try:
        import baostock as bs
    except ImportError as e:
        raise AdjQuotesError(
            "未安装 baostock，无法使用备用因子源。请执行：pip install baostock"
        ) from e

    symbol = to_baostock_symbol(code)
    end = end_date or date.today().strftime("%Y-%m-%d")
    lg = None
    try:
        lg = bs.login()
        if getattr(lg, "error_code", "0") not in ("0", 0, None, ""):
            raise AdjQuotesError(
                f"BaoStock 登录失败：{getattr(lg, 'error_msg', lg)}"
            )
        rs = bs.query_adjust_factor(
            code=symbol, start_date=start_date, end_date=end
        )
        if getattr(rs, "error_code", "0") not in ("0", 0, None, ""):
            raise AdjQuotesError(
                f"BaoStock 查询复权因子失败（{symbol}）："
                f"{getattr(rs, 'error_msg', rs)}"
            )
        fields = list(getattr(rs, "fields", []) or [])
        field_l = {str(f).lower(): i for i, f in enumerate(fields)}
        date_i = field_l.get("dividoperatedate")
        factor_i = field_l.get("foreadjustfactor")
        if date_i is None or factor_i is None:
            # 兜底按常见列序：code, dividOperateDate, foreAdjustFactor, ...
            date_i = 1 if len(fields) > 1 else 0
            factor_i = 2 if len(fields) > 2 else 1

        rows: List[Dict[str, Any]] = []
        while getattr(rs, "error_code", "0") in ("0", 0, None, "") and rs.next():
            raw = rs.get_row_data()
            if not raw:
                continue
            td = _parse_trade_date(raw[date_i] if date_i < len(raw) else None)
            if td is None or not _is_valid_factor_trade_date(td):
                continue
            try:
                f = float(raw[factor_i])
            except (TypeError, ValueError, IndexError):
                continue
            if f <= 0:
                continue
            rows.append(
                {
                    "code": normalize_a_share_code(code),
                    "trade_date": td,
                    "adj_factor": f,
                    "source": SOURCE_BAOSTOCK_QFQ,
                }
            )
        if not rows:
            raise AdjQuotesError(f"BaoStock 复权因子为空（{symbol}）")
        rows.sort(key=lambda x: x["trade_date"])
        return rows
    finally:
        try:
            if lg is not None:
                bs.logout()
        except Exception:
            pass


def fetch_qfq_factors(
    code: str,
    *,
    factor_source: str = FACTOR_SOURCE_AUTO,
) -> Tuple[List[Dict[str, Any]], str]:
    """按策略拉取因子，返回 (rows, source_tag)。"""
    src = normalize_factor_source(factor_source)
    errors: List[str] = []

    def _try_sina() -> List[Dict[str, Any]]:
        return fetch_sina_qfq_factors(code)

    def _try_bao() -> List[Dict[str, Any]]:
        return fetch_baostock_qfq_factors(code)

    if src == FACTOR_SOURCE_SINA:
        return _try_sina(), SOURCE_AKSHARE_SINA_QFQ
    if src == FACTOR_SOURCE_BAOSTOCK:
        return _try_bao(), SOURCE_BAOSTOCK_QFQ

    # auto：新浪 → BaoStock
    try:
        return _try_sina(), SOURCE_AKSHARE_SINA_QFQ
    except AdjQuotesError as e:
        errors.append(f"新浪：{e.message}")
        logger.warning("新浪复权因子失败，尝试 BaoStock：%s", e.message)
    except Exception as e:
        errors.append(f"新浪：{e}")
        logger.warning("新浪复权因子异常，尝试 BaoStock：%s", e)

    try:
        return _try_bao(), SOURCE_BAOSTOCK_QFQ
    except AdjQuotesError as e:
        errors.append(f"BaoStock：{e.message}")
        raise AdjQuotesError(
            "获取复权因子失败（已尝试新浪与 BaoStock）。" + "；".join(errors)
        ) from e
    except Exception as e:
        errors.append(f"BaoStock：{e}")
        raise AdjQuotesError(
            "获取复权因子失败（已尝试新浪与 BaoStock）。" + "；".join(errors)
        ) from e


def upsert_adj_factors(
    db: Session,
    rows: Sequence[Dict[str, Any]],
    *,
    source: str = SOURCE_AKSHARE_SINA_QFQ,
) -> int:
    """PostgreSQL UPSERT 写入 stock_adj_factor（冲突键含 source，多源并存）。"""
    if not rows:
        return 0
    now = datetime.now()
    n = 0
    sql = text(
        """
        INSERT INTO stock_adj_factor (code, trade_date, adj_factor, source, updated_at)
        VALUES (:code, :trade_date, :adj_factor, :source, :updated_at)
        ON CONFLICT (code, trade_date, source) DO UPDATE SET
            adj_factor = EXCLUDED.adj_factor,
            updated_at = EXCLUDED.updated_at
        """
    )
    for r in rows:
        code = normalize_a_share_code(str(r.get("code") or ""))
        td = r.get("trade_date")
        if isinstance(td, str):
            td = _parse_trade_date(td)
        if not code or not isinstance(td, date) or not _is_valid_factor_trade_date(td):
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


def load_adj_factors_from_db(
    db: Session,
    code: str,
    *,
    source: str,
) -> List[Tuple[date, float]]:
    """按 code + source 加载因子序列（不同来源互不混用）。"""
    code_n = normalize_a_share_code(code)
    src = str(source or "").strip()
    if not src:
        raise AdjQuotesError("加载复权因子时必须指定 source")
    rows = db.execute(
        text(
            """
            SELECT trade_date, adj_factor
            FROM stock_adj_factor
            WHERE code = :code AND source = :source
              AND trade_date > DATE '1900-01-01'
            ORDER BY trade_date ASC
            """
        ),
        {"code": code_n, "source": src},
    ).fetchall()
    out: List[Tuple[date, float]] = []
    for r in rows:
        td = r[0]
        if isinstance(td, datetime):
            td = td.date()
        if not isinstance(td, date):
            td = _parse_trade_date(td)
        if td is None or not _is_valid_factor_trade_date(td):
            continue
        try:
            f = float(r[1])
        except (TypeError, ValueError):
            continue
        if f > 0:
            out.append((td, f))
    return out


def _latest_factor_meta(
    db: Session,
    code: str,
    *,
    source: str,
) -> Tuple[Optional[date], Optional[datetime], Optional[str]]:
    row = db.execute(
        text(
            """
            SELECT trade_date, updated_at, source
            FROM stock_adj_factor
            WHERE code = :code AND source = :source
              AND trade_date > DATE '1900-01-01'
            ORDER BY trade_date DESC
            LIMIT 1
            """
        ),
        {"code": normalize_a_share_code(code), "source": str(source)},
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


def _is_fresh(latest_td: Optional[date], max_age_days: int) -> bool:
    if latest_td is None:
        return False
    age = (date.today() - latest_td).days
    return age <= max(0, int(max_age_days))


def ensure_adj_factors(
    db: Session,
    code: str,
    *,
    max_age_days: int = DEFAULT_FACTOR_MAX_AGE_DAYS,
    force_refresh: bool = False,
    factor_source: str = FACTOR_SOURCE_AUTO,
) -> Dict[str, Any]:
    """确保库内有较新的前复权因子；不足则按 factor_source 拉取并 UPSERT。

    factor_source: auto | sina | baostock
    按 source 分桶存储与读取，新浪与 BaoStock 互不覆盖。
    返回：{ factors, factor_fetched, source, adj_factor_asof, factor_source }
    """
    code_n = normalize_a_share_code(code)
    if not code_n.isdigit() or len(code_n) != 6:
        raise AdjQuotesError("前复权计算目前仅支持 A 股（6 位代码），港股暂不支持")

    src_pref = normalize_factor_source(factor_source)
    factor_fetched = False
    source: Optional[str] = None

    if not force_refresh:
        if src_pref == FACTOR_SOURCE_AUTO:
            for cand in (SOURCE_AKSHARE_SINA_QFQ, SOURCE_BAOSTOCK_QFQ):
                latest_td, _, src = _latest_factor_meta(db, code_n, source=cand)
                if _is_fresh(latest_td, max_age_days):
                    source = src or cand
                    break
        else:
            tag = _factor_source_tag(src_pref)
            assert tag is not None
            latest_td, _, src = _latest_factor_meta(db, code_n, source=tag)
            if _is_fresh(latest_td, max_age_days):
                source = src or tag

    if source is None:
        rows, fetched_source = fetch_qfq_factors(code_n, factor_source=src_pref)
        upsert_adj_factors(db, rows, source=fetched_source)
        factor_fetched = True
        source = fetched_source

    factors = load_adj_factors_from_db(db, code_n, source=source)
    if not factors:
        raise AdjQuotesError("复权因子为空，无法按前复权计算")
    asof = factors[-1][0]
    return {
        "factors": factors,
        "factor_fetched": factor_fetched,
        "source": source or SOURCE_AKSHARE_SINA_QFQ,
        "adj_factor_asof": _bar_date_str(asof),
        "factor_source": src_pref,
    }


def apply_qfq_to_bars(
    bars: Sequence[Dict[str, Any]],
    factors: Sequence[Tuple[date, float]],
) -> List[Dict[str, Any]]:
    """将不复权 bars 现算为前复权（OHLC 乘 f_t/f_T；volume/amount 不变）。

    因子按日期升序，对 bar 日期 forward-fill；
    若某 bar 早于全部因子日，则使用首个因子。
    """
    if not bars:
        return []
    if not factors:
        raise AdjQuotesError("缺少复权因子，无法现算前复权价格")

    factors_sorted = sorted(factors, key=lambda x: x[0])
    f_T = float(factors_sorted[-1][1])
    if f_T <= 0:
        raise AdjQuotesError("锚定复权因子无效")

    fi = 0
    last_f: Optional[float] = None
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
