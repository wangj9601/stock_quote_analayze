"""不复权行情 + 复权因子 → 查询/内存层现算前复权。

内部约定（与 BaoStock / 港股新浪一致）：
  P_qfq = P_raw * f_t / f_T（f_T 为序列最新因子日，约 f_T≈1；历史因子通常 ≤1）。
  volume / amount 不乘因子。因子按日对齐时对缺口做 forward-fill。

因子来源：
  - A 股主源：AkShare 新浪 `stock_zh_a_daily(adjust=\"qfq-factor\")`
    新浪原始 qfq-factor 为「历史>1、最新≈1」的倒数形态；入库前取倒数归一化
    为内部约定（历史≤1、最新≈1），见 normalize_sina_factor_to_internal。
    符号：沪 sh / 深 sz / 北交所 bj（不可把 92xxxx 误标为 sh）。
  - A 股备用：BaoStock `query_adjust_factor` → `foreAdjustFactor`（原样入库，已符合内部约定）。
    BaoStock 仅支持沪深，北交所不走备用源；港股亦不支持 BaoStock（无 hk. 复权因子）。
  - 港股主源：AkShare 新浪 `stock_hk_daily(symbol, adjust=\"qfq-factor\")`
    实测（如 00700）原始序列已是「最新≈1、历史更小」，与内部约定一致，
    **入库不取倒数**（切勿照搬 A 股新浪倒数逻辑）。代码统一 5 位补零。
    无除权事件时新浪常只返回 ``1900-01-01`` 占位一行（factor=1）；过滤占位后
    按单位因子 1.0 合成（与 AkShare 自身 ``len(qfq_factor)==1`` 不复权行为一致）。
  - 港股备用：东财 `stock_hk_hist` 不复权/前复权收盘比推导因子（``akshare_em_hk_qfq``）。
    BaoStock 不可用时的次优回退，供形态/levels 现算 qfq。

factor_source=auto：A 股=归一化新浪 → BaoStock（北交所除外）；
  港股=新浪（含占位→单位因子）→ 东财收盘比。
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SOURCE_AKSHARE_SINA_QFQ = "akshare_sina_qfq"
SOURCE_AKSHARE_SINA_HK_QFQ = "akshare_sina_hk_qfq"
SOURCE_AKSHARE_EM_HK_QFQ = "akshare_em_hk_qfq"
SOURCE_BAOSTOCK_QFQ = "baostock_qfq"
DEFAULT_FACTOR_MAX_AGE_DAYS = 5
# 批量前复权补因子：是否限速 + 间隔秒数（见 ADJ_FACTOR_FETCH_THROTTLE_*）
DEFAULT_FACTOR_FETCH_THROTTLE_ENABLED = True
DEFAULT_FACTOR_FETCH_INTERVAL_SEC = 3.0

_fetch_interval_lock = threading.Lock()
_last_third_party_fetch_mono: float = 0.0

FACTOR_SOURCE_AUTO = "auto"
FACTOR_SOURCE_SINA = "sina"
FACTOR_SOURCE_BAOSTOCK = "baostock"
FACTOR_SOURCE_CHOICES = (
    FACTOR_SOURCE_AUTO,
    FACTOR_SOURCE_SINA,
    FACTOR_SOURCE_BAOSTOCK,
)

# 与 VSB_BOARD_PREFIX_GROUPS["BJ"] 对齐：北交所/北证代码段
BSE_CODE_PREFIXES = ("43", "83", "87", "88", "92")


class AdjQuotesError(Exception):
    """前复权现算/因子拉取业务错误（可直接展示给用户）。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def normalize_a_share_code(code: str) -> str:
    s = str(code or "").strip().upper()
    if s.startswith(("SH", "SZ", "BJ")) and len(s) > 2:
        s = s[2:]
    return s


def normalize_hk_code(code: str) -> str:
    """港股代码归一化为 5 位（``700`` / ``0700`` / ``HK00700`` → ``00700``）。"""
    try:
        from backend_api.utils.equity_code import normalize_equity_code
    except ImportError:
        from utils.equity_code import normalize_equity_code  # type: ignore

    c = normalize_equity_code(code)
    if not c.isdigit() or len(c) != 5:
        raise AdjQuotesError(f"仅支持港股 5 位代码获取复权因子，当前：{code}")
    return c


