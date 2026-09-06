"""Tushare 财务指标采集 → stock_fina_indicator（CAN SLIM C/A）。"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
import tushare as ts
from sqlalchemy import text

from backend_core.config.config import DATA_COLLECTORS, TUSHARE_CONFIG
from backend_core.data_collectors.tushare.base import TushareCollector
from backend_core.database.db import SessionLocal

logger = logging.getLogger(__name__)

FINA_FIELDS = (
    "ts_code,ann_date,end_date,eps,dt_eps,q_eps,q_dt_eps,"
    "basic_eps_yoy,dt_eps_yoy,q_eps_yoy,q_profit_yoy,q_netprofit_yoy,q_sales_yoy,"
    "roe,roe_waa"
)

UPSERT_SQL = text(
    """
    INSERT INTO stock_fina_indicator (
        code, end_date, ann_date, ts_code,
        eps, q_eps, basic_eps_yoy, dt_eps_yoy,
        q_eps_yoy, q_profit_yoy, q_netprofit_yoy, q_sales_yoy,
        roe, roe_waa, update_time
    ) VALUES (
        :code, :end_date, :ann_date, :ts_code,
        :eps, :q_eps, :basic_eps_yoy, :dt_eps_yoy,
        :q_eps_yoy, :q_profit_yoy, :q_netprofit_yoy, :q_sales_yoy,
        :roe, :roe_waa, CURRENT_TIMESTAMP
    )
    ON CONFLICT (code, end_date) DO UPDATE SET
        ann_date = EXCLUDED.ann_date,
        ts_code = EXCLUDED.ts_code,
        eps = EXCLUDED.eps,
        q_eps = EXCLUDED.q_eps,
        basic_eps_yoy = EXCLUDED.basic_eps_yoy,
        dt_eps_yoy = EXCLUDED.dt_eps_yoy,
        q_eps_yoy = COALESCE(EXCLUDED.q_eps_yoy, stock_fina_indicator.q_eps_yoy),
        q_profit_yoy = COALESCE(EXCLUDED.q_profit_yoy, stock_fina_indicator.q_profit_yoy),
        q_netprofit_yoy = COALESCE(EXCLUDED.q_netprofit_yoy, stock_fina_indicator.q_netprofit_yoy),
        q_sales_yoy = COALESCE(EXCLUDED.q_sales_yoy, stock_fina_indicator.q_sales_yoy),
        roe = COALESCE(EXCLUDED.roe, stock_fina_indicator.roe),
        roe_waa = COALESCE(EXCLUDED.roe_waa, stock_fina_indicator.roe_waa),
        update_time = CURRENT_TIMESTAMP
    """
)


def _code_to_ts_code(code: str) -> str:
    c = str(code).strip().zfill(6)
    if c.startswith("6"):
        return f"{c}.SH"
    if c.startswith(("4", "8")):
        return f"{c}.BJ"
    return f"{c}.SZ"


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _row_to_params(row: pd.Series) -> Optional[Dict[str, Any]]:
    ts_code = str(row.get("ts_code") or "").strip()
    end_date = str(row.get("end_date") or "").strip()[:8]
    if not ts_code or not end_date:
        return None
    code = ts_code.split(".")[0]
    ann = row.get("ann_date")
    ann_date = str(ann).strip()[:8] if ann is not None and not (isinstance(ann, float) and pd.isna(ann)) else None
    return {
        "code": code,
        "end_date": end_date,
        "ann_date": ann_date,
        "ts_code": ts_code,
        "eps": _safe_float(row.get("eps")),
        "q_eps": _safe_float(row.get("q_eps") if row.get("q_eps") is not None else row.get("q_dt_eps")),
        "basic_eps_yoy": _safe_float(row.get("basic_eps_yoy")),
        "dt_eps_yoy": _safe_float(row.get("dt_eps_yoy")),
        "q_eps_yoy": _safe_float(row.get("q_eps_yoy")),
        "q_profit_yoy": _safe_float(row.get("q_profit_yoy")),
        "q_netprofit_yoy": _safe_float(row.get("q_netprofit_yoy")),
        "q_sales_yoy": _safe_float(row.get("q_sales_yoy")),
        "roe": _safe_float(row.get("roe")),
        "roe_waa": _safe_float(row.get("roe_waa")),
    }


def _is_tushare_access_denied(exc: BaseException) -> bool:
    """识别 Tushare 积分/权限类错误（应立即放弃该源）。"""
    msg = str(exc) if exc is not None else ""
    needles = (
        "没有接口",
        "访问权限",
        "权限的具体详情",
        "积分不足",
        "没有访问权限",
        "抱歉，您没有",
        "code=2002",  # 常见权限/积分错误码文案变体
        "权限不足",
    )
    return any(n in msg for n in needles)


class FinaIndicatorCollector(TushareCollector):
    """按股票增量拉取 fina_indicator 并 UPSERT。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        token = (self.config or {}).get("token") or TUSHARE_CONFIG.get("token") or ""
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api()
        self.sleep_sec = float((self.config or {}).get("fina_sleep_sec", 0.35))

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

    def _upsert_df(self, session, df: pd.DataFrame) -> int:
        if df is None or df.empty:
            return 0
        n = 0
        for _, row in df.iterrows():
            params = _row_to_params(row)
            if not params:
                continue
            session.execute(UPSERT_SQL, params)
            n += 1
        return n

    def collect_one(
        self,
        code: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> int:
        ts_code = _code_to_ts_code(code)
        kwargs: Dict[str, Any] = {
            "ts_code": ts_code,
            "start_date": start_date,
            "fields": FINA_FIELDS,
        }
        if end_date:
            kwargs["end_date"] = end_date
        df = self.pro.fina_indicator(**kwargs)
        if df is None or df.empty:
            return 0
        session = SessionLocal()
        try:
            n = self._upsert_df(session, df)
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
        """全市场（或指定代码）增量采集近 years_back 年财务指标。"""
        self.ensure_table()
        start_date = (datetime.now() - timedelta(days=int(years_back) * 365)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        session = SessionLocal()
        try:
            code_list = self._list_codes(session, codes)
        finally:
            session.close()
        if max_stocks is not None and max_stocks > 0:
            code_list = code_list[: int(max_stocks)]

        ok = 0
        fail = 0
        rows = 0
        aborted_permission = False
        abort_error: Optional[str] = None
        for i, code in enumerate(code_list):
            try:
                n = self.collect_one(code, start_date=start_date, end_date=end_date)
                rows += n
                if n > 0:
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                if _is_tushare_access_denied(e):
                    aborted_permission = True
                    abort_error = str(e)
                    self.logger.error(
                        "Tushare fina_indicator 无访问权限，立即中止（已试 %d 只）: %s",
                        i + 1,
                        e,
                    )
                    break
                self.logger.warning("fina_indicator 采集失败 %s: %s", code, e)
            if self.sleep_sec > 0 and i + 1 < len(code_list) and not aborted_permission:
                time.sleep(self.sleep_sec)
            if (i + 1) % 200 == 0:
                self.logger.info(
                    "fina_indicator 进度 %d/%d ok=%d fail=%d rows=%d",
                    i + 1,
                    len(code_list),
                    ok,
                    fail,
                    rows,
                )

        result = {
            "success": (not aborted_permission) and (ok > 0),
            "source": "tushare",
            "stocks": len(code_list),
            "ok": ok,
            "fail": fail,
            "rows": rows,
            "start_date": start_date,
            "end_date": end_date,
            "aborted_permission": aborted_permission,
        }
        if abort_error:
            result["error"] = abort_error
        self.logger.info("fina_indicator 采集完成: %s", result)
        return result


def run_fina_indicator_collect(**kwargs: Any) -> Dict[str, Any]:
    cfg = dict(DATA_COLLECTORS.get("tushare", {}) or {})
    if TUSHARE_CONFIG.get("token"):
        cfg.setdefault("token", TUSHARE_CONFIG["token"])
    return FinaIndicatorCollector(cfg).collect(**kwargs)


def _tushare_token_available() -> bool:
    import os

    token = (
        (TUSHARE_CONFIG.get("token") or "").strip()
        or (os.getenv("TUSHARE_TOKEN") or "").strip()
        or str((DATA_COLLECTORS.get("tushare") or {}).get("token") or "").strip()
    )
    return bool(token)


def run_fina_indicator_collect_auto(**kwargs: Any) -> Dict[str, Any]:
    """按 CANSLIM_FINA_SOURCE 选择数据源：auto | tushare | akshare。

    auto：有 token 时先试 Tushare；无权限/失败则立即改用 AkShare（不再扫全市场）。
    """
    import os

    source = (os.getenv("CANSLIM_FINA_SOURCE") or "auto").strip().lower()
    if source == "akshare":
        from backend_core.data_collectors.akshare.fina_indicator import (
            run_akshare_fina_indicator_collect,
        )

        return run_akshare_fina_indicator_collect(**kwargs)

    if source == "tushare":
        return run_fina_indicator_collect(**kwargs)

    # auto
    if not _tushare_token_available():
        logger.warning("TUSHARE_TOKEN 未配置，财务采集改用 AkShare")
        from backend_core.data_collectors.akshare.fina_indicator import (
            run_akshare_fina_indicator_collect,
        )

        return run_akshare_fina_indicator_collect(**kwargs)

    try:
        result = run_fina_indicator_collect(**kwargs)
        if isinstance(result, dict) and result.get("success"):
            result = dict(result)
            result.setdefault("source", "tushare")
            return result
        reason = (result or {}).get("error") or (result or {}).get("aborted_permission")
        logger.warning(
            "Tushare fina 未成功（reason=%s, result=%s），立即回退 AkShare",
            reason,
            {k: result.get(k) for k in ("ok", "fail", "rows", "aborted_permission") if isinstance(result, dict)},
        )
    except Exception as e:
        logger.warning("Tushare fina 异常，回退 AkShare: %s", e)

    from backend_core.data_collectors.akshare.fina_indicator import (
        run_akshare_fina_indicator_collect,
    )

    logger.warning("开始 AkShare 财务采集（按票拉取，请关注进度日志；可用 CANSLIM_FINA_MAX_STOCKS 限流试跑）")
    ak_result = run_akshare_fina_indicator_collect(**kwargs)
    if isinstance(ak_result, dict):
        ak_result = dict(ak_result)
        ak_result["fallback_from"] = "tushare"
    return ak_result
