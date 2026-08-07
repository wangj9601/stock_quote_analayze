"""
增强的实时行情数据采集器
解决SSL连接问题、IP封禁问题，支持代理轮换、User-Agent轮换等功能
"""

import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime

# 直接导入增强的base模块
from .enhanced_base import EnhancedAKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text

class EnhancedRealtimeQuoteCollector(EnhancedAKShareCollector):
    """增强的沪深京A股实时行情数据采集器"""
    
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

        # 确保 stock_basic_info 存在行业字段（部分环境可能缺列，导致 ORM 查询报 UndefinedColumn）
        cursor = session.execute(text('''
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_name='stock_basic_info'
                               AND column_name='industry') THEN
                    ALTER TABLE stock_basic_info ADD COLUMN industry TEXT;
                END IF;
            END
            $$;
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
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
    
    def collect_quotes(self) -> bool:
        """
        采集实时行情数据，使用增强的回退机制
        
        Returns:
            bool: 是否成功
        """
        session = None
        try:
            affected_rows = 0
            try:
                # HTTP 在开 Session 之前
                df = self.get_realtime_quotes_with_fallback()
            except Exception as e:
                self.logger.error(f"所有数据源都失败了: {e}")
                return False

            if df is None or (hasattr(df, 'empty') and df.empty):
                self.logger.error("采集到的实时行情数据为空")
                return False
                
            self.logger.info("采集到 %d 条股票行情数据", len(df))
            session = SessionLocal()

            for _, row in df.iterrows():
                code = row['代码']
                name = row['名称']
                # 名称含「退」的股票（退市等）不再写入实时、历史行情表
                if '退' in (name or ''):
                    continue
                # 获取当前交易日期
                trade_date = datetime.now().strftime('%Y-%m-%d')
                data = {
                    'code': code,
                    'name': name,
                    'trade_date': trade_date,
                    'current_price': self._safe_value(row['最新价']),
                    'change_percent': self._safe_value(row['涨跌幅']),
                    'volume': self._safe_value(row['成交量']),
                    'amount': self._safe_value(row['成交额']),
                    'high': self._safe_value(row['最高']),
                    'low': self._safe_value(row['最低']),
                    'open': self._safe_value(row['今开']),
                    'pre_close': self._safe_value(row['昨收']),
                    'turnover_rate': self._safe_value(row['换手率']),
                    'pe_dynamic': self._safe_value(row['市盈率-动态']),
                    'total_market_value': self._safe_value(row['总市值']),
                    'pb_ratio': self._safe_value(row['市净率']),
                    'circulating_market_value': self._safe_value(row['流通市值']),
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                # --- 重试机制插入 stock_basic_info ---
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        session.execute(text('''
                            INSERT INTO stock_basic_info (code, name, create_date)
                            VALUES (:code, :name, :create_date)
                            ON CONFLICT (code) DO UPDATE SET
                                name = EXCLUDED.name,
                                create_date = EXCLUDED.create_date
                        '''), {'code': code, 'name': name, 'create_date': data['update_time']})
                        break
                    except Exception as e:
                        if ("LockNotAvailable" in str(e)) or ("DeadlockDetected" in str(e)):
                            retry_count += 1
                            session.rollback()
                            self.logger.warning(f"stock_basic_info插入锁冲突，第{retry_count}次重试: {e}")
                            import time
                            time.sleep(0.2 * retry_count)
                            continue
                        else:
                            session.rollback()
                            raise
                if retry_count >= max_retries:
                    self.logger.error(f"stock_basic_info插入锁冲突重试{max_retries}次仍失败: code={code}, name={name}")
                    continue

                # --- 重试机制插入 stock_realtime_quote ---
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        session.execute(    
                            text('''
                                INSERT INTO stock_realtime_quote
                                (code, trade_date, name, current_price, change_percent, volume, amount,
                                high, low, open, pre_close, turnover_rate, pe_dynamic,
                                total_market_value, pb_ratio, circulating_market_value,
                                update_time)
                                VALUES (
                                    :code, :trade_date, :name, :current_price, :change_percent, :volume, :amount,
                                    :high, :low, :open, :pre_close, :turnover_rate, :pe_dynamic,
                                    :total_market_value, :pb_ratio, :circulating_market_value,
                                    :update_time
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
                            '''), 
                            {'code': code, 'trade_date': data['trade_date'], 'name': name, 'current_price': data['current_price'], 'change_percent': data['change_percent'], 'volume': data['volume'], 'amount': data['amount'], 'high': data['high'], 'low': data['low'], 'open': data['open'], 'pre_close': data['pre_close'], 'turnover_rate': data['turnover_rate'], 'pe_dynamic': data['pe_dynamic'], 'total_market_value': data['total_market_value'], 'pb_ratio': data['pb_ratio'], 'circulating_market_value': data['circulating_market_value'], 'update_time': data['update_time']})
                        break
                    except Exception as e:
                        if ("LockNotAvailable" in str(e)) or ("DeadlockDetected" in str(e)):
                            retry_count += 1
                            session.rollback()
                            self.logger.warning(f"stock_realtime_quote插入锁冲突，第{retry_count}次重试: {e}")
                            import time
                            time.sleep(0.2 * retry_count)
                            continue
                        else:
                            session.rollback()
                            raise
                if retry_count >= max_retries:
                    self.logger.error(f"stock_realtime_quote插入锁冲突重试{max_retries}次仍失败: code={code}, name={name}")
                    continue

                affected_rows += 1

            # 记录操作日志
            session.execute(text('''
                INSERT INTO realtime_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)
            '''), {
                'operation_type': 'enhanced_realtime_quote_collect',
                'operation_desc': f'增强采集并更新{len(df)}条股票实时行情数据',
                'affected_rows': affected_rows,
                'status': 'success',
                'error_message': None,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            session.commit()
            self.logger.info("全部股票行情数据采集并入库完成")
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
                        (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                        VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)
                    '''), {
                        'operation_type': 'enhanced_realtime_quote_collect',
                        'operation_desc': '增强采集股票实时行情数据失败',
                        'affected_rows': 0,
                        'status': 'error',
                        'error_message': error_msg,
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
