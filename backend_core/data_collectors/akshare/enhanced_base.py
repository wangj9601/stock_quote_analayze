"""
增强的AKShare数据采集器基类
解决SSL连接问题、IP封禁问题，支持代理轮换、User-Agent轮换等功能
"""

import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any, Callable, TypeVar, Any, List, Union
from datetime import datetime, timedelta
import logging
import time
import random
import requests
from functools import wraps
import os
from pathlib import Path
import json
import ssl
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from backend_core.config.config import DATA_COLLECTORS
from backend_core.logging_utils import get_logs_dir

T = TypeVar('T')

class EnhancedAKShareCollector:
    """增强的AKShare数据采集器基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        self.config = config or DATA_COLLECTORS.get('akshare', {})
        self._setup_logging()
        self._setup_session()
        self._setup_proxy_pool()
        self._setup_user_agents()
        
    def _setup_logging(self):
        """设置日志（统一写入项目根 logs/）"""
        log_dir = Path(self.config.get('log_dir') or get_logs_dir())
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f'enhanced_akshare_{self.__class__.__name__.lower()}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _setup_session(self):
        """设置请求会话"""
        self.session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.config.get('max_retries', 3),
            backoff_factor=self.config.get('retry_delay', 5),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # 配置适配器
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 配置SSL
        self.session.verify = True
        # 创建自定义SSL上下文，允许更多连接选项
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 设置超时
        self.session.timeout = self.config.get('timeout', 30)
        
    def _setup_proxy_pool(self):
        """设置代理池"""
        self.proxy_pool = self.config.get('proxy_pool', [])
        self.current_proxy_index = 0
        
        # 如果没有配置代理，尝试使用一些免费的代理服务
        if not self.proxy_pool:
            self.proxy_pool = [
                # 可以在这里添加一些免费代理
                # {'http': 'http://proxy1:port', 'https': 'https://proxy1:port'},
                # {'http': 'http://proxy2:port', 'https': 'https://proxy2:port'},
            ]
            
    def _setup_user_agents(self):
        """设置User-Agent池"""
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        self.current_ua_index = 0
        
    def _get_next_proxy(self) -> Optional[Dict[str, str]]:
        """获取下一个代理"""
        if not self.proxy_pool:
            return None
            
        proxy = self.proxy_pool[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_pool)
        return proxy
        
    def _get_next_user_agent(self) -> str:
        """获取下一个User-Agent"""
        ua = self.user_agents[self.current_ua_index]
        self.current_ua_index = (self.current_ua_index + 1) % len(self.user_agents)
        return ua
        
    def _random_delay(self):
        """随机延迟"""
        delay = random.uniform(1, 3)  # 1-3秒随机延迟
        time.sleep(delay)
        
    def _retry_on_failure(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        增强的失败重试装饰器
        
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
                # 随机延迟
                if i > 0:
                    self._random_delay()
                    
                # 设置User-Agent
                if hasattr(self.session, 'headers'):
                    self.session.headers.update({'User-Agent': self._get_next_user_agent()})
                    
                # 设置代理（如果有）
                proxy = self._get_next_proxy()
                if proxy:
                    self.session.proxies.update(proxy)
                    
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if i == max_retries - 1:
                    self.logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
                    raise
                    
                # 检查是否是SSL或连接错误
                if any(keyword in error_str for keyword in ['ssl', 'connection', 'timeout', 'eof']):
                    self.logger.warning(f"第 {i+1} 次重试失败 (SSL/连接错误): {str(e)}")
                    # SSL错误时使用更长的延迟
                    time.sleep(retry_delay * 2)
                else:
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
                # stock_zh_a_spot_em 不支持单个股票代码，需要获取全部然后过滤
                df = self._retry_on_failure(ak.stock_zh_a_spot_em)
                # 过滤出指定的股票代码
                df = df[df['代码'].isin(stock_codes)]
            else:
                self.logger.info("开始获取所有股票的实时行情...")
                df = self._retry_on_failure(ak.stock_zh_a_spot_em)
            
            self.logger.info(f"成功获取{len(df)}条实时行情数据")
            return df
        except Exception as e:
            self.logger.error(f"获取实时行情失败: {str(e)}")
            raise
    
    def get_realtime_quotes_with_fallback(self) -> pd.DataFrame:
        """
        获取实时行情数据，支持多种数据源的回退机制
        
        Returns:
            DataFrame: 实时行情数据
        """
        # 定义多个数据源，按优先级排序
        data_sources = [
            ('stock_zh_a_spot_em', ak.stock_zh_a_spot_em, []),
            ('stock_sh_a_spot_em', ak.stock_sh_a_spot_em, []),
            ('stock_sz_a_spot_em', ak.stock_sz_a_spot_em, []),
            ('stock_bj_a_spot_em', ak.stock_bj_a_spot_em, []),
        ]
        
        dfs = []
        successful_sources = []
        
        for source_name, source_func, source_args in data_sources:
            try:
                self.logger.info(f"尝试使用数据源: {source_name}")
                df = self._retry_on_failure(source_func, *source_args)
                if df is not None and hasattr(df, 'empty') and not df.empty:
                    dfs.append(df)
                    successful_sources.append(source_name)
                    self.logger.info(f"成功从 {source_name} 获取 {len(df)} 条数据")
                else:
                    self.logger.warning(f"数据源 {source_name} 返回空数据")
            except Exception as e:
                self.logger.warning(f"数据源 {source_name} 失败: {str(e)}")
                continue
                
        if dfs:
            # 合并所有成功的数据源
            combined_df = pd.concat(dfs, ignore_index=True)
            self.logger.info(f"成功从 {len(successful_sources)} 个数据源获取数据，总计 {len(combined_df)} 条记录")
            return combined_df
        else:
            raise Exception("所有数据源都失败了")
    
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
