"""
A股公告数据采集器
负责采集A股公告数据并存储到数据库
"""

import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime, date
import time

# 直接导入base模块
from .base import AKShareCollector
from backend_core.database.db import SessionLocal
from sqlalchemy import text

def convert_dates(obj):
    if isinstance(obj, dict):
        return {k: convert_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_dates(v) for v in obj]
    elif isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    else:
        return obj

class AkshareStockNoticeReportCollector(AKShareCollector):
    """A股公告数据采集器"""
    
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
        
        # 创建A股公告数据表
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS stock_notice_report (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                notice_title TEXT NOT NULL,
                notice_type TEXT,
                publish_date TEXT,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, notice_title, publish_date)
            )
        '''))
        
        # 创建索引
        session.execute(text('''
            CREATE INDEX IF NOT EXISTS idx_stock_notice_code 
            ON stock_notice_report(code)
        '''))
        
        session.execute(text('''
            CREATE INDEX IF NOT EXISTS idx_stock_notice_date 
            ON stock_notice_report(publish_date)
        '''))
        
        session.execute(text('''
            CREATE INDEX IF NOT EXISTS idx_stock_notice_type 
            ON stock_notice_report(notice_type)
        '''))
        
        # 创建操作日志表（如果不存在）
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS realtime_collect_operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    def collect_stock_notices(self, symbol: str = "全部", date_str: Optional[str] = None) -> bool:
        """
        采集A股公告数据
        
        Args:
            symbol: 报告类型，默认为"全部"，可选：全部、重大事项、财务报告、融资公告、风险提示、资产重组、信息变更、持股变动
            date_str: 指定日期，格式：YYYY-MM-DD，如果为None则使用当前日期
        
        Returns:
            bool: 是否成功
        """
        try:
            # 设置默认日期为当前日期
            if date_str is None:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            # 连接数据库
            session = SessionLocal()
            
            # 获取公告数据
            self.logger.info(f"开始采集A股公告数据，类型：{symbol}，日期：{date_str}")
            df = self._retry_on_failure(ak.stock_notice_report, symbol=symbol, date=date_str)
            
            if df.empty:
                self.logger.warning(f"未获取到公告数据，类型：{symbol}，日期：{date_str}")
                # 记录操作日志
                log_data = {
                    'operation_type': 'stock_notice_collect',
                    'operation_desc': f'采集A股公告数据，类型：{symbol}，日期：{date_str}',
                    'affected_rows': 0,
                    'status': 'success',
                    'error_message': '未获取到数据',
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                log_data = convert_dates(log_data)
                session.execute(text('''
                    INSERT INTO realtime_collect_operation_logs 
                    (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)
                '''), log_data)
                session.commit()
                session.close()
                return True
            
            self.logger.info(f"采集到 {len(df)} 条A股公告数据")
            
            # 批量处理数据
            affected_rows = 0
            for _, row in df.iterrows():
                try:
                    # 准备数据
                    data = {
                        'code': str(row['代码']).strip(),
                        'name': str(row['名称']).strip(),
                        'notice_title': str(row['公告标题']).strip(),
                        'notice_type': str(row['公告类型']).strip(),
                        'publish_date': str(row['公告日期']).strip(),
                        'url': str(row['网址']).strip() if pd.notna(row['网址']) else '',
                        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # 插入或更新数据（PostgreSQL UPSERT）
                    data = convert_dates(data)
                    session.execute(
                        text('''
                            INSERT INTO stock_notice_report
                            (code, name, notice_title, notice_type, publish_date, url, updated_at)
                            VALUES (:code, :name, :notice_title, :notice_type, :publish_date, :url, :updated_at)
                            ON CONFLICT (code, notice_title, publish_date)
                            DO UPDATE SET
                                name = EXCLUDED.name,
                                notice_type = EXCLUDED.notice_type,
                                url = EXCLUDED.url,
                                updated_at = EXCLUDED.updated_at
                        '''),
                        data
                    )
                    affected_rows += 1
                    
                except Exception as e:
                    self.logger.warning(f"处理单条公告数据时出错: {str(e)}, 数据: {row.to_dict()}")
                    raise
            
            # 记录操作日志
            log_data = {
                'operation_type': 'stock_notice_collect',
                'operation_desc': f'采集并更新A股公告数据，类型：{symbol}，日期：{date_str}，共{len(df)}条数据',
                'affected_rows': affected_rows,
                'status': 'success',
                'error_message': None,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            log_data = convert_dates(log_data)
            session.execute(text('''
                INSERT INTO realtime_collect_operation_logs 
                (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)
            '''), log_data)
            
            session.commit()
            session.close()
            
            self.logger.info(f"A股公告数据采集并入库完成，成功处理 {affected_rows} 条数据")
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"采集A股公告数据时出错: {error_msg}", exc_info=True)
            
            # 记录错误日志
            try:
                session = SessionLocal()
                log_data = {
                    'operation_type': 'stock_notice_collect',
                    'operation_desc': f'采集A股公告数据失败，类型：{symbol}，日期：{date_str}',
                    'affected_rows': 0,
                    'status': 'error',
                    'error_message': error_msg,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                log_data = convert_dates(log_data)
                session.execute(text('''
                    INSERT INTO realtime_collect_operation_logs 
                    (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                    VALUES (:operation_type, :operation_desc, :affected_rows, :status, :error_message, :created_at)
                '''), log_data)
                session.commit()
                session.close()
            except Exception as log_error:
                self.logger.error(f"记录错误日志失败: {str(log_error)}")
            
            return False
    
    def collect_multiple_types(self, date_str: Optional[str] = None) -> bool:
        """
        采集多种类型的公告数据
        
        Args:
            date_str: 指定日期，格式：YYYY-MM-DD，如果为None则使用当前日期
        
        Returns:
            bool: 是否全部成功
        """
        # 定义要采集的公告类型
        notice_types = [
            "全部",
            "重大事项", 
            "财务报告", 
            "融资公告", 
            "风险提示", 
            "资产重组", 
            "信息变更", 
            "持股变动"
        ]
        
        success_count = 0
        total_count = len(notice_types)
        
        for notice_type in notice_types:
            try:
                self.logger.info(f"开始采集公告类型：{notice_type}")
                if self.collect_stock_notices(symbol=notice_type, date_str=date_str):
                    success_count += 1
                    self.logger.info(f"公告类型 {notice_type} 采集成功")
                else:
                    self.logger.warning(f"公告类型 {notice_type} 采集失败")
                    
                # 添加延迟避免请求过于频繁
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"采集公告类型 {notice_type} 时出错: {str(e)}")
        
        self.logger.info(f"多类型公告采集完成，成功 {success_count}/{total_count}")
        return success_count == total_count
    
    def get_notices_by_stock(self, stock_code: str, limit: int = 100) -> pd.DataFrame:
        """
        按股票代码查询公告数据
        
        Args:
            stock_code: 股票代码
            limit: 返回数据条数限制
        
        Returns:
            pandas.DataFrame: 公告数据
        """
        try:
            session = SessionLocal()
            
            query = text('''
                SELECT code, name, notice_title, notice_type, publish_date, url, created_at
                FROM stock_notice_report 
                WHERE code = ? 
                ORDER BY publish_date DESC, created_at DESC
                LIMIT ?
            ''')
            
            df = pd.read_sql_query(query, session.connection(), params=(stock_code, limit))
            session.close()
            
            self.logger.info(f"查询到股票 {stock_code} 的 {len(df)} 条公告数据")
            return df
            
        except Exception as e:
            self.logger.error(f"查询股票公告数据时出错: {str(e)}")
            return pd.DataFrame()
    
    def get_notices_by_date(self, date_str: str, limit: int = 100) -> pd.DataFrame:
        """
        按日期查询公告数据
        
        Args:
            date_str: 日期字符串，格式：YYYY-MM-DD
            limit: 返回数据条数限制
        
        Returns:
            pandas.DataFrame: 公告数据
        """
        try:
            session = SessionLocal()
            
            query = text('''
                SELECT code, name, notice_title, notice_type, publish_date, url, created_at
                FROM stock_notice_report 
                WHERE publish_date = ? 
                ORDER BY created_at DESC
                LIMIT ?
            ''')
            
            df = pd.read_sql_query(query, session.connection(), params=(date_str, limit))
            session.close()
            
            self.logger.info(f"查询到日期 {date_str} 的 {len(df)} 条公告数据")
            return df
            
        except Exception as e:
            self.logger.error(f"查询日期公告数据时出错: {str(e)}")
            return pd.DataFrame() 