"""
实时行情数据采集器
负责采集股票实时行情数据并存储到数据库
"""

import akshare as ak
import pandas as pd
import time
from typing import Optional, Dict, Any, List, Set, Tuple
from pathlib import Path
import logging
from datetime import datetime

# 直接导入base模块
from backend_core.data_collectors.akshare.base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text

A_SHARE_LOT_SIZE = 100  # A股1手=100股
DEFAULT_BATCH_SIZE = 500


def normalize_stock_code(code: Any, data_source: str = "em") -> Optional[str]:
    """统一 A 股代码为 6 位字符串。"""
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return None
    s = str(code).strip()
    if not s or s.lower() == "nan":
        return None
    if data_source == "sina" and len(s) > 2 and s[:2].isalpha():
        s = s[2:]
    if s.isdigit():
        return s.zfill(6)
    return s


def should_collect_stock(code: str, disabled_codes: Set[str]) -> bool:
    """collect_enabled=false 的已登记股票跳过；未登记的新股允许写入。"""
    return code not in disabled_codes


class AkshareRealtimeQuoteCollector(AKShareCollector):
    """沪深京A股实时行情数据采集器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        super().__init__(config)
        self.db_file = Path(self.config.get('db_file', 'database/stock_analysis.db'))
        
    def _init_db(self) -> bool:
        """
        初始化数据库表结构
        
        Returns:
            bool: 是否成功
        """
        session = SessionLocal()
        cursor = session.execute(text('''
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT,
                create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        session.commit()

        cursor = session.execute(text('''
            CREATE TABLE IF NOT EXISTS stock_realtime_quote (
                code TEXT,
                trade_date TEXT,
                name TEXT,
                current_price REAL,
                change_percent REAL,
                volume REAL,
                amount REAL,
                high REAL,
                low REAL,
                open REAL,
                pre_close REAL,
                turnover_rate REAL,
                pe_dynamic REAL,
                total_market_value REAL,
                pb_ratio REAL,
                circulating_market_value REAL,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(code, trade_date),
                FOREIGN KEY(code) REFERENCES stock_basic_info(code)
            )
        '''))
        session.commit()

        cursor = session.execute(text('''
            CREATE TABLE IF NOT EXISTS realtime_collect_operation_logs (
                id SERIAL PRIMARY KEY,
                operation_type TEXT NOT NULL,
                operation_desc TEXT NOT NULL,
                affected_rows INTEGER,
                status TEXT NOT NULL,
                error_message TEXT,
                collect_source TEXT DEFAULT 'akshare',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        # 添加 collect_source 字段（如果表已存在但字段不存在）
        session.execute(text('''
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='realtime_collect_operation_logs' 
                               AND column_name='collect_source') THEN
                    ALTER TABLE realtime_collect_operation_logs ADD COLUMN collect_source TEXT DEFAULT 'akshare';
                END IF;
            END
            $$;
        '''))
        session.commit()

        # 为 stock_basic_info 表新增股本相关字段（用于自行计算换手率）
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

                -- GMS/其它策略会用到行业字段。历史上部分库可能缺少该列，需保证兜底存在。
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_name='stock_basic_info'
                               AND column_name='industry') THEN
                    ALTER TABLE stock_basic_info ADD COLUMN industry TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_name='stock_basic_info'
                               AND column_name='collect_enabled') THEN
                    ALTER TABLE stock_basic_info ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE;
                END IF;
            END
            $$;
        '''))
        session.commit()

        session.close()
        return True
    
    def _safe_value(self, val: Any) -> Optional[float]:
        """
        安全地转换数值
        
        Args:
            val: 输入值
            
        Returns:
            Optional[float]: 转换后的浮点数，如果转换失败则返回None
        """
        return None if pd.isna(val) else float(val)

    def _calculate_turnover_rate_from_shares(
        self,
        code: str,
        volume_hand: Optional[float],
        current_price: Optional[float],
        circulating_market_value: Optional[float],
        free_float_by_code: Optional[Dict[str, float]] = None,
    ) -> Optional[float]:
        """
        当上游未提供换手率时，按股本口径回退计算。

        口径：
        - 实时表 volume 单位为「手」
        - stock_basic_info.free_float_shares 单位为「股」
        - 换手率(%) = (volume_hand * 100) / free_float_shares * 100
        """
        try:
            if volume_hand is None or float(volume_hand) <= 0:
                return None

            free_float_shares = None
            if free_float_by_code and code in free_float_by_code:
                free_float_shares = free_float_by_code[code]
            elif (
                circulating_market_value is not None
                and current_price is not None
                and float(circulating_market_value) > 0
                and float(current_price) > 0
            ):
                free_float_shares = float(circulating_market_value) / float(current_price)

            if free_float_shares is None or free_float_shares <= 0:
                return None

            volume_shares = float(volume_hand) * A_SHARE_LOT_SIZE
            return round(volume_shares / free_float_shares * 100, 4)
        except Exception as e:
            self.logger.debug(f"换手率回退计算失败: code={code}, err={e}")
            return None

    def _load_collect_policy(self, session) -> Tuple[Set[str], Dict[str, float]]:
        """返回 (collect_enabled=false 的代码集合, 流通股本映射)。"""
        disabled: Set[str] = set()
        free_float: Dict[str, float] = {}
        rows = session.execute(
            text(
                """
                SELECT code, collect_enabled, free_float_shares
                FROM stock_basic_info
                """
            )
        ).fetchall()
        for row in rows:
            code = normalize_stock_code(row[0]) or str(row[0]).strip()
            if row[1] is False:
                disabled.add(code)
            if row[2] is not None:
                try:
                    fv = float(row[2])
                    if fv > 0:
                        free_float[code] = fv
                except (TypeError, ValueError):
                    pass
        return disabled, free_float

    def _bulk_upsert_with_retry(
        self,
        session,
        sql: str,
        params_list: List[Dict[str, Any]],
        label: str,
        batch_size: int,
    ) -> int:
        if not params_list:
            return 0
        max_retries = self.config.get("max_retries", 3)
        total = 0
        for start in range(0, len(params_list), batch_size):
            chunk = params_list[start : start + batch_size]
            retry = 0
            while retry < max_retries:
                try:
                    session.execute(text(sql), chunk)
                    session.commit()
                    total += len(chunk)
                    break
                except Exception as e:
                    if ("LockNotAvailable" in str(e)) or ("DeadlockDetected" in str(e)):
                        retry += 1
                        session.rollback()
                        self.logger.warning(
                            "%s 批量写入锁冲突，第 %s 次重试（batch %s-%s）: %s",
                            label,
                            retry,
                            start,
                            start + len(chunk),
                            e,
                        )
                        time.sleep(0.2 * retry)
                        continue
                    session.rollback()
                    raise
            else:
                self.logger.error(
                    "%s 批量写入重试 %s 次仍失败，跳过本批 %s 条",
                    label,
                    max_retries,
                    len(chunk),
                )
        return total

    def _build_rows_from_df(
        self,
        df: pd.DataFrame,
        data_source: str,
        disabled_codes: Set[str],
        free_float_by_code: Dict[str, float],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        """解析接口数据，返回 (basic_info 行, quote 行, 跳过数)。"""
        trade_date = datetime.now().strftime("%Y-%m-%d")
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        basic_rows: List[Dict[str, Any]] = []
        quote_rows: List[Dict[str, Any]] = []
        skipped = 0

        for _, row in df.iterrows():
            code = normalize_stock_code(row.get("代码"), data_source)
            if not code:
                skipped += 1
                continue
            name = row.get("名称")
            if "退" in (name or ""):
                skipped += 1
                continue
            if not should_collect_stock(code, disabled_codes):
                skipped += 1
                continue

            raw_vol = self._safe_value(row.get("成交量"))
            volume = (
                (raw_vol / 100)
                if (data_source == "sina" and raw_vol is not None)
                else raw_vol
            )
            current_price = self._safe_value(row.get("最新价"))
            if current_price is None or float(current_price) <= 0:
                skipped += 1
                continue

            turnover_rate = (
                self._safe_value(row.get("换手率"))
                if "换手率" in row.index
                else None
            )
            if data_source == "sina" and turnover_rate is None:
                turnover_rate = self._calculate_turnover_rate_from_shares(
                    code=code,
                    volume_hand=volume,
                    current_price=current_price,
                    circulating_market_value=self._safe_value(row.get("流通市值"))
                    if "流通市值" in row.index
                    else None,
                    free_float_by_code=free_float_by_code,
                )

            basic_rows.append(
                {"code": code, "name": name, "create_date": update_time}
            )
            quote_rows.append(
                {
                    "code": code,
                    "trade_date": trade_date,
                    "name": name,
                    "current_price": current_price,
                    "change_percent": self._safe_value(row.get("涨跌幅")),
                    "volume": volume,
                    "amount": self._safe_value(row.get("成交额")),
                    "high": self._safe_value(row.get("最高")),
                    "low": self._safe_value(row.get("最低")),
                    "open": self._safe_value(row.get("今开")),
                    "pre_close": self._safe_value(row.get("昨收")),
                    "turnover_rate": turnover_rate,
                    "pe_dynamic": (
                        self._safe_value(row.get("市盈率-动态"))
                        if "市盈率-动态" in row.index
                        else self._safe_value(row.get("市盈率"))
                        if "市盈率" in row.index
                        else None
                    ),
                    "total_market_value": (
                        self._safe_value(row.get("总市值"))
                        if "总市值" in row.index
                        else None
                    ),
                    "pb_ratio": (
                        self._safe_value(row.get("市净率"))
                        if "市净率" in row.index
                        else None
                    ),
                    "circulating_market_value": (
                        self._safe_value(row.get("流通市值"))
                        if "流通市值" in row.index
                        else None
                    ),
                    "update_time": update_time,
                }
            )
        return basic_rows, quote_rows, skipped

    def collect_quotes(self) -> bool:
        """
        采集实时行情数据
        Returns:
            bool: 是否成功
        """
        session = None
        try:
            affected_rows = 0
            data_source = "em"  # 东方财富 stock_zh_a_spot_em：成交量单位为「手」
            # HTTP 必须在开 Session 之前，避免空会话/异常路径泄漏连接
            try:
                df = self._retry_on_failure(ak.stock_zh_a_spot_em)
            except Exception as e:
                self.logger.warning(f"东方财富数据接口（stock_zh_a_spot_em）调用失败: {e}，将尝试切换至新浪接口")
                try:
                    # 直接尝试新浪行情数据源（新浪：成交量单位为「股」）
                    data_source = "sina"
                    df_sina = self._retry_on_failure(ak.stock_zh_a_spot)
                    if df_sina is not None and hasattr(df_sina, 'empty') and not df_sina.empty:
                        df = df_sina
                        self.logger.info(f"新浪行情接口采集到 {len(df)} 条股票数据")
                    else:
                        self.logger.error("新浪数据源（stock_zh_a_spot）采集数据为空")
                        df = None
                except Exception as e4:
                    self.logger.error(f"调用新浪数据源（stock_zh_a_spot）失败: {e4}")
                    df = None

            if df is None or (hasattr(df, 'empty') and df.empty):
                self.logger.error("akshare主数据源采集到的实时行情数据为空")
                return False
            self.logger.info("采集到 %d 条股票行情数据", len(df))

            session = SessionLocal()
            disabled_codes, free_float_by_code = self._load_collect_policy(session)
            if disabled_codes:
                self.logger.info(
                    "collect_enabled=false 已登记股票 %d 只，将跳过实时写入",
                    len(disabled_codes),
                )

            basic_rows, quote_rows, skipped = self._build_rows_from_df(
                df, data_source, disabled_codes, free_float_by_code
            )
            batch_size = int(self.config.get("batch_size", DEFAULT_BATCH_SIZE))

            basic_sql = """
                INSERT INTO stock_basic_info (code, name, create_date)
                VALUES (:code, :name, :create_date)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    create_date = EXCLUDED.create_date
            """
            quote_sql = """
                INSERT INTO stock_realtime_quote
                (code, trade_date, name, current_price, change_percent, volume, amount,
                 high, low, open, pre_close, turnover_rate, pe_dynamic,
                 total_market_value, pb_ratio, circulating_market_value, update_time)
                VALUES (
                    :code, :trade_date, :name, :current_price, :change_percent, :volume, :amount,
                    :high, :low, :open, :pre_close, :turnover_rate, :pe_dynamic,
                    :total_market_value, :pb_ratio, :circulating_market_value, :update_time
                )
                ON CONFLICT (code, trade_date) DO UPDATE SET
                    name = EXCLUDED.name,
                    current_price = EXCLUDED.current_price,
                    change_percent = EXCLUDED.change_percent,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    open = EXCLUDED.open,
                    pre_close = EXCLUDED.pre_close,
                    turnover_rate = EXCLUDED.turnover_rate,
                    pe_dynamic = EXCLUDED.pe_dynamic,
                    total_market_value = EXCLUDED.total_market_value,
                    pb_ratio = EXCLUDED.pb_ratio,
                    circulating_market_value = EXCLUDED.circulating_market_value,
                    update_time = EXCLUDED.update_time
            """

            self._bulk_upsert_with_retry(
                session, basic_sql, basic_rows, "stock_basic_info", batch_size
            )
            affected_rows = self._bulk_upsert_with_retry(
                session, quote_sql, quote_rows, "stock_realtime_quote", batch_size
            )

            desc = (
                f"接口 {len(df)} 条，写入 {affected_rows} 条实时行情"
                f"（跳过 {skipped} 条，含 collect_enabled=false/无效价/退市）"
            )
            session.execute(text('''
                INSERT INTO realtime_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source, created_at)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source, :created_at)
            '''), {
                'operation_type': 'realtime_quote_collect',
                'operation_desc': desc,
                'affected_rows': affected_rows,
                'status': 'success',
                'error_message': None,
                'collect_source': 'akshare',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            session.commit()
            self.logger.info("批量入库完成: %s", desc)
            return True
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            # 记录错误日志
            try:
                if session is not None:
                    try:
                        session.rollback()
                    except Exception:
                        pass
                    session.execute(text('''
                        INSERT INTO realtime_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, error_message, collect_source, created_at)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source, :created_at)
                    '''), {
                        'operation_type': 'realtime_quote_collect',
                        'operation_desc': '采集股票实时行情数据失败',
                        'affected_rows': 0,
                        'status': 'error',
                        'error_message': error_msg,
                        'collect_source': 'akshare',
                        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    session.commit()
            except Exception as log_error:
                self.logger.error("记录错误日志失败: %s", str(log_error))
            return False
        finally:
            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    pass
                try:
                    session.close()
                except Exception:
                    pass
