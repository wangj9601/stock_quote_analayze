"""AkShare 财务指标采集 → stock_fina_indicator（CAN SLIM C/A 兜底）。

优先 ``stock_financial_abstract``（单次请求），不足再补同花顺「按报告期」。
关键业务日志一律用本模块 logger（与工作流控制台同源），带超时与进度/ETA。
"""

from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable, Dict, List, Optional, Sequence

import akshare as ak
import pandas as pd
from sqlalchemy import text

from backend_core.config.config import DATA_COLLECTORS
from backend_core.data_collectors.akshare.base import AKShareCollector
from backend_core.data_collectors.tushare.fina_indicator import UPSERT_SQL, _code_to_ts_code
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

_COL_PERIOD = ("报告期", "报告日期", "日期")
_COL_EPS = ("基本每股收益", "每股收益", "每股收益(元)", "EPS")
# Eastmoney abstract 实际名为「净资产收益率(ROE)」；勿只写短名精确匹配
_COL_ROE = (
    "净资产收益率(ROE)",
    "净资产收益率_平均",
    "净资产收益率-加权",
    "净资产收益率(加权)",
    "摊薄净资产收益率",
    "净资产收益率",
    "ROE",
)
_COL_PROFIT = ("净利润", "归母净利润", "净利润(元)")
_COL_REVENUE = ("营业总收入", "营业收入", "营业总收入(元)")

