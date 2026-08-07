"""
港股实时行情数据采集器
负责采集港股实时行情数据并存储到数据库
"""

import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime

# 直接导入base模块
from .base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text

class HKRealtimeQuoteCollector(AKShareCollector):
    """港股实时行情数据采集器"""
    
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
        try:
            session.execute(text('''
                CREATE TABLE IF NOT EXISTS stock_basic_info_hk (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            session.commit()
            try:
                session.execute(text('''
                    ALTER TABLE stock_basic_info_hk
                    ADD COLUMN collect_enabled BOOLEAN DEFAULT TRUE
                '''))
                session.commit()
            except Exception:
                session.rollback()

            session.execute(text('''
                CREATE TABLE IF NOT EXISTS stock_realtime_quote_hk (
                    code TEXT,
                    trade_date TEXT,
                    name TEXT,
                    english_name TEXT,
                    current_price REAL,
                    change_percent REAL,
                    change_amount REAL,
                    volume REAL,
                    amount REAL,
                    high REAL,
                    low REAL,
                    open REAL,
                    pre_close REAL,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(code, trade_date),
                    FOREIGN KEY(code) REFERENCES stock_basic_info_hk(code)
                )
            '''))
            session.commit()
            
            # 如果表已存在，尝试添加新字段（如果不存在）
            try:
                # 检查并添加 english_name 字段
                session.execute(text('''
                    ALTER TABLE stock_realtime_quote_hk 
                    ADD COLUMN english_name TEXT
                '''))
                session.commit()
            except Exception:
                # 字段可能已存在，忽略错误
                session.rollback()
            
            try:
                # 检查并添加 change_amount 字段
                session.execute(text('''
                    ALTER TABLE stock_realtime_quote_hk 
                    ADD COLUMN change_amount REAL
                '''))
                session.commit()
            except Exception:
                # 字段可能已存在，忽略错误
                session.rollback()

            return True
        except Exception as e:
            self.logger.error(f"初始化数据库表结构失败: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
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
        采集港股实时行情数据
        Returns:
            bool: 是否成功
        """
        session = None
        try:
            self._init_db()  # 确保表结构存在
            affected_rows = 0
            # 优先使用 stock_hk_spot_em（东方财富接口），因为它返回的数据更全
            # HTTP 在开 Session 之前
            df = None
            source_name = None
            
            # 先尝试调用 stock_hk_spot_em（东方财富接口，数据更全）
            try:
                df = self._retry_on_failure(ak.stock_hk_spot_em)
                source_name = "stock_hk_spot_em"
                self.logger.info("成功使用 stock_hk_spot_em 接口获取港股实时行情数据")
            except Exception as e1:
                self.logger.warning(f"调用 stock_hk_spot_em 失败，尝试使用 stock_hk_spot，错误详情: {e1}")
                # 如果 stock_hk_spot_em 失败，则尝试调用新浪财经接口
                try:
                    df = self._retry_on_failure(ak.stock_hk_spot)
                    source_name = "stock_hk_spot"
                    self.logger.info("成功使用 stock_hk_spot 接口获取港股实时行情数据")
                except Exception as e2:
                    self.logger.error(f"调用 stock_hk_spot 也失败: {e2}")
                    return False
            
            if df is None or (hasattr(df, 'empty') and df.empty):
                self.logger.error("akshare港股实时行情数据为空或无法获取")
                return False

            session = SessionLocal()
            data_count = len(df)
            self.logger.info("采集到 %d 条港股行情数据（数据源: %s）", data_count, source_name)
            
            # 检查数据量是否正常（港股应该有2000+只股票）
            if data_count < 1000:
                self.logger.warning(f"警告：港股实时行情数据量异常偏少（{data_count}条），正常应该有2000+条。可能是接口限制或数据源问题。")
            
            # 打印列名和第一条数据用于调试
            if len(df) > 0:
                self.logger.info(f"数据列名: {list(df.columns)}")
                # 打印第一条数据的前几个字段用于验证
                first_row = df.iloc[0]
                self.logger.info(f"第一条数据示例 - 代码: {first_row.get('代码', 'N/A')}, "
                               f"中文名称: {first_row.get('中文名称', first_row.get('名称', 'N/A'))}, "
                               f"最新价: {first_row.get('最新价', 'N/A')}")
            
            for idx, row in df.iterrows():
                try:
                    # 港股代码格式：5位数字，如 "00700"
                    # 兼容不同的字段名，使用更安全的方式访问（使用row.get()方法）
                    code = None
                    # 尝试多种可能的字段名
                    for field_name in ['代码', '股票代码', 'symbol', 'code']:
                        if field_name in df.columns:
                            val = row.get(field_name)
                            if val is not None and pd.notna(val):
                                code = str(val).strip()
                                if code:
                                    break
                    
                    if not code:
                        self.logger.warning(f"无法获取股票代码，跳过该行。可用字段: {list(df.columns)}, 行数据: {row.to_dict() if hasattr(row, 'to_dict') else str(row)}")
                        continue
                    
                    # 兼容不同的名称字段：中文名称、名称
                    name = None
                    # 尝试多种可能的字段名
                    for field_name in ['中文名称', '名称', 'name', '股票名称']:
                        if field_name in df.columns:
                            val = row.get(field_name)
                            if val is not None and pd.notna(val):
                                name = str(val).strip()
                                if name:
                                    break
                    
                    if not name:
                        self.logger.warning(f"股票 {code} 无法获取名称，跳过")
                        continue
                    
                    # 获取当前交易日期
                    trade_date = datetime.now().strftime('%Y-%m-%d')
                    
                    # 处理英文名称，兼容不同的字段名
                    english_name = None
                    for field_name in ['英文名称', '英文名', 'engname', 'english_name']:
                        if field_name in df.columns:
                            val = row.get(field_name)
                            if val is not None and pd.notna(val):
                                english_name = str(val).strip()
                                if english_name:
                                    break
                    
                    # 安全地获取数值字段
                    def safe_get_value(*keys):
                        """安全地获取Series中的值"""
                        for key in keys:
                            if key and key in df.columns:
                                val = row.get(key)
                                if val is not None and pd.notna(val):
                                    return val
                        return None
                    
                    # 按数据源区分成交量单位：
                    # - 东方财富 stock_hk_spot_em：返回股，需 /100 转手
                    # - 新浪 stock_hk_spot：按当前业务约定直接按手入库（不换算）
                    raw_vol = self._safe_value(safe_get_value('成交量', 'volume'))
                    if raw_vol is None:
                        volume = None
                    elif source_name == "stock_hk_spot_em":
                        volume = raw_vol / 100.0
                    else:
                        volume = raw_vol
                    data = {
                        'code': code,
                        'name': name,
                        'trade_date': trade_date,
                        'english_name': english_name,
                        'current_price': self._safe_value(safe_get_value('最新价', '现价', 'lasttrade')),
                        'change_percent': self._safe_value(safe_get_value('涨跌幅', '涨跌%', 'changepercent')),
                        'change_amount': self._safe_value(safe_get_value('涨跌额', '涨跌', 'pricechange')),
                        'volume': volume,
                        'amount': self._safe_value(safe_get_value('成交额', 'amount')),
                        'high': self._safe_value(safe_get_value('最高', 'high')),
                        'low': self._safe_value(safe_get_value('最低', 'low')),
                        'open': self._safe_value(safe_get_value('今开', '开盘', 'open')),
                        'pre_close': self._safe_value(safe_get_value('昨收', '昨收价', 'prevclose')),
                        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                    # 现价为空/0/非正数时跳过，不写入数据库
                    if data['current_price'] is None or float(data['current_price']) <= 0:
                        self.logger.debug(f"跳过无效港股现价数据: code={code}, name={name}, current_price={data['current_price']}")
                        continue

                    # --- 重试机制插入 stock_basic_info_hk ---
                    max_retries = 3
                    retry_count = 0
                    while retry_count < max_retries:
                        try:
                            session.execute(text('''
                                INSERT INTO stock_basic_info_hk (code, name, create_date)
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
                                self.logger.warning(f"stock_basic_info_hk插入锁冲突，第{retry_count}次重试: {e}")
                                import time
                                time.sleep(0.2 * retry_count)
                                continue
                            else:
                                session.rollback()
                                raise
                    if retry_count >= max_retries:
                        self.logger.error(f"stock_basic_info_hk插入锁冲突重试{max_retries}次仍失败: code={code}, name={name}")
                        continue

                    # --- 重试机制插入 stock_realtime_quote_hk ---
                    retry_count = 0
                    while retry_count < max_retries:
                        try:
                            session.execute(    
                                text('''
                                    INSERT INTO stock_realtime_quote_hk
                                    (code, trade_date, name, english_name, current_price, change_percent, volume, amount,
                                    change_amount, high, low, open, pre_close, update_time)
                                    VALUES (
                                        :code, :trade_date, :name, :english_name, :current_price, :change_percent, :volume, :amount,
                                        :change_amount, :high, :low, :open, :pre_close, :update_time)
                                    ON CONFLICT (code, trade_date) DO UPDATE SET
                                        name = EXCLUDED.name,
                                        english_name = EXCLUDED.english_name,
                                        current_price = EXCLUDED.current_price,
                                        change_percent = EXCLUDED.change_percent,
                                        volume = EXCLUDED.volume,
                                        amount = EXCLUDED.amount,
                                        change_amount = EXCLUDED.change_amount,
                                        high = EXCLUDED.high,
                                        low = EXCLUDED.low,
                                        open = EXCLUDED.open,
                                        pre_close = EXCLUDED.pre_close,
                                        update_time = EXCLUDED.update_time
                                '''), 
                                {'code': code, 'trade_date': data['trade_date'], 'name': name, 
                                 'english_name': data['english_name'], 'current_price': data['current_price'], 'change_percent': data['change_percent'], 
                                 'volume': data['volume'], 'amount': data['amount'], 
                                 'change_amount': data['change_amount'], 'high': data['high'], 'low': data['low'], 
                                 'open': data['open'], 'pre_close': data['pre_close'], 
                                 'update_time': data['update_time']})
                            break
                        except Exception as e:
                            if ("LockNotAvailable" in str(e)) or ("DeadlockDetected" in str(e)):
                                retry_count += 1
                                session.rollback()
                                self.logger.warning(f"stock_realtime_quote_hk插入锁冲突，第{retry_count}次重试: {e}")
                                import time
                                time.sleep(0.2 * retry_count)
                                continue
                            else:
                                session.rollback()
                                raise
                    if retry_count >= max_retries:
                        self.logger.error(f"stock_realtime_quote_hk插入锁冲突重试{max_retries}次仍失败: code={code}, name={name}")
                        continue

                    affected_rows += 1
                    
                    # 每处理100条记录打印一次进度
                    if affected_rows % 100 == 0:
                        self.logger.info(f"已处理 {affected_rows} 条港股数据")
                        
                except Exception as row_e:
                    self.logger.error(f"处理第 {idx+1} 条港股数据失败: {row_e}")
                    self.logger.debug(f"失败的数据行: {row.to_dict() if hasattr(row, 'to_dict') else str(row)}")
                    continue

            # 记录操作日志
            session.execute(text('''
                INSERT INTO realtime_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, collect_source, created_at)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :collect_source, :created_at)
            '''), {
                'operation_type': 'hk_realtime_quote_collect',
                'operation_desc': f'采集并更新{len(df)}条港股实时行情数据',
                'affected_rows': affected_rows,
                'status': 'success',
                'error_message': None,
                'collect_source': 'akshare',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            session.commit()
            self.logger.info("全部港股行情数据采集并入库完成")
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
                        'operation_type': 'hk_realtime_quote_collect',
                        'operation_desc': '采集港股实时行情数据失败',
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