def normalize_adj_code(code: str) -> str:
    """复权因子用代码：港股 5 位 / A 股 6 位（去交易所前缀并补零）。"""
    try:
        from backend_api.utils.equity_code import (
            is_hk_equity_code,
            normalize_equity_code,
        )
    except ImportError:
        from utils.equity_code import (  # type: ignore
            is_hk_equity_code,
            normalize_equity_code,
        )

    c = normalize_equity_code(code)
    if not c or not c.isdigit() or len(c) not in (5, 6):
        raise AdjQuotesError(f"股票代码格式错误（A股6位，港股5位），当前：{code}")
    if is_hk_equity_code(c):
        return c
    return normalize_a_share_code(c)


def is_hk_adj_code(code: str) -> bool:
    """是否港股复权代码（归一化后 5 位纯数字）。"""
    try:
        from backend_api.utils.equity_code import is_hk_equity_code
    except ImportError:
        from utils.equity_code import is_hk_equity_code  # type: ignore

    return is_hk_equity_code(code)


def is_bse_a_share_code(code: str) -> bool:
    """是否北交所/北证 6 位 A 股（43/83/87/88/92 开头）。"""
    c = normalize_a_share_code(code)
    return len(c) == 6 and c.isdigit() and c.startswith(BSE_CODE_PREFIXES)


def to_sina_symbol(code: str) -> str:
    """A 股 6 位代码 → 新浪 symbol（sh600519 / sz000001 / bj920263）。

    注意：不可把北交所 92xxxx 误标为 sh（旧规则 startswith('9') 会踩坑）；
    新浪北交所前缀为 bj。
    """
    c = normalize_a_share_code(code)
    if not c.isdigit() or len(c) != 6:
        raise AdjQuotesError(f"仅支持 A 股 6 位代码获取复权因子，当前：{code}")
    if is_bse_a_share_code(c):
        return f"bj{c}"
    # 5/6/9：沪市基金与主板、沪 B（900xxx）；92 已在上方归 bj
    if c.startswith(("5", "6", "9")):
        return f"sh{c}"
    return f"sz{c}"


def to_baostock_symbol(code: str) -> str:
    """A 股 6 位代码 → BaoStock symbol（sh.600519 / sz.000001）。

    BaoStock 仅支持 sh./sz.，不支持北交所；对北交所直接抛可读错误，避免误用 sh.92xxxx。
    """
    c = normalize_a_share_code(code)
    if not c.isdigit() or len(c) != 6:
        raise AdjQuotesError(f"仅支持 A 股 6 位代码获取复权因子，当前：{code}")
    if is_bse_a_share_code(c):
        raise AdjQuotesError(
            f"BaoStock 不支持北交所代码（{c}），仅支持沪深 sh./sz.；"
            "请改用新浪因子、库内 stock_adj_factor，或不复权计算"
        )
    sina = to_sina_symbol(c)
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


def normalize_sina_factor_to_internal(factor: float) -> float:
    """将新浪原始 qfq-factor 归一化为内部约定（取倒数）。

    新浪：历史因子通常 >1、最新≈1；内部/BaoStock：历史通常 ≤1、最新≈1。
    factor 必须 >0，否则抛 AdjQuotesError。
    """
    try:
        f = float(factor)
    except (TypeError, ValueError) as e:
        raise AdjQuotesError(f"新浪复权因子无效：{factor}") from e
    if f <= 0:
        raise AdjQuotesError(f"新浪复权因子必须为正数，当前：{factor}")
    return 1.0 / f


