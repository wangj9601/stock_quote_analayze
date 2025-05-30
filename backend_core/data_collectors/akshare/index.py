"""
指数行情数据采集器
负责采集股票指数行情数据
"""

import akshare as ak
import pandas as pd
from typing import Optional, Dict, Any, List
import logging

# 直接导入base模块
from base import AKShareCollector

class IndexQuoteCollector(AKShareCollector):
    """指数行情数据采集器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化采集器
        
        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        super().__init__(config)
        
    def get_index_list(self) -> pd.DataFrame:
        """
        获取指数列表
        
        Returns:
            pd.DataFrame: 包含指数代码和名称的DataFrame
        """
        try:
            self.logger.info("开始获取指数列表...")
            df = self._retry_on_failure(ak.stock_zh_index_spot_sina)
            self.logger.info(f"成功获取{len(df)}个指数信息")
            return df
        except Exception as e:
            self.logger.error(f"获取指数列表失败: {str(e)}")
            raise
            
    def get_index_quotes(self, index_codes: Optional[List[str]] = None) -> pd.DataFrame:
        """
        获取指数行情数据
        
        Args:
            index_codes: 指数代码列表，如果为None则获取所有指数
            
        Returns:
            pd.DataFrame: 指数行情数据
        """
        try:
            if index_codes:
                self.logger.info(f"开始获取{len(index_codes)}个指数的行情数据...")
                df = self._retry_on_failure(ak.stock_zh_index_spot_sina)
                df = df[df['代码'].isin(index_codes)]
            else:
                self.logger.info("开始获取所有指数的行情数据...")
                df = self._retry_on_failure(ak.stock_zh_index_spot_sina)
                
            self.logger.info(f"成功获取{len(df)}条指数行情数据")
            return df
        except Exception as e:
            self.logger.error(f"获取指数行情数据失败: {str(e)}")
            raise
            
    def get_index_components(self, index_code: str) -> pd.DataFrame:
        """
        获取指数成分股
        
        Args:
            index_code: 指数代码
            
        Returns:
            pd.DataFrame: 指数成分股数据
        """
        try:
            self.logger.info(f"开始获取指数{index_code}的成分股...")
            df = self._retry_on_failure(ak.stock_zh_index_cons, symbol=index_code)
            self.logger.info(f"成功获取{len(df)}只成分股")
            return df
        except Exception as e:
            self.logger.error(f"获取指数成分股失败: {str(e)}")
            raise 