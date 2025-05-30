"""
AKShare数据采集器基类
提供基础的数据采集功能和通用方法
"""

import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any, Callable, TypeVar, Any, List, Union
from datetime import datetime, timedelta
import logging
import time
from functools import wraps
import os
from pathlib import Path
import json

# 直接导入config模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import DATA_COLLECTORS

T = TypeVar('T')

class AKShareCollector:
    """AKShare数据采集器基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        self.config = config or DATA_COLLECTORS.get('akshare', {})
        self._setup_logging()
        
    def _setup_logging(self):
        """设置日志"""
        log_dir = Path(self.config.get('log_dir', 'logs'))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f'akshare_{self.__class__.__name__.lower()}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _retry_on_failure(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        失败重试装饰器
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            T: 函数返回值
            
        Raises:
            Exception: 重试次数用完后仍然失败
        """
        max_retries = self.config.get('max_retries', 3)
        retry_delay = self.config.get('retry_delay', 5)
        
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if i == max_retries - 1:
                    self.logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
                    raise
                self.logger.warning(f"第 {i+1} 次重试失败: {str(e)}")
                time.sleep(retry_delay)
                
        raise Exception("重试次数用尽")
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取股票列表
        
        Returns:
            DataFrame: 包含股票代码和名称的DataFrame
        """
        try:
            self.logger.info("开始获取股票列表...")
            df = self._retry_on_failure(ak.stock_zh_a_spot_em)
            self.logger.info(f"成功获取{len(df)}只股票信息")
            return df
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {str(e)}")
            raise
    
    def get_realtime_quotes(self, stock_codes: Optional[List[str]] = None) -> pd.DataFrame:
        """
        获取实时行情数据
        
        Args:
            stock_codes: 股票代码列表，如果为None则获取所有股票
            
        Returns:
            DataFrame: 实时行情数据
        """
        try:
            if stock_codes:
                self.logger.info(f"开始获取{len(stock_codes)}只股票的实时行情...")
                df = pd.concat([
                    self._retry_on_failure(ak.stock_zh_a_spot_em, symbol=code)
                    for code in stock_codes
                ])
            else:
                self.logger.info("开始获取所有股票的实时行情...")
                df = self._retry_on_failure(ak.stock_zh_a_spot_em)
            
            self.logger.info(f"成功获取{len(df)}条实时行情数据")
            return df
        except Exception as e:
            self.logger.error(f"获取实时行情失败: {str(e)}")
            raise
    
    def get_historical_quotes(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily"
    ) -> pd.DataFrame:
        """
        获取历史行情数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期，格式：YYYYMMDD
            end_date: 结束日期，格式：YYYYMMDD
            period: 周期，可选：daily, weekly, monthly
            
        Returns:
            DataFrame: 历史行情数据
        """
        try:
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
                
            self.logger.info(f"开始获取{stock_code}的历史行情数据...")
            df = self._retry_on_failure(
                ak.stock_zh_a_hist,
                symbol=stock_code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            
            self.logger.info(f"成功获取{len(df)}条历史行情数据")
            return df
        except Exception as e:
            self.logger.error(f"获取历史行情失败: {str(e)}")
            raise
    
    def get_fundamental_data(self, stock_code: str) -> Dict[str, Any]:
        """
        获取基本面数据
        
        Args:
            stock_code: 股票代码
            
        Returns:
            Dict: 包含基本面数据的字典
        """
        try:
            self.logger.info(f"开始获取{stock_code}的基本面数据...")
            
            # 获取财务指标
            financial = self._retry_on_failure(
                ak.stock_financial_analysis_indicator,
                symbol=stock_code
            )
            
            # 获取公司概况
            profile = self._retry_on_failure(
                ak.stock_individual_info_em,
                symbol=stock_code
            )
            
            # 获取估值指标
            valuation = self._retry_on_failure(
                ak.stock_a_lg_indicator,
                symbol=stock_code
            )
            
            data = {
                'financial': financial.to_dict('records') if not financial.empty else [],
                'profile': profile.to_dict('records') if not profile.empty else [],
                'valuation': valuation.to_dict('records') if not valuation.empty else []
            }
            
            self.logger.info(f"成功获取{stock_code}的基本面数据")
            return data
        except Exception as e:
            self.logger.error(f"获取基本面数据失败: {str(e)}")
            raise
    
    def save_data(self, data: Union[pd.DataFrame, Dict], filepath: Union[str, Path]):
        """
        保存数据到文件
        
        Args:
            data: 要保存的数据
            filepath: 文件路径
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            if isinstance(data, pd.DataFrame):
                data.to_csv(filepath, index=False, encoding='utf-8')
            else:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
            self.logger.info(f"数据已保存到: {filepath}")
        except Exception as e:
            self.logger.error(f"保存数据失败: {str(e)}")
            raise 