def _factor_source_tag(factor_source: str, *, market: str = "CN") -> Optional[str]:
    """UI/参数 factor_source → 库内 source 标签；auto 返回 None。"""
    src = normalize_factor_source(factor_source)
    if market == "HK":
        if src == FACTOR_SOURCE_BAOSTOCK:
            raise AdjQuotesError(
                "BaoStock 不支持港股复权因子；请使用 auto/sina"
                "（新浪 stock_hk_daily，失败可回退东财 stock_hk_hist）"
            )
        if src == FACTOR_SOURCE_SINA:
            return SOURCE_AKSHARE_SINA_HK_QFQ
        # auto：多源候选，不落单一标签
        return None
    if src == FACTOR_SOURCE_SINA:
        return SOURCE_AKSHARE_SINA_QFQ
    if src == FACTOR_SOURCE_BAOSTOCK:
        return SOURCE_BAOSTOCK_QFQ
    return None


def _hk_unitary_factor_rows(
    code_n: str,
    *,
    source: str,
    note: str = "",
) -> List[Dict[str, Any]]:
    """无除权事件时合成单位因子（最新日=1），现算等价于不复权。"""
    if note:
        logger.info("港股复权使用单位因子 code=%s source=%s %s", code_n, source, note)
    return [
        {
            "code": code_n,
            "trade_date": date.today(),
            "adj_factor": 1.0,
            "source": source,
        }
    ]


def _parse_hk_sina_factor_frame(df: Any, code_n: str) -> Tuple[List[Dict[str, Any]], int]:
    """解析港股新浪 qfq-factor DataFrame。

    返回 (有效行, 占位无效日行数)。有效行已按 trade_date 升序。
    """
    rows: List[Dict[str, Any]] = []
    placeholder_n = 0
    cols = {str(c).lower(): c for c in df.columns}
    date_col = cols.get("date") or list(df.columns)[0]
    factor_col = (
        cols.get("qfq_factor")
        or cols.get("adj_factor")
        or cols.get("factor")
        or (list(df.columns)[1] if len(df.columns) > 1 else list(df.columns)[0])
    )
    for _, r in df.iterrows():
        td = _parse_trade_date(r.get(date_col))
        if td is None:
            continue
        if not _is_valid_factor_trade_date(td):
            placeholder_n += 1
            continue
        try:
            f = float(r.get(factor_col))
        except (TypeError, ValueError):
            continue
        if f <= 0:
            continue
        rows.append(
            {
                "code": code_n,
                "trade_date": td,
                "adj_factor": f,
                "source": SOURCE_AKSHARE_SINA_HK_QFQ,
            }
        )
    rows.sort(key=lambda x: x["trade_date"])
    return rows, placeholder_n


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on", "y")


def third_party_fetch_throttle_enabled() -> bool:
    """是否启用第三方复权因子拉取限速：ADJ_FACTOR_FETCH_THROTTLE_ENABLED。"""
    return _env_flag(
        "ADJ_FACTOR_FETCH_THROTTLE_ENABLED",
        DEFAULT_FACTOR_FETCH_THROTTLE_ENABLED,
    )


def third_party_fetch_interval_sec() -> float:
    """限速开启时的最小间隔（秒）：ADJ_FACTOR_FETCH_INTERVAL_SEC。"""
    try:
        return max(
            0.0,
            float(
                os.getenv("ADJ_FACTOR_FETCH_INTERVAL_SEC")
                or DEFAULT_FACTOR_FETCH_INTERVAL_SEC
            ),
        )
    except ValueError:
        return DEFAULT_FACTOR_FETCH_INTERVAL_SEC


def throttle_third_party_fetch(*, label: str = "") -> None:
    """批量补齐因子时限速，避免新浪/BaoStock IP 限制。

    需 ADJ_FACTOR_FETCH_THROTTLE_ENABLED=true，并配置 ADJ_FACTOR_FETCH_INTERVAL_SEC。
    首次调用不等待；之后保证两次第三方请求间隔 ≥ 配置秒数。
    读库命中不会走到此处。
    """
    global _last_third_party_fetch_mono
    if not third_party_fetch_throttle_enabled():
        return
    interval = third_party_fetch_interval_sec()
    if interval <= 0:
        return
    with _fetch_interval_lock:
        now = time.monotonic()
        if _last_third_party_fetch_mono > 0:
            wait = interval - (now - _last_third_party_fetch_mono)
            if wait > 0:
                logger.info(
                    "复权因子第三方限速等待 %.1fs（间隔 %.1fs）%s",
                    wait,
                    interval,
                    f" [{label}]" if label else "",
                )
                time.sleep(wait)
        _last_third_party_fetch_mono = time.monotonic()


