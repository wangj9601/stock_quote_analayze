"""
KDJ指标计算工具类
标准参数：N=9, M1=3, M2=3
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class KDJCalculator:
    """KDJ指标计算器"""
    
    def __init__(self, n: int = 9, m1: int = 3, m2: int = 3):
        """
        初始化KDJ计算器
        
        Args:
            n: 计算RSV的周期，默认9
            m1: K值平滑因子，默认3
            m2: D值平滑因子，默认3
        """
        self.n = n
        self.m1 = m1
        self.m2 = m2
        self.min_periods = n  # 至少需要N天数据
    
    def calculate_kdj_batch(self, closes: List[float], highs: List[float], lows: List[float]) -> List[Dict[str, float]]:
        """
        批量计算KDJ指标（返回所有日期的KDJ值）
        
        Args:
            closes: 收盘价列表（按日期升序排列）
            highs: 最高价列表
            lows: 最低价列表
            
        Returns:
            KDJ指标列表，每个元素包含K、D、J、RSV
        """
        if len(closes) < self.min_periods or len(closes) != len(highs) or len(closes) != len(lows):
            return []
        
        try:
            # 转换为pandas Series
            close_series = pd.Series(closes)
            high_series = pd.Series(highs)
            low_series = pd.Series(lows)
            
            # 计算RSV
            # RSV = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
            lowest_low = low_series.rolling(window=self.n, min_periods=0).min()
            highest_high = high_series.rolling(window=self.n, min_periods=0).max()
            
            # 处理分母为0的情况
            denominator = highest_high - lowest_low
            denominator = denominator.replace(0, np.nan) # 避免除以0
            
            rsv = (close_series - lowest_low) / denominator * 100
            rsv = rsv.fillna(0) # 填充为0或其他合适的值
            
            # 计算K, D, J
            # K = 2/3 * Prev K + 1/3 * RSV
            # D = 2/3 * Prev D + 1/3 * K
            # J = 3 * K - 2 * D
            
            k_values = []
            d_values = []
            j_values = []
            
            # 初始K, D值为50
            k = 50.0
            d = 50.0
            
            for r in rsv:
                k = (self.m1 - 1) / self.m1 * k + 1 / self.m1 * r
                d = (self.m2 - 1) / self.m2 * d + 1 / self.m2 * k
                j = 3 * k - 2 * d
                
                k_values.append(k)
                d_values.append(d)
                j_values.append(j)
            
            # 构建结果列表
            results = []
            for i in range(len(closes)):
                # 如果数据点不足周期N，虽然rolling设置了min_periods=0能算出RSV，但通常认为初期数据不稳定
                # 这里我们直接返回计算结果，由使用者决定是否展示
                results.append({
                    'k': round(float(k_values[i]), 4),
                    'd': round(float(d_values[i]), 4),
                    'j': round(float(j_values[i]), 4),
                    'rsv': round(float(rsv.iloc[i]), 4)
                })
            
            return results
        except Exception as e:
            logger.error(f"批量计算KDJ指标时出错: {str(e)}")
            return []