_DEFAULT_CALL_TIMEOUT = 25.0
_DEFAULT_SLEEP = 0.25
_DEFAULT_LOG_EVERY = 10


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _call_with_timeout(fn: Callable[..., Any], timeout_sec: float, *args: Any, **kwargs: Any) -> Any:
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn, *args, **kwargs)
        return fut.result(timeout=timeout_sec)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, str):
        s = val.strip().replace(",", "").replace("%", "")
        if not s or s in ("--", "-", "None", "nan"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def normalize_end_date(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    try:
        if pd.isna(raw):
            return None
    except (TypeError, ValueError):
        pass
    s = str(raw).strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 8:
        return digits[:8]
    m = re.match(r"(\d{4})", s)
    if not m:
        return None
    year = m.group(1)
    if "一季" in s or "Q1" in s.upper() or s.endswith("-03"):
        return f"{year}0331"
    if "中报" in s or "二季" in s or "Q2" in s.upper() or s.endswith("-06"):
        return f"{year}0630"
    if "三季" in s or "Q3" in s.upper() or s.endswith("-09"):
        return f"{year}0930"
    if "年报" in s or "四季" in s or "Q4" in s.upper() or "年度" in s or s.endswith("-12"):
        return f"{year}1231"
    return None


def _pick_col(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    colset = {str(c).strip(): c for c in columns}
    for cand in candidates:
        if cand in colset:
            return colset[cand]
    for cand in candidates:
        for c in columns:
            cs = str(c).strip()
            if cand and cand in cs:
                return c
    return None


def _match_indicator_rows(df: pd.DataFrame, row_name_col: str, candidates: Sequence[str]) -> pd.DataFrame:
    """按候选名匹配宽表指标行：先精确，再包含；多行时保留全部供取值合并。"""
    series = df[row_name_col].astype(str).str.strip()
    for cand in candidates:
        exact = df.loc[series == cand]
        if not exact.empty:
            return exact
    for cand in candidates:
        if not cand:
            continue
        # 避免「净资产」误匹配「每股净资产」：要求候选为完整指标子串
        fuzzy = df.loc[series.str.contains(cand, regex=False, na=False)]
        if not fuzzy.empty:
            # 优先更短的指标名（更接近主指标）
            lengths = fuzzy[row_name_col].astype(str).str.len()
            return fuzzy.loc[[lengths.idxmin()]]
    return df.iloc[0:0]


def _yoy_pct(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    if curr is None or prev is None or prev == 0:
        return None
    try:
        return (float(curr) / float(prev) - 1.0) * 100.0
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _same_quarter_prev_year(end_date: str) -> str:
    return f"{int(end_date[:4]) - 1}{end_date[4:8]}"


def records_from_ths_df(
    df: pd.DataFrame,
    *,
    code: str,
    kind: str,
) -> Dict[str, Dict[str, Any]]:
    if df is None or df.empty:
        return {}
    period_col = _pick_col(list(df.columns), _COL_PERIOD)
    if not period_col:
        return {}
    eps_col = _pick_col(list(df.columns), _COL_EPS)
    roe_col = _pick_col(list(df.columns), _COL_ROE)
    profit_col = _pick_col(list(df.columns), _COL_PROFIT)
    revenue_col = _pick_col(list(df.columns), _COL_REVENUE)

    by_end: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        end_date = normalize_end_date(row.get(period_col))
        if not end_date:
            continue
        eps = _safe_float(row.get(eps_col)) if eps_col else None
        roe = _safe_float(row.get(roe_col)) if roe_col else None
        profit = _safe_float(row.get(profit_col)) if profit_col else None
        revenue = _safe_float(row.get(revenue_col)) if revenue_col else None
        rec = by_end.setdefault(
            end_date,
            {
                "code": code,
                "end_date": end_date,
                "ann_date": None,
                "ts_code": _code_to_ts_code(code),
                "eps": None,
                "q_eps": None,
                "basic_eps_yoy": None,
                "dt_eps_yoy": None,
                "q_eps_yoy": None,
                "q_profit_yoy": None,
                "q_netprofit_yoy": None,
                "q_sales_yoy": None,
                "roe": None,
                "roe_waa": None,
                "_profit": None,
                "_revenue": None,
            },
        )
        if kind in ("quarter", "report"):
            if eps is not None:
                rec["q_eps"] = eps
                if end_date.endswith("1231") or kind == "report":
                    if rec.get("eps") is None:
                        rec["eps"] = eps
            if profit is not None:
                rec["_profit"] = profit
            if revenue is not None:
                rec["_revenue"] = revenue
        if kind in ("annual", "report"):
            if eps is not None:
                rec["eps"] = eps
            if roe is not None:
                rec["roe"] = roe
                rec["roe_waa"] = roe
            if profit is not None and rec.get("_profit") is None:
                rec["_profit"] = profit
            if revenue is not None and rec.get("_revenue") is None:
                rec["_revenue"] = revenue
        if roe is not None and rec.get("roe") is None:
            rec["roe"] = roe
            rec["roe_waa"] = roe
    return by_end


def attach_yoy(by_end: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    ends = sorted(by_end.keys())
    for end in ends:
        rec = by_end[end]
        prev = by_end.get(_same_quarter_prev_year(end))
        if prev:
            q_eps_yoy = _yoy_pct(rec.get("q_eps") or rec.get("eps"), prev.get("q_eps") or prev.get("eps"))
            if q_eps_yoy is not None:
                rec["q_eps_yoy"] = q_eps_yoy
            q_profit_yoy = _yoy_pct(rec.get("_profit"), prev.get("_profit"))
            if q_profit_yoy is not None:
                rec["q_profit_yoy"] = q_profit_yoy
                rec["q_netprofit_yoy"] = q_profit_yoy
            q_sales_yoy = _yoy_pct(rec.get("_revenue"), prev.get("_revenue"))
            if q_sales_yoy is not None:
                rec["q_sales_yoy"] = q_sales_yoy
        if end.endswith("1231"):
            prev_ann = by_end.get(f"{int(end[:4]) - 1}1231")
            if prev_ann:
                basic = _yoy_pct(rec.get("eps"), prev_ann.get("eps"))
                if basic is not None:
                    rec["basic_eps_yoy"] = basic
    out = []
    for end in ends:
        rec = dict(by_end[end])
        rec.pop("_profit", None)
        rec.pop("_revenue", None)
        out.append(rec)
    return out


def merge_period_maps(*maps: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for m in maps:
        for end, rec in (m or {}).items():
            if end not in merged:
                merged[end] = dict(rec)
                continue
            base = merged[end]
            for k, v in rec.items():
                if v is None:
                    continue
                if k.startswith("_") or base.get(k) is None:
                    base[k] = v
    return merged


def _has_usable_yoy(by_end: Dict[str, Dict[str, Any]]) -> bool:
    rows = attach_yoy({k: dict(v) for k, v in by_end.items()})
    for r in rows:
        if r.get("q_eps_yoy") is not None or r.get("q_profit_yoy") is not None or r.get("basic_eps_yoy") is not None:
            return True
    return len(by_end) >= 2


class AkshareFinaIndicatorCollector(AKShareCollector):
    """按股票拉取财务摘要并写入 stock_fina_indicator。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        cfg = self.config or {}
        self.sleep_sec = float(cfg.get("fina_sleep_sec", _env_float("CANSLIM_AK_FINA_SLEEP", _DEFAULT_SLEEP)))
        self.call_timeout = float(
            cfg.get("fina_timeout_sec", _env_float("CANSLIM_AK_FINA_TIMEOUT", _DEFAULT_CALL_TIMEOUT))
        )
        self.log_every = max(
            1, int(cfg.get("fina_log_every", _env_int("CANSLIM_AK_FINA_LOG_EVERY", _DEFAULT_LOG_EVERY)))
        )

    def ensure_table(self) -> None:
        session = SessionLocal()
        try:
            session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS stock_fina_indicator (
                        code TEXT NOT NULL,
                        end_date VARCHAR(8) NOT NULL,
                        ann_date VARCHAR(8),
                        ts_code VARCHAR(16),
                        eps DOUBLE PRECISION,
                        q_eps DOUBLE PRECISION,
                        basic_eps_yoy DOUBLE PRECISION,
                        dt_eps_yoy DOUBLE PRECISION,
                        q_eps_yoy DOUBLE PRECISION,
                        q_profit_yoy DOUBLE PRECISION,
                        q_netprofit_yoy DOUBLE PRECISION,
                        q_sales_yoy DOUBLE PRECISION,
                        roe DOUBLE PRECISION,
                        roe_waa DOUBLE PRECISION,
                        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (code, end_date)
                    )
                    """
                )
            )
            session.commit()
        finally:
            session.close()

    def _list_codes(self, session, codes: Optional[Sequence[str]] = None) -> List[str]:
        if codes:
            return [str(c).strip().zfill(6) for c in codes if str(c).strip()]
        rows = session.execute(
            text(
                """
                SELECT code FROM stock_basic_info
                WHERE COALESCE(collect_enabled, TRUE) = TRUE
                ORDER BY code
                """
            )
        ).fetchall()
        return [str(r[0]).zfill(6) for r in rows if r and r[0]]

    def _fetch_with_timeout(self, label: str, fn: Callable[[], Any]) -> Any:
        t0 = time.time()
        try:
            out = _call_with_timeout(fn, self.call_timeout)
            logger.info("AkShare 请求完成 %s 用时=%.1fs", label, time.time() - t0)
            return out
        except FuturesTimeout:
            logger.warning("AkShare 请求超时 %s (限时%.0fs)", label, self.call_timeout)
            return None
        except Exception as e:
            logger.warning("AkShare 请求失败 %s: %s", label, e)
            return None

    def _from_abstract_wide(self, df: pd.DataFrame, code: str) -> Dict[str, Dict[str, Any]]:
        if df is None or df.empty:
            return {}
        row_name_col = None
        for possible in ("指标", "选项", "名称"):
            if possible in df.columns:
                row_name_col = possible
                break
        if row_name_col is None:
            return {}
        period_cols = [c for c in df.columns if str(c).isdigit() or str(c).startswith("20")]
        if not period_cols:
            return {}

        def _row_vals(names: Sequence[str]) -> Dict[str, Optional[float]]:
            matched = _match_indicator_rows(df, row_name_col, names)
            if matched.empty:
                return {}
            out: Dict[str, Optional[float]] = {}
            for pc in period_cols:
                end = normalize_end_date(pc)
                if not end:
                    continue
                val = None
                for i in range(len(matched)):
                    val = _safe_float(matched.iloc[i][pc])
                    if val is not None:
                        break
                out[end] = val
            return out

        eps_map = _row_vals(_COL_EPS)
        roe_map = _row_vals(_COL_ROE)
        profit_map = _row_vals(_COL_PROFIT)
        revenue_map = _row_vals(_COL_REVENUE)
        ends = set(eps_map) | set(roe_map) | set(profit_map) | set(revenue_map)
        by_end: Dict[str, Dict[str, Any]] = {}
        for end in ends:
            by_end[end] = {
                "code": code,
                "end_date": end,
                "ann_date": None,
                "ts_code": _code_to_ts_code(code),
                "eps": eps_map.get(end),
                "q_eps": eps_map.get(end),
                "basic_eps_yoy": None,
                "dt_eps_yoy": None,
                "q_eps_yoy": None,
                "q_profit_yoy": None,
                "q_netprofit_yoy": None,
                "q_sales_yoy": None,
                "roe": roe_map.get(end),
                "roe_waa": roe_map.get(end),
                "_profit": profit_map.get(end),
                "_revenue": revenue_map.get(end),
            }
        return by_end

    def build_rows_for_code(self, code: str) -> List[Dict[str, Any]]:
        maps: List[Dict[str, Dict[str, Any]]] = []
        abs_df = self._fetch_with_timeout(
            f"abstract:{code}",
            lambda: ak.stock_financial_abstract(symbol=code),
        )
        if abs_df is not None and not getattr(abs_df, "empty", True):
            wide = self._from_abstract_wide(abs_df, code)
            if wide:
                maps.append(wide)

        merged = merge_period_maps(*maps) if maps else {}
        if not _has_usable_yoy(merged):
            logger.info("AkShare %s abstract 不足，补拉同花顺按报告期", code)
            ths_df = self._fetch_with_timeout(
                f"ths-report:{code}",
                lambda: ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期"),
            )
            if ths_df is not None and not getattr(ths_df, "empty", True):
                maps.append(records_from_ths_df(ths_df, code=code, kind="report"))
                merged = merge_period_maps(*maps)

        if not merged:
            return []
        return attach_yoy(merged)

    def collect_one(self, code: str) -> int:
        rows = self.build_rows_for_code(code)
        if not rows:
            return 0
        session = SessionLocal()
        n = 0
        try:
            for rec in rows:
                session.execute(
                    UPSERT_SQL,
                    {
                        "code": rec["code"],
                        "end_date": rec["end_date"],
                        "ann_date": rec.get("ann_date"),
                        "ts_code": rec.get("ts_code") or _code_to_ts_code(code),
                        "eps": rec.get("eps"),
                        "q_eps": rec.get("q_eps"),
                        "basic_eps_yoy": rec.get("basic_eps_yoy"),
                        "dt_eps_yoy": rec.get("dt_eps_yoy"),
                        "q_eps_yoy": rec.get("q_eps_yoy"),
                        "q_profit_yoy": rec.get("q_profit_yoy"),
                        "q_netprofit_yoy": rec.get("q_netprofit_yoy"),
                        "q_sales_yoy": rec.get("q_sales_yoy"),
                        "roe": rec.get("roe"),
                        "roe_waa": rec.get("roe_waa"),
                    },
                )
                n += 1
            session.commit()
            return n
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def collect(
        self,
        *,
        years_back: int = 4,
        codes: Optional[Sequence[str]] = None,
        max_stocks: Optional[int] = None,
    ) -> Dict[str, Any]:
        del years_back
        logger.info(
            "AkShare fina 准备中：建表/列股票池 timeout=%.0fs sleep=%.2fs log_every=%d",
            self.call_timeout,
            self.sleep_sec,
            self.log_every,
        )
        self.ensure_table()
        session = SessionLocal()
        try:
            code_list = self._list_codes(session, codes)
        finally:
            session.close()
        if max_stocks is not None and max_stocks > 0:
            code_list = code_list[: int(max_stocks)]

        total = len(code_list)
        if total == 0:
            logger.warning("AkShare fina：股票池为空，结束")
            return {"success": False, "source": "akshare", "stocks": 0, "ok": 0, "fail": 0, "rows": 0}

        logger.info(
            "AkShare fina 开始采集：共 %d 只股票（每票约 1～2 次外网请求；前5只逐条打日志，之后每 %d 只一次）",
            total,
            self.log_every,
        )

        ok = 0
        fail = 0
        rows = 0
        t0 = time.time()
        for i, code in enumerate(code_list):
            done = i + 1
            if done <= 5 or done == 1:
                logger.info("AkShare fina 正在处理 [%d/%d] code=%s ...", done, total, code)
            try:
                n = self.collect_one(code)
                rows += n
                if n > 0:
                    ok += 1
                    if done <= 5:
                        logger.info("AkShare fina [%d/%d] code=%s 成功写入 %d 行报告期", done, total, code, n)
                else:
                    fail += 1
                    if done <= 5:
                        logger.warning("AkShare fina [%d/%d] code=%s 无有效财务行", done, total, code)
            except Exception as e:
                fail += 1
                logger.warning("AkShare fina [%d/%d] code=%s 异常: %s", done, total, code, e)

            if done <= 5 or done % self.log_every == 0 or done == total:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                logger.info(
                    "AkShare fina 进度 %d/%d ok=%d fail=%d rows=%d 用时=%.0fs ETA≈%.0fs 最近=%s",
                    done,
                    total,
                    ok,
                    fail,
                    rows,
                    elapsed,
                    eta,
                    code,
                )

            if self.sleep_sec > 0 and done < total:
                time.sleep(self.sleep_sec)

        result = {
            "success": ok > 0,
            "source": "akshare",
            "stocks": total,
            "ok": ok,
            "fail": fail,
            "rows": rows,
            "elapsed_sec": round(time.time() - t0, 1),
        }
        logger.info("AkShare fina 采集完成: %s", result)
        return result


def run_akshare_fina_indicator_collect(**kwargs: Any) -> Dict[str, Any]:
    logger.info(
        "run_akshare_fina_indicator_collect 启动 max_stocks=%s years_back=%s",
        kwargs.get("max_stocks"),
        kwargs.get("years_back"),
    )
    cfg = dict(DATA_COLLECTORS.get("akshare", {}) or {})
    return AkshareFinaIndicatorCollector(cfg).collect(**kwargs)