def _friendly_sina_factor_error(symbol: str, err: BaseException) -> str:
    """将 akshare/新浪侧常见解析失败转为可读说明。

    新浪 qfq.js 经 akshare 用 eval 解析；错误 symbol（如北交所误标 sh）常返回
    404 HTML，触发 SyntaxError: invalid syntax (<string>, line 1)。
    """
    msg = str(err).strip() or err.__class__.__name__
    low = msg.lower()
    if "invalid syntax" in low or isinstance(err, SyntaxError):
        return (
            f"新浪复权因子响应无法解析（{symbol}）：{msg}。"
            "常见原因是市场前缀错误或该代码无因子数据"
        )
    return f"获取新浪复权因子失败：{msg}"


def fetch_sina_qfq_factors(code: str) -> List[Dict[str, Any]]:
    """调用 AkShare 新浪接口拉取前复权因子，入库前取倒数归一化为内部约定。"""
    import akshare as ak

    throttle_third_party_fetch(label=f"sina:{normalize_a_share_code(code)}")
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
                    f_raw = float(r.get(factor_col))
                except (TypeError, ValueError):
                    continue
                if f_raw <= 0:
                    continue
                # 新浪原始为倒数形态 → 归一化为内部约定后再入库
                f = normalize_sina_factor_to_internal(f_raw)
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
    raise AdjQuotesError(_friendly_sina_factor_error(symbol, last_err or Exception("未知错误")))


def fetch_hk_sina_qfq_factors(code: str) -> List[Dict[str, Any]]:
    """调用 AkShare 港股新浪接口拉取前复权因子（原样入库，不取倒数）。

    ``stock_hk_daily(..., adjust=\"qfq-factor\")`` 实测序列已符合内部约定：
    最新因子日 ≈1、更早事件日更小（如 00700）。现算仍用
    ``P_qfq = P_raw × f_t / f_T``（见 apply_qfq_to_bars），故不可对 A 股新浪
    做「取倒数」照搬。接口要求 5 位补零 symbol（``700`` / ``100`` 会失败，须 ``00700`` / ``00100``）。

    无除权事件票（如部分新股 ``00100``）新浪常只返回 ``1900-01-01`` 占位一行；
    过滤占位后为空时合成单位因子 1.0（与 AkShare ``len==1`` 时直接返回不复权行情一致），
    不再报「解析为空」。
    """
    import akshare as ak

    code_n = normalize_hk_code(code)
    throttle_third_party_fetch(label=f"sina_hk:{code_n}")
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            df = ak.stock_hk_daily(symbol=code_n, adjust="qfq-factor")
            if df is None or getattr(df, "empty", True):
                raise AdjQuotesError(
                    f"港股新浪未返回复权因子（{code_n}）。"
                    "请确认代码为 5 位补零（如 00100），或改用 auto 走东财回退"
                )
            rows, placeholder_n = _parse_hk_sina_factor_frame(df, code_n)
            if not rows:
                # 仅占位日（1900-01-01）或因子列全无效 → 视为无除权事件
                if placeholder_n > 0 or len(df) > 0:
                    return _hk_unitary_factor_rows(
                        code_n,
                        source=SOURCE_AKSHARE_SINA_HK_QFQ,
                        note=(
                            f"新浪仅占位/无有效因子日（rows={len(df)}, "
                            f"placeholder={placeholder_n}）"
                        ),
                    )
                raise AdjQuotesError(
                    f"港股新浪复权因子解析为空（{code_n}）："
                    f"返回 {len(df)} 行但无有效 date/qfq_factor"
                )
            # 轻量形态校验：最新应接近 1；若明显呈「历史>1」则告警（仍按原样入库）
            f_latest = float(rows[-1]["adj_factor"])
            f_oldest = float(rows[0]["adj_factor"])
            if f_latest > 0 and abs(f_latest - 1.0) > 0.15:
                logger.warning(
                    "港股复权因子最新值偏离 1 较多 code=%s latest=%s oldest=%s",
                    code_n,
                    f_latest,
                    f_oldest,
                )
            if f_oldest > f_latest * 1.05 and f_oldest > 1.05:
                logger.warning(
                    "港股复权因子疑似倒数形态（未取倒数）code=%s oldest=%s latest=%s",
                    code_n,
                    f_oldest,
                    f_latest,
                )
            return rows
        except AdjQuotesError:
            raise
        except Exception as e:
            last_err = e
            sleep_s = (attempt + 1) * 1.5 + random.uniform(0.2, 0.8)
            logger.warning(
                "拉取港股 qfq-factor 失败 %s attempt=%s: %s", code_n, attempt + 1, e
            )
            time.sleep(sleep_s)
    raise AdjQuotesError(
        _friendly_sina_factor_error(code_n, last_err or Exception("未知错误"))
    )


