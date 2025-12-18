import akshare as ak
import pandas as pd
from datetime import datetime
import logging
from pathlib import Path
import time
from backend_core.config.config import DATA_COLLECTORS
from backend_core.database.db import SessionLocal
from sqlalchemy import text

class HKIndexRealtimeCollector:
    """港股指数实时行情数据采集器"""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = DATA_COLLECTORS['akshare']['db_file']
        self.db_file = Path(db_path)
        self.logger = logging.getLogger('HKIndexRealtimeCollector')
        # 确保数据库目录存在
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """初始化数据库表"""
        session = SessionLocal()
        
        # 港股指数基础信息表
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS hk_index_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                english_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        
        # 港股指数实时行情表（按日期存储）
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS hk_index_realtime_quotes (
                code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL,
                change REAL,
                pct_chg REAL,
                open REAL,
                pre_close REAL,
                high REAL,
                low REAL,
                volume REAL,
                amount REAL,
                update_time TEXT,
                collect_time TEXT,
                PRIMARY KEY (code, trade_date)
            )
        '''))
        
        # 港股指数历史行情表
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS hk_index_historical_quotes (
                code TEXT,
                name TEXT NOT NULL,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                change REAL,
                pct_chg REAL,
                collected_source TEXT,
                collected_date TEXT,
                PRIMARY KEY (code, date)
            )
        '''))
        
        # 操作日志表
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS hk_index_collect_operation_logs (
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
        return session

    def _retry_on_failure(self, func, max_retries=3, retry_delay=5, *args, **kwargs):
        """失败重试装饰器"""
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if i == max_retries - 1:
                    self.logger.error(f"函数 {func.__name__ if hasattr(func, '__name__') else 'unknown'} 执行失败: {str(e)}")
                    raise
                self.logger.warning(f"第 {i+1} 次重试失败: {str(e)}，{retry_delay}秒后重试")
                time.sleep(retry_delay)
        raise Exception("重试次数用尽")

    def collect_realtime_quotes(self):
        """采集港股指数实时行情数据（全量）"""
        session = None
        try:
            session = self._init_db()
            
            collected_data = []
            basic_info_data = []
            
            # 优先尝试使用 stock_hk_index_spot_em 获取全量数据（带重试）
            try:
                self.logger.info('尝试使用 stock_hk_index_spot_em 接口获取全量港股指数数据')
                df = self._retry_on_failure(ak.stock_hk_index_spot_em, max_retries=3, retry_delay=5)
                
                if df is not None and not df.empty:
                    self.logger.info(f'stock_hk_index_spot_em 返回数据形状: {df.shape}')
                    
                    # 处理全量数据
                    for _, row in df.iterrows():
                        try:
                            # 提取指数代码和名称
                            code = str(row.get('代码', row.get('code', '')))
                            name = str(row.get('名称', row.get('name', '')))
                            
                            if not code or not name:
                                continue
                            
                            # 基础信息
                            basic_info = {
                                'code': code,
                                'name': name,
                                'english_name': None  # 如果有英文名称字段可以提取
                            }
                            basic_info_data.append(basic_info)
                            
                            # 实时行情数据
                            data = {
                                'code': code,
                                'name': name,
                                'price': self._safe_float(row.get('最新价', row.get('current', row.get('price', None)))),
                                'change': self._safe_float(row.get('涨跌额', row.get('change', row.get('change_amount', None)))),
                                'pct_chg': self._safe_float(row.get('涨跌幅', row.get('change_percent', row.get('pct_chg', None)))),
                                'open': self._safe_float(row.get('今开', row.get('open', None))),
                                'pre_close': self._safe_float(row.get('昨收', row.get('pre_close', None))),
                                'high': self._safe_float(row.get('最高', row.get('high', None))),
                                'low': self._safe_float(row.get('最低', row.get('low', None))),
                                'volume': self._safe_float(row.get('成交量', row.get('volume', row.get('vol', 0)))),
                                'amount': self._safe_float(row.get('成交额', row.get('amount', 0))),
                            }
                            collected_data.append(data)
                            
                        except Exception as e:
                            self.logger.warning(f'处理指数时出错: {str(e)}')
                            continue
                    
                    if not collected_data:
                        raise Exception('未能从 stock_hk_index_spot_em 获取任何指数数据')
                    
                    self.logger.info(f'成功从 stock_hk_index_spot_em 获取 {len(collected_data)} 条港股指数数据')
                        
            except Exception as e1:
                self.logger.warning(f'stock_hk_index_spot_em 接口调用失败: {str(e1)}，尝试使用 stock_hk_index_spot_sina')
                
                # 失败则尝试使用 stock_hk_index_spot_sina 获取全量数据（不需要参数）
                try:
                    self.logger.info('尝试使用 stock_hk_index_spot_sina 接口获取全量港股指数数据')
                    df = self._retry_on_failure(ak.stock_hk_index_spot_sina, max_retries=3, retry_delay=5)
                            
                    if df is not None and not df.empty:
                        self.logger.info(f'stock_hk_index_spot_sina 返回数据形状: {df.shape}')
                        
                        # 处理全量数据
                        for _, row in df.iterrows():
                            try:
                                # 提取指数代码和名称
                                code = str(row.get('代码', row.get('code', '')))
                                name = str(row.get('名称', row.get('name', '')))
                                
                                if not code or not name:
                                    continue
                                
                                # 基础信息
                                basic_info = {
                                    'code': code,
                                    'name': name,
                                    'english_name': None
                                }
                                basic_info_data.append(basic_info)
                                
                                # 实时行情数据
                                data = {
                                    'code': code,
                                    'name': name,
                                    'price': self._safe_float(row.get('最新价', row.get('current', row.get('price', None)))),
                                    'change': self._safe_float(row.get('涨跌额', row.get('change', row.get('change_amount', None)))),
                                    'pct_chg': self._safe_float(row.get('涨跌幅', row.get('change_percent', row.get('pct_chg', None)))),
                                    'open': self._safe_float(row.get('今开', row.get('open', None))),
                                    'pre_close': self._safe_float(row.get('昨收', row.get('pre_close', None))),
                                    'high': self._safe_float(row.get('最高', row.get('high', None))),
                                    'low': self._safe_float(row.get('最低', row.get('low', None))),
                                    'volume': self._safe_float(row.get('成交量', row.get('volume', row.get('vol', 0)))),
                                    'amount': self._safe_float(row.get('成交额', row.get('amount', 0))),
                                }
                                collected_data.append(data)
                                
                            except Exception as e:
                                self.logger.warning(f'处理指数时出错: {str(e)}')
                                continue
                    
                        if not collected_data:
                            raise Exception('未能从 stock_hk_index_spot_sina 获取任何指数数据')
                        
                        self.logger.info(f'成功从 stock_hk_index_spot_sina 获取 {len(collected_data)} 条港股指数数据')
                    else:
                        raise Exception('stock_hk_index_spot_sina 返回空数据')
                        
                except Exception as e2:
                    self.logger.error(f'stock_hk_index_spot_sina 接口调用失败: {str(e2)}')
                    raise Exception(f'港股指数数据获取失败: stock_hk_index_spot_em错误={str(e1)}, stock_hk_index_spot_sina错误={str(e2)}')
            
            # 如果成功获取数据，写入数据库
            if collected_data and basic_info_data:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                trade_date = datetime.now().strftime('%Y-%m-%d')
                
                basic_info_count = 0
                realtime_count = 0
                
                # 批量处理，减少事务次数
                try:
                    # 1. 写入或更新基础信息表
                    for info in basic_info_data:
                        session.execute(text('''
                            INSERT INTO hk_index_basic_info (code, name, english_name, created_at, updated_at)
                            VALUES (:code, :name, :english_name, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ON CONFLICT (code) DO UPDATE SET
                                name = EXCLUDED.name,
                                english_name = EXCLUDED.english_name,
                                updated_at = CURRENT_TIMESTAMP
                        '''), {
                            'code': info['code'],
                            'name': info['name'],
                            'english_name': info['english_name']
                        })
                        basic_info_count += 1
                    
                    # 2. 写入或更新实时行情表（按日期）
                    for data in collected_data:
                        session.execute(text('''
                            INSERT INTO hk_index_realtime_quotes (
                                code, trade_date, name, price, change, pct_chg, open, pre_close, 
                                high, low, volume, amount, update_time, collect_time
                            ) VALUES (
                                :code, :trade_date, :name, :price, :change, :pct_chg, :open, :pre_close,
                                :high, :low, :volume, :amount, :update_time, :collect_time
                            )
                            ON CONFLICT (code, trade_date) DO UPDATE SET
                                name = EXCLUDED.name,
                                price = EXCLUDED.price,
                                change = EXCLUDED.change,
                                pct_chg = EXCLUDED.pct_chg,
                                open = EXCLUDED.open,
                                pre_close = EXCLUDED.pre_close,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                volume = EXCLUDED.volume,
                                amount = EXCLUDED.amount,
                                update_time = EXCLUDED.update_time,
                                collect_time = EXCLUDED.collect_time
                        '''), {
                            'code': data['code'],
                            'trade_date': trade_date,
                            'name': data['name'],
                            'price': data['price'],
                            'change': data['change'],
                            'pct_chg': data['pct_chg'],
                            'open': data['open'],
                            'pre_close': data['pre_close'],
                            'high': data['high'],
                            'low': data['low'],
                            'volume': data['volume'],
                            'amount': data['amount'],
                            'update_time': current_time,
                            'collect_time': current_time
                        })
                        realtime_count += 1
                    
                    # 3. 记录操作日志
                    session.execute(text('''
                        INSERT INTO hk_index_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                        VALUES (
                            :operation_type, :operation_desc, :affected_rows, :status, :error_message, CURRENT_TIMESTAMP
                        )
                    '''), {
                        'operation_type': 'hk_index_realtime_quote_collect',
                        'operation_desc': f'采集并更新港股指数数据：基础信息{basic_info_count}条，实时行情{realtime_count}条',
                        'affected_rows': basic_info_count + realtime_count,
                        'status': 'success',
                        'error_message': None
                    })
                    
                    session.commit()
                    self.logger.info(f"港股指数数据采集并入库完成：基础信息{basic_info_count}条，实时行情{realtime_count}条")
                    return collected_data
                    
                except Exception as db_error:
                    session.rollback()
                    raise Exception(f"数据库写入失败: {str(db_error)}")
            else:
                raise Exception('未能获取任何港股指数数据')
                
        except Exception as e:
            error_msg = str(e)
            self.logger.error("采集或入库时出错: %s", error_msg, exc_info=True)
            
            # 记录错误日志
            try:
                if session is not None:
                    session.rollback()
                    session.execute(text('''
                        INSERT INTO hk_index_collect_operation_logs 
                        (operation_type, operation_desc, affected_rows, status, error_message, created_at)
                        VALUES (
                            :operation_type, :operation_desc, :affected_rows, :status, :error_message, CURRENT_TIMESTAMP
                        )
                    '''), {
                        'operation_type': 'hk_index_realtime_quote_collect',
                        'operation_desc': '采集港股指数实时行情数据失败',
                        'affected_rows': 0,
                        'status': 'error',
                        'error_message': error_msg[:500]  # 限制错误消息长度
                    })
                    session.commit()
            except Exception as log_error:
                self.logger.error(f"记录错误日志失败: {log_error}")
            finally:
                if session is not None:
                    session.close()
            return None

    def _safe_float(self, value):
        """安全地将值转换为浮点数"""
        try:
            if pd.isna(value) or value in [None, '', '-']:
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

if __name__ == '__main__':
    # 测试采集器
    logging.basicConfig(level=logging.INFO)
    collector = HKIndexRealtimeCollector()
    result = collector.collect_realtime_quotes()
    if result:
        print(f"成功采集 {len(result)} 条港股指数数据")
        for item in result:
            print(f"{item['name']}: {item['price']} ({item['pct_chg']}%)")
    else:
        print("采集失败")
