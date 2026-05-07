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
from typing import Optional, Dict, Any, List, Tuple
import logging
import time
import random
from datetime import datetime

from backend_core.data_collectors.akshare.base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text

# Excel 模板列为「万股」，库内与 akshare 一致为「股」
_SHARES_PER_WAN_GU = 10000.0

# 列名兼容（表头去首尾空格后匹配）
_EXCEL_CODE_HEADERS = ("证券代码",)
_EXCEL_TOTAL_WAN_HEADERS = ("总股本(万股)", "总股本")
_EXCEL_FLOAT_WAN_HEADERS = ("已流通股份(万股)", "流通股(万股)", "流通股本(万股)")
_EXCEL_CHANGE_DATE_HEADERS = ("变动日期",)
_EXCEL_ANNOUNCE_DATE_HEADERS = ("公告日期",)


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
            # 增量模式：只更新 shares_updated_at 为 NULL 或超过 7 天的
            query = """
                SELECT code, name FROM stock_basic_info
                WHERE COALESCE(collect_enabled, TRUE) = TRUE
                  AND (
                       shares_updated_at IS NULL
                   OR shares_updated_at < NOW() - INTERVAL '7 days'
                  )
                ORDER BY shares_updated_at ASC NULLS FIRST, code
            """

        if max_stocks:
            query += f" LIMIT {max_stocks}"

        result = session.execute(text(query))
        return result.fetchall()

    def _fetch_shares_info(self, code: str) -> Dict[str, Optional[float]]:
        """
        从 akshare 获取单只股票的股本信息

        Args:
            code: 股票代码

        Returns:
            dict: {'total_shares': float, 'free_float_shares': float}
        """
        try:
            df = self._retry_on_failure(ak.stock_individual_info_em, symbol=code)

            if df is None or df.empty:
                return {'total_shares': None, 'free_float_shares': None}

            total_shares = None
            free_float_shares = None

            for _, row in df.iterrows():
                item = str(row.get('item', '')).strip()
                value = row.get('value', None)

                if item in ('总股本', '总股本(股)'):
                    try:
                        total_shares = float(value)
                    except (ValueError, TypeError):
                        pass
                elif item in ('流通股', '流通股(股)', '流通股本', '流通股本(股)'):
                    try:
                        free_float_shares = float(value)
                    except (ValueError, TypeError):
                        pass

            return {
                'total_shares': total_shares,
                'free_float_shares': free_float_shares
            }

        except Exception as e:
            self.logger.warning(f"获取股票 {code} 股本信息失败: {e}")
            return {'total_shares': None, 'free_float_shares': None}

    def collect_shares(self, mode: str = 'incremental', max_stocks: Optional[int] = None) -> Dict[str, int]:
        """
        采集并更新股本数据

        Args:
            mode: 'full' 全量更新, 'incremental' 增量更新
            max_stocks: 最大更新数量限制

        Returns:
            dict: 采集结果统计
        """
        session = SessionLocal()
        success_count = 0
        fail_count = 0
        skip_count = 0
        fail_threshold = 3

        try:
            self._ensure_stock_basic_shares_columns(session)
            session.commit()

            stocks = self._get_stocks_to_update(session, mode, max_stocks)
            total = len(stocks)
            self.logger.info(f"股本数据采集开始，模式: {mode}，待更新股票数: {total}")

            for i, stock in enumerate(stocks, 1):
                code = stock[0]
                name = stock[1] or ''

                # 跳过退市股票
                if '退' in name:
                    skip_count += 1
                    continue

                try:
                    shares_info = self._fetch_shares_info(code)

                    if shares_info['total_shares'] is not None or shares_info['free_float_shares'] is not None:
                        session.execute(text('''
                            UPDATE stock_basic_info
                            SET total_shares = COALESCE(:total_shares, total_shares),
                                free_float_shares = COALESCE(:free_float_shares, free_float_shares),
                                shares_updated_at = :updated_at
                            WHERE code = :code
                        '''), {
                            'code': code,
                            'total_shares': shares_info['total_shares'],
                            'free_float_shares': shares_info['free_float_shares'],
                            'updated_at': datetime.now()
                        })
                        success_count += 1
                        self.logger.debug(f"更新股票 {code}({name}) 股本数据: "
                                          f"总股本={shares_info['total_shares']}, "
                                          f"流通股本={shares_info['free_float_shares']}")
                    else:
                        skip_count += 1
                        self.logger.debug(f"股票 {code}({name}) 未获取到股本数据，跳过")

                except Exception as e:
                    fail_count += 1
                    self.logger.error(f"处理股票 {code}({name}) 股本数据时异常: {e}")
                    if fail_count > fail_threshold:
                        raise StockSharesSyncAbortError(
                            f"FAIL_THRESHOLD_EXCEEDED: 股本同步失败股票数 {fail_count} 超过阈值 {fail_threshold}，中止任务"
                        )

                # 每 50 条提交一次
                if i % 50 == 0:
                    session.commit()
                    self.logger.info(f"股本数据采集进度: {i}/{total}，"
                                     f"成功: {success_count}，失败: {fail_count}，跳过: {skip_count}")

                # 限速：避免请求过于频繁
                time.sleep(random.uniform(0.3, 0.8))

            session.commit()

            result = {
                'total': total,
                'success': success_count,
                'failed': fail_count,
                'skipped': skip_count
            }
            self.logger.info(f"股本数据采集完成: {result}")
            return result

        except StockSharesSyncAbortError:
            session.rollback()
            raise
        except Exception as e:
            self.logger.error(f"股本数据采集异常: {e}")
            session.rollback()
            return {
                'total': 0,
                'success': success_count,
                'failed': fail_count,
                'skipped': skip_count,
                'error': str(e)
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

    def run(self, mode: str = 'incremental', max_stocks: Optional[int] = None):
        """
        运行采集器

        Args:
            mode: 'full' 全量更新, 'incremental' 增量更新
            max_stocks: 最大更新数量限制
        """
        self.logger.info(f"股本数据采集器启动，模式: {mode}")
        result = self.collect_shares(mode=mode, max_stocks=max_stocks)
        self.logger.info(f"股本数据采集器结束，结果: {result}")
        return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="股本数据采集器")
    parser.add_argument(
        "--source",
        choices=["akshare", "excel"],
        default="akshare",
        help="数据来源：akshare（默认）或 excel（列格式见文档）",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
        help="akshare 模式：full=全量, incremental=增量(默认)",
    )
    parser.add_argument("--max-stocks", type=int, default=None, help="akshare 最大更新数量")
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
    if args.source == "excel":
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
        collector.run(mode=args.mode, max_stocks=args.max_stocks)