def _em_hk_hist_close_series(df: Any) -> List[Tuple[date, float]]:
    """从东财 stock_hk_hist DataFrame 提取 (date, close)。兼容中英文列名。"""
    if df is None or getattr(df, "empty", True):
        return []
    cols = {str(c).strip().lower(): c for c in df.columns}
    date_col = (
        cols.get("日期")
        or cols.get("date")
        or next((c for k, c in cols.items() if "日期" in str(k) or k == "date"), None)
        or list(df.columns)[0]
    )
    # 东财列顺序：日期, 开盘, 收盘, ...
    close_col = cols.get("收盘") or cols.get("close")
    if close_col is None:
        # 按常见位置：第 3 列（index 2）为收盘
        close_col = list(df.columns)[2] if len(df.columns) > 2 else list(df.columns)[-1]
    out: List[Tuple[date, float]] = []
    for _, r in df.iterrows():
        td = _parse_trade_date(r.get(date_col))
        if td is None or not _is_valid_factor_trade_date(td):
            continue
        try:
            c = float(r.get(close_col))
        except (TypeError, ValueError):
            continue
        if c > 0:
            out.append((td, c))
    out.sort(key=lambda x: x[0])
    return out


def fetch_hk_em_qfq_factors(
    code: str,
    *,
    start_date: str = "19900101",
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """东财港股备用：用 stock_hk_hist 不复权/前复权收盘比推导前复权因子。

    BaoStock 不支持港股；新浪 qfq-factor 失败或不可用时的次优回退。
    公式：f_raw(t)=close_qfq(t)/close_raw(t)，再除以最新日使 f_T≈1（内部约定）。
    仅保留因子变化日 + 首末日，避免按日全量入库。
    """
    import akshare as ak

    code_n = normalize_hk_code(code)
    throttle_third_party_fetch(label=f"em_hk:{code_n}")
    end = end_date or date.today().strftime("%Y%m%d")
    start = str(start_date or "19900101").replace("-", "")
    if len(start) == 8 and start.isdigit():
        pass
    else:
        start = "19900101"

    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            df_raw = ak.stock_hk_hist(
                symbol=code_n,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="",
            )
            df_qfq = ak.stock_hk_hist(
                symbol=code_n,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            raw_s = _em_hk_hist_close_series(df_raw)
            qfq_s = _em_hk_hist_close_series(df_qfq)
            if not raw_s or not qfq_s:
                raise AdjQuotesError(
                    f"东财港股行情为空，无法推导复权因子（{code_n}）"
                )
            qfq_map = {d: c for d, c in qfq_s}
            ratios: List[Tuple[date, float]] = []
            for td, raw_c in raw_s:
                q = qfq_map.get(td)
                if q is None or raw_c <= 0:
                    continue
                ratios.append((td, float(q) / float(raw_c)))
            if not ratios:
                raise AdjQuotesError(
                    f"东财港股复权比为空（{code_n}）：raw/qfq 日期无法对齐"
                )
            # 全体 ≈1 → 无除权，单位因子即可
            if all(abs(r - 1.0) < 1e-6 for _, r in ratios):
                return _hk_unitary_factor_rows(
                    code_n,
                    source=SOURCE_AKSHARE_EM_HK_QFQ,
                    note="东财 raw/qfq 收盘一致",
                )
            f_T = float(ratios[-1][1])
            if f_T <= 0:
                raise AdjQuotesError(f"东财港股最新复权比无效（{code_n}）：{f_T}")
            # 归一化到最新≈1，并只保留变化点
            normed: List[Tuple[date, float]] = [
                (td, float(r) / f_T) for td, r in ratios
            ]
            kept: List[Tuple[date, float]] = [normed[0]]
            for i in range(1, len(normed)):
                prev_f = kept[-1][1]
                cur_f = normed[i][1]
                if abs(cur_f - prev_f) > 1e-8:
                    kept.append(normed[i])
            if kept[-1][0] != normed[-1][0]:
                kept.append(normed[-1])
            return [
                {
                    "code": code_n,
                    "trade_date": td,
                    "adj_factor": f,
                    "source": SOURCE_AKSHARE_EM_HK_QFQ,
                }
                for td, f in kept
            ]
        except AdjQuotesError:
            raise
        except Exception as e:
            last_err = e
            sleep_s = (attempt + 1) * 1.5 + random.uniform(0.2, 0.8)
            logger.warning(
                "拉取东财港股复权比失败 %s attempt=%s: %s", code_n, attempt + 1, e
            )
            time.sleep(sleep_s)
    raise AdjQuotesError(
        f"获取东财港股复权因子失败（{code_n}）："
        f"{last_err or '未知错误'}"
    )


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

    throttle_third_party_fetch(label=f"baostock:{normalize_a_share_code(code)}")
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
    """按策略拉取因子，返回 (rows, source_tag)。

    港股：新浪 qfq-factor（含占位→单位因子）→ 东财收盘比；BaoStock 不支持港股。
    """
    src = normalize_factor_source(factor_source)
    errors: List[str] = []

    if is_hk_adj_code(code):
        code_n = normalize_hk_code(code)
        if src == FACTOR_SOURCE_BAOSTOCK:
            raise AdjQuotesError(
                f"BaoStock 不支持港股（{code_n}，无 hk. query_adjust_factor）；"
                "请使用 auto/sina（新浪，失败时 auto 可回退东财）"
            )

        def _try_hk_sina() -> List[Dict[str, Any]]:
            return fetch_hk_sina_qfq_factors(code_n)

        def _try_hk_em() -> List[Dict[str, Any]]:
            return fetch_hk_em_qfq_factors(code_n)

        if src == FACTOR_SOURCE_SINA:
            try:
                return _try_hk_sina(), SOURCE_AKSHARE_SINA_HK_QFQ
            except AdjQuotesError as e:
                raise AdjQuotesError(
                    f"获取港股复权因子失败（{code_n}）：{e.message}。"
                    "若库内无 stock_adj_factor（source=akshare_sina_hk_qfq），"
                    "可改 factor_source=auto 启用东财回退，或不复权计算"
                ) from e

        # auto：新浪 → 东财
        try:
            return _try_hk_sina(), SOURCE_AKSHARE_SINA_HK_QFQ
        except AdjQuotesError as e:
            errors.append(f"新浪：{e.message}")
            logger.warning("港股新浪复权因子失败，尝试东财：%s", e.message)
        except Exception as e:
            errors.append(f"新浪：{e}")
            logger.warning("港股新浪复权因子异常，尝试东财：%s", e)

        try:
            return _try_hk_em(), SOURCE_AKSHARE_EM_HK_QFQ
        except AdjQuotesError as e:
            errors.append(f"东财：{e.message}")
            raise AdjQuotesError(
                f"获取港股复权因子失败（{code_n}，已尝试新浪与东财）。"
                + "；".join(errors)
                + "。BaoStock 不支持港股；若库内无因子请改用不复权计算"
            ) from e
        except Exception as e:
            errors.append(f"东财：{e}")
            raise AdjQuotesError(
                f"获取港股复权因子失败（{code_n}，已尝试新浪与东财）。"
                + "；".join(errors)
                + "。BaoStock 不支持港股；若库内无因子请改用不复权计算"
            ) from e

    def _try_sina() -> List[Dict[str, Any]]:
        return fetch_sina_qfq_factors(code)

    def _try_bao() -> List[Dict[str, Any]]:
        return fetch_baostock_qfq_factors(code)

    if src == FACTOR_SOURCE_SINA:
        return _try_sina(), SOURCE_AKSHARE_SINA_QFQ
    if src == FACTOR_SOURCE_BAOSTOCK:
        return _try_bao(), SOURCE_BAOSTOCK_QFQ

    # auto：生产默认归一化新浪 → BaoStock 备用（北交所无 BaoStock，不再空跑 sh.92xxxx）
    code_n = normalize_a_share_code(code)
    try:
        return _try_sina(), SOURCE_AKSHARE_SINA_QFQ
    except AdjQuotesError as e:
        errors.append(f"归一化新浪：{e.message}")
        logger.warning("归一化新浪复权因子失败，尝试备用源：%s", e.message)
    except Exception as e:
        errors.append(f"归一化新浪：{e}")
        logger.warning("归一化新浪复权因子异常，尝试备用源：%s", e)

    if is_bse_a_share_code(code_n):
        raise AdjQuotesError(
            "获取复权因子失败（北交所暂无可用第三方备用源；BaoStock 不支持北交所）。"
            + "；".join(errors)
            + "。若库内无 stock_adj_factor，请改用不复权计算"
        )

    try:
        return _try_bao(), SOURCE_BAOSTOCK_QFQ
    except AdjQuotesError as e:
        errors.append(f"BaoStock：{e.message}")
        raise AdjQuotesError(
            "获取复权因子失败（已尝试归一化新浪与 BaoStock）。" + "；".join(errors)
        ) from e
    except Exception as e:
        errors.append(f"BaoStock：{e}")
        raise AdjQuotesError(
            "获取复权因子失败（已尝试归一化新浪与 BaoStock）。" + "；".join(errors)
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
        raw_code = str(r.get("code") or "")
        try:
            code = normalize_adj_code(raw_code) if raw_code else ""
        except AdjQuotesError:
            code = normalize_a_share_code(raw_code)
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
    try:
        code_n = normalize_adj_code(code)
    except AdjQuotesError:
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
    try:
        code_n = normalize_adj_code(code)
    except AdjQuotesError:
        code_n = normalize_a_share_code(code)
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
        {"code": code_n, "source": str(source)},
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


def _candidate_factor_sources(factor_source: str, *, market: str = "CN") -> List[str]:
    """按 factor_source 偏好返回要检索的 stock_adj_factor.source 列表。"""
    src_pref = normalize_factor_source(factor_source)
    if market == "HK":
        if src_pref == FACTOR_SOURCE_SINA:
            return [SOURCE_AKSHARE_SINA_HK_QFQ]
        if src_pref == FACTOR_SOURCE_BAOSTOCK:
            # 调用方应已拦截；此处仍返回空候选以外的可读路径由 fetch 抛错
            return [SOURCE_AKSHARE_SINA_HK_QFQ]
        # auto：新浪优先，东财备用（库内命中任一即可）
        return [SOURCE_AKSHARE_SINA_HK_QFQ, SOURCE_AKSHARE_EM_HK_QFQ]
    if src_pref == FACTOR_SOURCE_AUTO:
        return [SOURCE_AKSHARE_SINA_QFQ, SOURCE_BAOSTOCK_QFQ]
    tag = _factor_source_tag(src_pref, market="CN")
    return [tag] if tag else [SOURCE_AKSHARE_SINA_QFQ]


def ensure_adj_factors(
    db: Session,
    code: str,
    *,
    max_age_days: int = DEFAULT_FACTOR_MAX_AGE_DAYS,
    force_refresh: bool = False,
    factor_source: str = FACTOR_SOURCE_AUTO,
    prefer_db: bool = True,
) -> Dict[str, Any]:
    """确保可用前复权因子。

    默认（prefer_db=True，整策略前复权现算）：
      1) 优先读 stock_adj_factor（有数据即用，不因“不新鲜”打外网）
      2) 库中无该源因子时，才调用第三方接口拉取并 UPSERT
      3) 返回前再从库读出，保证读写同口径

    prefer_db=False：仅当库内因子在 max_age_days 内视为可用，否则走外网刷新。
    force_refresh=True：跳过读库，强制拉取并覆盖写入。

    factor_source: auto | sina | baostock
      - A 股 auto=新浪优先，失败再 BaoStock
      - 港股 auto=新浪（占位→单位因子）→ 东财收盘比；baostock 不可用
    返回：{ factors, factor_fetched, source, adj_factor_asof, factor_source, from_db }
    """
    try:
        code_n = normalize_adj_code(code)
    except AdjQuotesError as e:
        raise AdjQuotesError(
            f"前复权计算仅支持 A 股（6 位）或港股（5 位）代码：{e.message}"
        ) from e

    market = "HK" if is_hk_adj_code(code_n) else "CN"
    src_pref = normalize_factor_source(factor_source)
    candidates = _candidate_factor_sources(src_pref, market=market)
    default_source = (
        SOURCE_AKSHARE_SINA_HK_QFQ if market == "HK" else SOURCE_AKSHARE_SINA_QFQ
    )

    if not force_refresh:
        for cand in candidates:
            factors = load_adj_factors_from_db(db, code_n, source=cand)
            if not factors:
                continue
            if prefer_db:
                # 整策略前复权：有库用库，不调第三方
                asof = factors[-1][0]
                logger.debug(
                    "复权因子优先读库 code=%s source=%s rows=%s asof=%s",
                    code_n,
                    cand,
                    len(factors),
                    _bar_date_str(asof),
                )
                return {
                    "factors": factors,
                    "factor_fetched": False,
                    "source": cand,
                    "adj_factor_asof": _bar_date_str(asof),
                    "factor_source": src_pref,
                    "from_db": True,
                }
            # 非 prefer_db：仅新鲜可用
            latest_td, _, _ = _latest_factor_meta(db, code_n, source=cand)
            if _is_fresh(latest_td, max_age_days):
                asof = factors[-1][0]
                return {
                    "factors": factors,
                    "factor_fetched": False,
                    "source": cand,
                    "adj_factor_asof": _bar_date_str(asof),
                    "factor_source": src_pref,
                    "from_db": True,
                }

    # 库无因子（或 force_refresh / 非 prefer_db 且已过期）才调第三方
    try:
        rows, fetched_source = fetch_qfq_factors(code_n, factor_source=src_pref)
    except AdjQuotesError:
        raise
    except Exception as e:
        raise AdjQuotesError(
            f"获取复权因子失败（{code_n}）：{e}。"
            + (
                "港股请确认 AkShare stock_hk_daily 可用，或改用不复权"
                if market == "HK"
                else "请改用不复权计算"
            )
        ) from e

    written = upsert_adj_factors(db, rows, source=fetched_source)
    logger.info(
        "复权因子外网拉取并写入 stock_adj_factor code=%s source=%s upsert_rows=%s",
        code_n,
        fetched_source,
        written,
    )

    factors = load_adj_factors_from_db(db, code_n, source=fetched_source)
    if not factors:
        raise AdjQuotesError(
            f"复权因子为空，无法按前复权计算（{code_n}，写入后仍读不到；"
            f"期望 source={fetched_source or default_source}）"
        )
    asof = factors[-1][0]
    return {
        "factors": factors,
        "factor_fetched": True,
        "source": fetched_source or default_source,
        "adj_factor_asof": _bar_date_str(asof),
        "factor_source": src_pref,
        "from_db": False,
    }


def apply_qfq_to_bars(
    bars: Sequence[Dict[str, Any]],
    factors: Sequence[Tuple[date, float]],
) -> List[Dict[str, Any]]:
    """将不复权 bars 现算为前复权（OHLC 乘 f_t/f_T；volume/amount 不变）。

    公式：P_qfq = P_raw × f_t / f_T。
    要求 factors 已按内部约定入库（最新≈1、历史通常≤1）。
    A 股新浪因子入库前已取倒数；港股新浪因子原样入库（本身已符合约定）。

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
