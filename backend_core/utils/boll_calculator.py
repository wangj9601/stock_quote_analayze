"""
BOLL布林带指标计算工具类
标准参数设定为 (20, 2)，即 20 日均线和 2 倍标准差。
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

class BOLLCalculator:
    """BOLL指标计算器"""
    
    def __init__(self, window: int = 20, k: int = 2):
        """
        初始化计算器
        Args:
            window: 移动平均线周期，默认20
            k: 标准差倍数，默认2
        """
        self.window = window
        self.k = k

    def calculate_boll_for_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        为DataFrame计算BOLL指标。
        Args:
            df: 包含'close'列的DataFrame，日期应已排序。
        Returns:
            DataFrame: 包含'boll_mid', 'boll_upper', 'boll_lower'列的原始DataFrame。
        """
        if 'close' not in df.columns:
            raise ValueError("DataFrame必须包含'close'列")
        
        df = df.copy()
        
        # 计算中轨 (20日SMA)
        df['boll_mid'] = df['close'].rolling(window=self.window, min_periods=self.window).mean()
        
        # 计算标准差
        df['std'] = df['close'].rolling(window=self.window, min_periods=self.window).std()
        
        # 计算上轨和下轨
        df['boll_upper'] = df['boll_mid'] + (self.k * df['std'])
        df['boll_lower'] = df['boll_mid'] - (self.k * df['std'])
        
        # 删除临时列
        df.drop(columns=['std'], inplace=True)
        
        return df.round(4)

    def calculate_boll_batch(self, closes: List[float]) -> List[Dict[str, Optional[float]]]:
        """
        批量计算BOLL指标（返回所有日期的BOLL值）。
        Args:
            closes: 收盘价列表（按日期升序排列）
        Returns:
            BOLL指标列表，每个元素包含 mid, upper, lower
        """
        if not closes or len(closes) < self.window:
            return [{'mid': None, 'upper': None, 'lower': None} for _ in range(len(closes))]
        
        try:
            close_series = pd.Series(closes)
            mid = close_series.rolling(window=self.window, min_periods=self.window).mean()
            std = close_series.rolling(window=self.window, min_periods=self.window).std()
            
            upper = mid + (self.k * std)
            lower = mid - (self.k * std)
            
            results = []
            for m, u, l in zip(mid, upper, lower):
                results.append({
                    'mid': round(float(m), 4) if not pd.isna(m) else None,
                    'upper': round(float(u), 4) if not pd.isna(u) else None,
                    'lower': round(float(l), 4) if not pd.isna(l) else None
                })
            return results
        except Exception as e:
            logger.error(f"批量计算BOLL指标时出错: {str(e)}")
            return [{'mid': None, 'upper': None, 'lower': None} for _ in range(len(closes))]
