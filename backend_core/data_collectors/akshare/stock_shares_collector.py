import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
_current_dir = Path(__file__).resolve().parent
# akshare (parent) -> data_collectors (parent) -> backend_core (parent) -> root
_project_root = str(_current_dir.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple, Sequence
import logging
import time
import random
from datetime import datetime, timedelta

from backend_core.data_collectors.akshare.base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text

# Excel / Tushare daily_basic / 巨潮股本变动：万股 → 库内「股」
_SHARES_PER_WAN_GU = 10000.0

# 列名兼容（表头去首尾空格后匹配）
_EXCEL_CODE_HEADERS = ("证券代码",)
_EXCEL_TOTAL_WAN_HEADERS = ("总股本(万股)", "总股本")
_EXCEL_FLOAT_WAN_HEADERS = ("已流通股份(万股)", "流通股(万股)", "流通股本(万股)")
_EXCEL_CHANGE_DATE_HEADERS = ("变动日期",)
_EXCEL_ANNOUNCE_DATE_HEADERS = ("公告日期",)

_CNINFO_TOTAL_COLS = ("总股本",)
_CNINFO_FLOAT_COLS = ("已流通股份", "流通股", "流通股本")
_CNINFO_DATE_COLS = ("变动日期", "公告日期")


def _ts_code_to_plain(ts_code: str) -> Optional[str]:
    s = str(ts_code or "").strip().upper()
    if not s:
        return None
    if "." in s:
        s = s.split(".", 1)[0]
    if s.isdigit():
        return s.zfill(6)
    return s or None


def _wan_to_shares(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return f * _SHARES_PER_WAN_GU


def parse_cninfo_share_change_latest(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """从巨潮股本变动表取最新一行的总股本/已流通股份（万股→股）。"""
    empty = {"total_shares": None, "free_float_shares": None}
    if df is None or df.empty:
        return empty
    date_col = _pick_column(list(df.columns), _CNINFO_DATE_COLS)
    total_col = _pick_column(list(df.columns), _CNINFO_TOTAL_COLS)
    float_col = _pick_column(list(df.columns), _CNINFO_FLOAT_COLS)
    if not total_col and not float_col:
        return empty
    work = df.copy()
    if date_col:
        work["_sort"] = pd.to_datetime(work[date_col], errors="coerce")
        work = work.sort_values("_sort", ascending=False)
    row = work.iloc[0]
    return {
        "total_shares": _wan_to_shares(row.get(total_col)) if total_col else None,
        "free_float_shares": _wan_to_shares(row.get(float_col)) if float_col else None,
    }


def resolve_shares_source(raw: Optional[str] = None) -> str:
    """auto|tushare|akshare|cninfo|excel。"""
    s = (raw or os.getenv("STOCK_SHARES_SOURCE") or os.getenv("STOCK_SHARES_UPDATE_SOURCE") or "auto").strip().lower()
    if s in ("", "em", "eastmoney"):
        return "akshare"
    if s not in ("auto", "tushare", "akshare", "cninfo", "excel"):
        return "auto"
    return s


def _strip_header(h: Any) -> str:
    if h is None or (isinstance(h, float) and pd.isna(h)):
        return ""
    s = str(h).strip().replace("\u3000", " ")
    return " ".join(s.split())


def _pick_column(columns: List[str], candidates: Tuple[str, ...]) -> Optional[str]:
    norm = {_strip_header(c): c for c in columns}
    for cand in candidates:
        if cand in norm:
            return norm[cand]
    return None


def normalize_excel_stock_code(raw: Any) -> Optional[str]:
    """将 Excel 中的证券代码规范为 6 位字符串（与 stock_basic_info.code 对齐）。"""
    if raw is None:
        return None
    if isinstance(raw, float) and pd.isna(raw):
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        try:
            return str(int(float(raw))).zfill(6)
        except (ValueError, OverflowError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    if s.endswith(".0") and s[:-2].replace(".", "", 1).isdigit():
        try:
            return str(int(float(s))).zfill(6)
        except ValueError:
            pass
    try:
        if all(c in "0123456789." for c in s):
            return str(int(float(s))).zfill(6)
    except ValueError:
        pass
    if s.isdigit():
        return s.zfill(6)
    return s


def _wan_gu_to_shares_cell(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val) * _SHARES_PER_WAN_GU
    except (TypeError, ValueError):
        return None


def prepare_shares_excel_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    将原始 Excel DataFrame 解析为按证券代码去重后的更新行（每股单位：股）。
    同一代码多行时保留「变动日期」最新一行；变动日期缺失时用「公告日期」。
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["code", "total_shares", "free_float_shares", "_sort_ts"])

    cols = list(df.columns)
    code_col = _pick_column(cols, _EXCEL_CODE_HEADERS)
    total_col = _pick_column(cols, _EXCEL_TOTAL_WAN_HEADERS)
    float_col = _pick_column(cols, _EXCEL_FLOAT_WAN_HEADERS)
    change_col = _pick_column(cols, _EXCEL_CHANGE_DATE_HEADERS)
    announce_col = _pick_column(cols, _EXCEL_ANNOUNCE_DATE_HEADERS)

    if not code_col:
        raise ValueError("Excel 中未找到「证券代码」列，请检查表头是否与模板一致")

    out_rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        code = normalize_excel_stock_code(row.get(code_col))
        if not code:
            continue
        total_s = _wan_gu_to_shares_cell(row.get(total_col)) if total_col else None
        free_s = _wan_gu_to_shares_cell(row.get(float_col)) if float_col else None
        if total_s is None and free_s is None:
            continue

        ch_raw = row.get(change_col) if change_col else None
        an_raw = row.get(announce_col) if announce_col else None
        ch_dt = pd.to_datetime(ch_raw, errors="coerce") if change_col else pd.NaT
        an_dt = pd.to_datetime(an_raw, errors="coerce") if announce_col else pd.NaT
        sort_ts = ch_dt if pd.notna(ch_dt) else an_dt
        if pd.isna(sort_ts):
            sort_ts = pd.Timestamp.min

        out_rows.append(
            {
                "code": code,
                "total_shares": total_s,
                "free_float_shares": free_s,
                "_sort_ts": sort_ts,
            }
        )

    if not out_rows:
        return pd.DataFrame(columns=["code", "total_shares", "free_float_shares"])

    mdf = pd.DataFrame(out_rows)
    mdf = mdf.sort_values("_sort_ts", ascending=False).drop_duplicates(subset=["code"], keep="first")
    return mdf.drop(columns=["_sort_ts"])


class StockSharesSyncAbortError(Exception):
    """股本同步失败数超过阈值时触发的致命异常。"""


class StockSharesCollector(AKShareCollector):
    """股本数据采集器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

    def _ensure_stock_basic_shares_columns(self, session) -> None:
        session.execute(text('''
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info'
                                   AND column_name='total_shares') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN total_shares REAL;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info'
                                   AND column_name='free_float_shares') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN free_float_shares REAL;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info'
                                   AND column_name='shares_updated_at') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN shares_updated_at TIMESTAMP;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                                   WHERE table_name='stock_basic_info'
                                   AND column_name='collect_enabled') THEN
                        ALTER TABLE stock_basic_info ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE;
                    END IF;
                END
                $$;
            '''))

    def _get_stocks_to_update(self, session, mode: str = 'incremental', max_stocks: Optional[int] = None):
        """
        获取需要更新股本数据的股票列表

        Args:
            session: 数据库会话
            mode: 'full' 全量更新, 'incremental' 增量更新（只更新未填充或超过7天的）
            max_stocks: 最大更新数量限制

        Returns:
            list: [(code, name), ...]
        """
        if mode == 'full':
            query = "SELECT code, name FROM stock_basic_info WHERE COALESCE(collect_enabled, TRUE) = TRUE ORDER BY code"
        else:
            # 增量：缺更近或超过 7 天；优先刷新「已有流通股本但偏旧」的主板股，
            # 缺数股（北交所等常拉不到）放后面，避免长期挡在队列头导致全市场股本过期。
            query = """
                SELECT code, name FROM stock_basic_info
                WHERE COALESCE(collect_enabled, TRUE) = TRUE
                  AND (
                       shares_updated_at IS NULL
                   OR shares_updated_at < NOW() - INTERVAL '7 days'
                  )
                ORDER BY
                  CASE
                    WHEN free_float_shares IS NOT NULL AND free_float_shares > 0 THEN 0
                    ELSE 1
                  END,
                  shares_updated_at ASC NULLS LAST,
                  code
            """

        if max_stocks:
            query += f" LIMIT {max_stocks}"

        result = session.execute(text(query))
        return result.fetchall()

    def _fetch_from_em(self, code: str) -> Dict[str, Optional[float]]:
        df = self._retry_on_failure(ak.stock_individual_info_em, symbol=code)
        if df is None or df.empty:
            return {"total_shares": None, "free_float_shares": None}

        total_shares = None
        free_float_shares = None
        for _, row in df.iterrows():
            item = str(row.get("item", "")).strip()
            value = row.get("value", None)
            parsed = None
            try:
                if value is not None and str(value).strip() not in ("", "-", "--", "None"):
                    parsed = float(str(value).replace(",", "").strip())
            except (ValueError, TypeError):
                parsed = None
            if parsed is None:
                continue
            if item in ("总股本", "总股本(股)", "总股本（股）") or (
                "总股本" in item and "流通" not in item
            ):
                total_shares = parsed
            elif item in (
                "流通股",
                "流通股(股)",
                "流通股（股）",
                "流通股本",
                "流通股本(股)",
                "流通A股",
                "流通A股(股)",
            ) or ("流通股" in item or "流通A股" in item):
                free_float_shares = parsed

        if (
            total_shares is not None
            and free_float_shares is not None
            and total_shares < 1_000_000
            and free_float_shares < 1_000_000
        ):
            total_shares = total_shares * _SHARES_PER_WAN_GU
            free_float_shares = free_float_shares * _SHARES_PER_WAN_GU

        return {"total_shares": total_shares, "free_float_shares": free_float_shares}

    def _fetch_from_cninfo(self, code: str) -> Dict[str, Optional[float]]:
        df = self._retry_on_failure(ak.stock_share_change_cninfo, symbol=code)
        return parse_cninfo_share_change_latest(df)

    def _fetch_shares_info(
        self,
        code: str,
        *,
        providers: Optional[Sequence[str]] = None,
    ) -> Dict[str, Optional[float]]:
        """
        按 providers 顺序拉取单票股本。默认：东财 → 巨潮。
        """
        order = list(providers) if providers else ["em", "cninfo"]
        last_err: Optional[Exception] = None
        for p in order:
            try:
                if p in ("em", "akshare", "eastmoney"):
                    info = self._fetch_from_em(code)
                elif p in ("cninfo", "巨潮"):
                    info = self._fetch_from_cninfo(code)
                else:
                    continue
                if info.get("total_shares") is not None or info.get("free_float_shares") is not None:
                    return info
            except Exception as e:
                last_err = e
                self.logger.warning("获取股票 %s 股本失败 provider=%s: %s", code, p, e)
        if last_err:
            self.logger.warning("获取股票 %s 股本信息失败: %s", code, last_err)
        return {"total_shares": None, "free_float_shares": None}

    def _resolve_tushare_pro(self):
        token = (
            (os.getenv("TUSHARE_TOKEN") or "").strip()
            or str((__import__("backend_core.config.config", fromlist=["TUSHARE_CONFIG"]).TUSHARE_CONFIG or {}).get("token") or "").strip()
        )
        if not token:
            return None
        try:
            import tushare as ts

            return ts.pro_api(token)
        except Exception as e:
            self.logger.warning("初始化 Tushare 失败: %s", e)
            return None

    def _latest_daily_basic_trade_date(self, pro) -> Optional[str]:
        """推断最近交易日（不发起 API）；实际有无数据由 daily_basic 拉取时校验。"""
        del pro  # 保留签名兼容
        forced = (os.getenv("STOCK_SHARES_TRADE_DATE") or "").strip()
        if forced and len(forced) == 8 and forced.isdigit():
            return forced
        d = datetime.now().date()
        # 盘中也可能尚无当日 daily_basic：默认先用「上一工作日」更稳
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d.strftime("%Y%m%d")

    def collect_shares_from_tushare(
        self,
        *,
        codes: Optional[Sequence[str]] = None,
        trade_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tushare daily_basic 全市场/指定代码批量写入（字段单位：万股）。
        比逐票打东财快两个数量级，适合东财断连时主路径。
        """
        pro = self._resolve_tushare_pro()
        if pro is None:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "error": "tushare_token_missing",
                "source": "tushare",
            }

        td = (trade_date or "").strip() or self._latest_daily_basic_trade_date(pro)
        if not td:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "error": "no_trade_date",
                "source": "tushare",
            }

        self.logger.info("Tushare daily_basic 拉取股本 trade_date=%s ...", td)
        try:
            df = pro.daily_basic(
                trade_date=td,
                fields="ts_code,trade_date,total_share,float_share,free_share",
            )
        except Exception as e:
            # 若首日失败且非强制日期，再试前一工作日一次
            self.logger.error("Tushare daily_basic 失败 trade_date=%s: %s", td, e)
            retry_td = None
            forced = (os.getenv("STOCK_SHARES_TRADE_DATE") or "").strip()
            if not forced:
                try:
                    d0 = datetime.strptime(td, "%Y%m%d").date() - timedelta(days=1)
                    while d0.weekday() >= 5:
                        d0 -= timedelta(days=1)
                    retry_td = d0.strftime("%Y%m%d")
                except Exception:
                    retry_td = None
            if retry_td and retry_td != td and "频率" not in str(e) and "频次" not in str(e):
                self.logger.info("重试 daily_basic trade_date=%s", retry_td)
                try:
                    df = pro.daily_basic(
                        trade_date=retry_td,
                        fields="ts_code,trade_date,total_share,float_share,free_share",
                    )
                    td = retry_td
                except Exception as e2:
                    return {
                        "total": 0,
                        "success": 0,
                        "failed": 0,
                        "skipped": 0,
                        "error": str(e2),
                        "source": "tushare",
                        "trade_date": retry_td,
                    }
            else:
                return {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                    "error": str(e),
                    "source": "tushare",
                    "trade_date": td,
                }
        if df is None or df.empty:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "error": "empty_daily_basic",
                "source": "tushare",
                "trade_date": td,
            }

        want: Optional[set] = None
        if codes:
            want = {str(c).strip().zfill(6) for c in codes if str(c).strip()}

        session = SessionLocal()
        success = 0
        skip = 0
        fail = 0
        updated_at = datetime.now()
        try:
            self._ensure_stock_basic_shares_columns(session)
            session.commit()
            upd = text(
                """
                UPDATE stock_basic_info
                SET total_shares = COALESCE(:total_shares, total_shares),
                    free_float_shares = COALESCE(:free_float_shares, free_float_shares),
                    shares_updated_at = :updated_at
                WHERE code = :code
                """
            )
            n_rows = len(df)
            for i, row in enumerate(df.itertuples(index=False), 1):
                code = _ts_code_to_plain(getattr(row, "ts_code", None))
                if not code:
                    skip += 1
                    continue
                if want is not None and code not in want:
                    continue
                total_s = _wan_to_shares(getattr(row, "total_share", None))
                # CAN SLIM S / 现有口径：流通股本用 float_share（非 free_share 自由流通）
                float_s = _wan_to_shares(getattr(row, "float_share", None))
                if total_s is None and float_s is None:
                    skip += 1
                    continue
                try:
                    r = session.execute(
                        upd,
                        {
                            "code": code,
                            "total_shares": total_s,
                            "free_float_shares": float_s,
                            "updated_at": updated_at,
                        },
                    )
                    if r is not None and r.rowcount and r.rowcount > 0:
                        success += 1
                    else:
                        skip += 1
                except Exception as e:
                    fail += 1
                    self.logger.error("Tushare 写入股本失败 %s: %s", code, e)
                if i % 500 == 0:
                    session.commit()
                    self.logger.info(
                        "Tushare 股本进度 %d/%d success=%d skip=%d fail=%d",
                        i,
                        n_rows,
                        success,
                        skip,
                        fail,
                    )
            session.commit()
            result = {
                "total": n_rows if want is None else len(want),
                "success": success,
                "failed": fail,
                "skipped": skip,
                "source": "tushare",
                "trade_date": td,
            }
            self.logger.info("Tushare 股本同步完成: %s", result)
            return result
        except Exception as e:
            session.rollback()
            self.logger.error("Tushare 股本同步异常: %s", e)
            return {
                "total": 0,
                "success": success,
                "failed": fail,
                "skipped": skip,
                "error": str(e),
                "source": "tushare",
                "trade_date": td,
            }
        finally:
            session.close()

    def collect_shares(
        self,
        mode: str = "incremental",
        max_stocks: Optional[int] = None,
        *,
        source: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        采集并更新股本数据。

        source:
          - auto: 优先 Tushare daily_basic 批量；未覆盖的再逐票 东财→巨潮
          - tushare: 仅 Tushare 批量
          - akshare: 逐票东财→巨潮
          - cninfo: 逐票仅巨潮
        """
        src = resolve_shares_source(source)
        self.logger.info("股本采集 source=%s mode=%s", src, mode)

        if src == "tushare":
            session = SessionLocal()
            try:
                self._ensure_stock_basic_shares_columns(session)
                session.commit()
                stocks = self._get_stocks_to_update(session, mode, max_stocks)
            finally:
                session.close()
            codes = [s[0] for s in stocks] if mode == "incremental" else None
            # full：全表批量；incremental：只刷待更新代码（仍一次 API）
            return self.collect_shares_from_tushare(codes=codes)

        if src == "auto":
            session = SessionLocal()
            try:
                self._ensure_stock_basic_shares_columns(session)
                session.commit()
                stocks = self._get_stocks_to_update(session, mode, max_stocks)
            finally:
                session.close()
            codes = [s[0] for s in stocks]
            ts_res = self.collect_shares_from_tushare(
                codes=None if mode == "full" else codes
            )
            if ts_res.get("success", 0) > 0 and not ts_res.get("error"):
                # 批量已成功：再补漏（库中仍缺流通股的）
                return self._collect_shares_per_stock(
                    mode=mode,
                    max_stocks=max_stocks,
                    providers=["cninfo", "em"],
                    only_missing=True,
                    prior_result=ts_res,
                )
            self.logger.warning(
                "Tushare 股本批量不可用(%s)，回退逐票巨潮→东财",
                ts_res.get("error") or "success=0",
            )
            return self._collect_shares_per_stock(
                mode=mode,
                max_stocks=max_stocks,
                providers=["cninfo", "em"],
            )

        if src == "cninfo":
            providers = ["cninfo"]
        else:
            # akshare：东财常断连，优先巨潮
            providers = ["cninfo", "em"]
        return self._collect_shares_per_stock(
            mode=mode, max_stocks=max_stocks, providers=providers
        )

    def _collect_shares_per_stock(
        self,
        mode: str = "incremental",
        max_stocks: Optional[int] = None,
        *,
        providers: Optional[Sequence[str]] = None,
        only_missing: bool = False,
        prior_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """逐票拉取（东财/巨潮）。"""
        session = SessionLocal()
        success_count = 0
        fail_count = 0
        skip_count = 0
        fail_threshold = int(os.getenv("STOCK_SHARES_FAIL_THRESHOLD") or 50)
        consecutive_fail = 0
        consecutive_fail_abort = int(os.getenv("STOCK_SHARES_CONSEC_FAIL_ABORT") or 15)
        prov = list(providers) if providers else ["em", "cninfo"]

        try:
            self._ensure_stock_basic_shares_columns(session)
            session.commit()

            stocks = self._get_stocks_to_update(session, mode, max_stocks)
            if only_missing:
                # 仅保留库中仍缺流通股的
                miss = session.execute(
                    text(
                        """
                        SELECT code FROM stock_basic_info
                        WHERE COALESCE(collect_enabled, TRUE) = TRUE
                          AND (free_float_shares IS NULL OR free_float_shares <= 0)
                        """
                    )
                ).fetchall()
                miss_set = {str(r[0]).zfill(6) for r in miss}
                stocks = [s for s in stocks if str(s[0]).zfill(6) in miss_set]

            total = len(stocks)
            self.logger.info(
                "股本逐票采集开始 providers=%s only_missing=%s 待更新=%d",
                prov,
                only_missing,
                total,
            )
            if total == 0:
                out = {
                    "total": (prior_result or {}).get("total", 0),
                    "success": (prior_result or {}).get("success", 0),
                    "failed": (prior_result or {}).get("failed", 0),
                    "skipped": (prior_result or {}).get("skipped", 0),
                    "source": (prior_result or {}).get("source", "akshare"),
                    "trade_date": (prior_result or {}).get("trade_date"),
                    "per_stock_filled": 0,
                }
                return out

            for i, stock in enumerate(stocks, 1):
                code = stock[0]
                name = stock[1] or ""

                if "退" in name:
                    skip_count += 1
                    continue

                try:
                    shares_info = self._fetch_shares_info(code, providers=prov)

                    if shares_info["total_shares"] is not None or shares_info["free_float_shares"] is not None:
                        session.execute(
                            text(
                                """
                                UPDATE stock_basic_info
                                SET total_shares = COALESCE(:total_shares, total_shares),
                                    free_float_shares = COALESCE(:free_float_shares, free_float_shares),
                                    shares_updated_at = :updated_at
                                WHERE code = :code
                                """
                            ),
                            {
                                "code": code,
                                "total_shares": shares_info["total_shares"],
                                "free_float_shares": shares_info["free_float_shares"],
                                "updated_at": datetime.now(),
                            },
                        )
                        success_count += 1
                        consecutive_fail = 0
                        self.logger.debug(
                            "更新股票 %s(%s) 股本: 总=%s 流通=%s",
                            code,
                            name,
                            shares_info["total_shares"],
                            shares_info["free_float_shares"],
                        )
                    else:
                        skip_count += 1
                        session.execute(
                            text(
                                """
                                UPDATE stock_basic_info
                                SET shares_updated_at = COALESCE(shares_updated_at, :updated_at)
                                WHERE code = :code
                                  AND free_float_shares IS NULL
                                  AND total_shares IS NULL
                                  AND shares_updated_at IS NULL
                                """
                            ),
                            {"code": code, "updated_at": datetime.now()},
                        )
                        self.logger.debug("股票 %s(%s) 未获取到股本数据，跳过", code, name)

                except Exception as e:
                    fail_count += 1
                    consecutive_fail += 1
                    self.logger.error("处理股票 %s(%s) 股本数据时异常: %s", code, name, e)
                    if fail_count > fail_threshold or consecutive_fail >= consecutive_fail_abort:
                        raise StockSharesSyncAbortError(
                            f"FAIL_THRESHOLD_EXCEEDED: 股本同步失败数 fail={fail_count}/"
                            f"consec={consecutive_fail} 超过阈值，中止任务"
                        )

                if i % 50 == 0:
                    session.commit()
                    self.logger.info(
                        "股本逐票进度: %d/%d，成功: %d，失败: %d，跳过: %d",
                        i,
                        total,
                        success_count,
                        fail_count,
                        skip_count,
                    )

                time.sleep(random.uniform(0.3, 0.8))

            session.commit()

            if prior_result:
                result = {
                    "total": prior_result.get("total", 0) + total,
                    "success": int(prior_result.get("success", 0)) + success_count,
                    "failed": int(prior_result.get("failed", 0)) + fail_count,
                    "skipped": int(prior_result.get("skipped", 0)) + skip_count,
                    "source": f"{prior_result.get('source', 'tushare')}+per_stock",
                    "trade_date": prior_result.get("trade_date"),
                    "per_stock_filled": success_count,
                }
            else:
                result = {
                    "total": total,
                    "success": success_count,
                    "failed": fail_count,
                    "skipped": skip_count,
                    "source": "+".join(prov),
                }
            self.logger.info("股本逐票采集完成: %s", result)
            return result

        except StockSharesSyncAbortError:
            session.rollback()
            raise
        except Exception as e:
            self.logger.error("股本数据采集异常: %s", e)
            session.rollback()
            return {
                "total": 0,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "error": str(e),
            }
        finally:
            session.close()

    def collect_shares_from_excel(
        self,
        excel_path: str,
        sheet_name: Any = 0,
    ) -> Dict[str, Any]:
        """
        从固定列格式的 Excel 批量更新股本（万股 → 股写入 stock_basic_info）。
        列：证券代码、总股本(万股)、已流通股份(万股)；可选 变动日期/公告日期 用于同代码多行取最新。
        """
        path = Path(excel_path).expanduser()
        if not path.is_file():
            self.logger.error("股本 Excel 文件不存在: %s", path)
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "not_in_db": 0,
                "error": f"file_not_found: {path}",
            }

        try:
            df_raw = pd.read_excel(path, sheet_name=sheet_name, dtype=object)
        except Exception as e:
            self.logger.error("读取股本 Excel 失败: %s", e)
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "not_in_db": 0,
                "error": str(e),
            }

        try:
            mdf = prepare_shares_excel_rows(df_raw)
        except ValueError as e:
            self.logger.error("%s", e)
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "not_in_db": 0,
                "error": str(e),
            }

        total = len(mdf)
        if total == 0:
            self.logger.warning("股本 Excel 解析后无有效数据行（需至少证券代码及总股本/已流通股份之一）")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "not_in_db": 0,
            }

        self.logger.info("股本 Excel 解析完成，待写入股票数: %s（来源: %s）", total, path)

        session = SessionLocal()
        success_count = 0
        fail_count = 0
        skip_count = 0
        not_in_db = 0
        updated_at = datetime.now()

        try:
            self._ensure_stock_basic_shares_columns(session)
            session.commit()

            upd = text("""
                UPDATE stock_basic_info
                SET total_shares = COALESCE(:total_shares, total_shares),
                    free_float_shares = COALESCE(:free_float_shares, free_float_shares),
                    shares_updated_at = :updated_at
                WHERE code = :code
            """)

            for i, row in enumerate(mdf.itertuples(index=False), 1):
                code = row.code
                total_shares = getattr(row, "total_shares", None)
                free_float_shares = getattr(row, "free_float_shares", None)
                try:
                    r = session.execute(
                        upd,
                        {
                            "code": code,
                            "total_shares": total_shares,
                            "free_float_shares": free_float_shares,
                            "updated_at": updated_at,
                        },
                    )
                    n = r.rowcount if r is not None else 0
                    if n and n > 0:
                        success_count += 1
                    else:
                        not_in_db += 1
                except Exception as e:
                    fail_count += 1
                    self.logger.error("写入股本失败 code=%s: %s", code, e)

                if i % 200 == 0:
                    session.commit()
                    self.logger.info(
                        "股本 Excel 导入进度: %s/%s，成功 %s，失败 %s，库中无此代码 %s",
                        i,
                        total,
                        success_count,
                        fail_count,
                        not_in_db,
                    )

            session.commit()
            result = {
                "total": total,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "not_in_db": not_in_db,
            }
            self.logger.info("股本 Excel 导入完成: %s", result)
            return result

        except Exception as e:
            self.logger.error("股本 Excel 导入异常: %s", e)
            session.rollback()
            return {
                "total": total,
                "success": success_count,
                "failed": fail_count,
                "skipped": skip_count,
                "not_in_db": not_in_db,
                "error": str(e),
            }
        finally:
            session.close()

    def run(
        self,
        mode: str = "incremental",
        max_stocks: Optional[int] = None,
        *,
        source: Optional[str] = None,
    ):
        """
        运行采集器

        Args:
            mode: 'full' 全量更新, 'incremental' 增量更新
            max_stocks: 最大更新数量限制
            source: auto|tushare|akshare|cninfo（默认读环境变量）
        """
        src = resolve_shares_source(source)
        self.logger.info(f"股本数据采集器启动，模式: {mode}，source: {src}")
        result = self.collect_shares(mode=mode, max_stocks=max_stocks, source=src)
        self.logger.info(f"股本数据采集器结束，结果: {result}")
        return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="股本数据采集器")
    parser.add_argument(
        "--source",
        choices=["auto", "tushare", "akshare", "cninfo", "excel"],
        default=None,
        help="数据来源：auto(默认,Tushare优先)/tushare/akshare/cninfo/excel",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
        help="模式：full=全量, incremental=增量(默认)",
    )
    parser.add_argument("--max-stocks", type=int, default=None, help="逐票模式最大更新数量")
    parser.add_argument(
        "--excel-path",
        type=str,
        default=None,
        help="excel 模式：xlsx/xls 路径（亦可设环境变量 STOCK_SHARES_EXCEL_PATH）",
    )
    parser.add_argument(
        "--excel-sheet",
        type=str,
        default="",
        help="工作表序号（如 0）或名称；不设则用环境变量 STOCK_SHARES_EXCEL_SHEET，否则首张表",
    )
    args = parser.parse_args()

    collector = StockSharesCollector()
    src = resolve_shares_source(args.source)
    if src == "excel":
        path = (args.excel_path or os.getenv("STOCK_SHARES_EXCEL_PATH") or "").strip()
        if not path:
            parser.error("--source=excel 需要 --excel-path 或环境变量 STOCK_SHARES_EXCEL_PATH")
        sheet_kw: Any = 0
        sheet_raw = (args.excel_sheet or os.getenv("STOCK_SHARES_EXCEL_SHEET") or "").strip()
        if sheet_raw:
            try:
                sheet_kw = int(sheet_raw)
            except ValueError:
                sheet_kw = sheet_raw
        collector.collect_shares_from_excel(path, sheet_name=sheet_kw)
    else:
        collector.run(mode=args.mode, max_stocks=args.max_stocks, source=src)


