"""
MACD指标计算工具类
标准参数：快线EMA12，慢线EMA26，信号线EMA9
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MACDCalculator:
    """MACD指标计算器"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        初始化MACD计算器
        
        Args:
            fast_period: 快线EMA周期，默认12
            slow_period: 慢线EMA周期，默认26
            signal_period: 信号线EMA周期，默认9
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.min_periods = slow_period  # 至少需要慢线周期的数据
    
    def calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """
        计算指数移动平均线（EMA）
        
        Args:
            prices: 价格序列
            period: EMA周期
            
        Returns:
            EMA序列
        """
        return prices.ewm(span=period, adjust=False).mean()
    
    def calculate_macd(self, closes: List[float]) -> Optional[Dict[str, float]]:
        """
        计算MACD指标
        
        Args:
            closes: 收盘价列表（按日期升序排列）
            
        Returns:
            包含DIF、DEA、MACD、EMA12、EMA26的字典，如果数据不足返回None
        """
        if len(closes) < self.min_periods:
            logger.warning(f"数据不足，需要至少{self.min_periods}天数据，当前只有{len(closes)}天")
            return None
        
        try:
            # 转换为pandas Series
            close_series = pd.Series(closes)
            
            # 计算EMA12和EMA26
            ema12 = self.calculate_ema(close_series, self.fast_period)
            ema26 = self.calculate_ema(close_series, self.slow_period)
            
            # 计算DIF（快线 - 慢线）
            dif = ema12 - ema26
            
            # 计算DEA（DIF的9日EMA）
            dea = self.calculate_ema(dif, self.signal_period)
            
            # 计算MACD柱状图值（DIF - DEA，通常乘以2）
            macd = (dif - dea) * 2
            
            # 返回最后一个值
            return {
                'dif': round(float(dif.iloc[-1]), 4),
                'dea': round(float(dea.iloc[-1]), 4),
                'macd': round(float(macd.iloc[-1]), 4),
                'ema12': round(float(ema12.iloc[-1]), 4),
                'ema26': round(float(ema26.iloc[-1]), 4)
            }
        except Exception as e:
            logger.error(f"计算MACD指标时出错: {str(e)}")
            return None
    
    def calculate_macd_batch(self, closes: List[float]) -> List[Dict[str, float]]:
        """
        批量计算MACD指标（返回所有日期的MACD值）
        
        Args:
            closes: 收盘价列表（按日期升序排列）
            
        Returns:
            MACD指标列表，每个元素包含DIF、DEA、MACD、EMA12、EMA26
        """
        if len(closes) < self.min_periods:
            return []
        
        try:
            # 转换为pandas Series
            close_series = pd.Series(closes)
            
            # 计算EMA12和EMA26
            ema12 = self.calculate_ema(close_series, self.fast_period)
            ema26 = self.calculate_ema(close_series, self.slow_period)
            
            # 计算DIF（快线 - 慢线）
            dif = ema12 - ema26
            
            # 计算DEA（DIF的9日EMA）
            dea = self.calculate_ema(dif, self.signal_period)
            
            # 计算MACD柱状图值（DIF - DEA，通常乘以2）
            macd = (dif - dea) * 2
            
            # 构建结果列表
            results = []
            for i in range(len(closes)):
                # 前slow_period-1天的数据不足，返回None值
                if i < self.slow_period - 1:
                    results.append({
                        'dif': None,
                        'dea': None,
                        'macd': None,
                        'ema12': None,
                        'ema26': None
                    })
                else:
                    results.append({
                        'dif': round(float(dif.iloc[i]), 4) if not pd.isna(dif.iloc[i]) else None,
                        'dea': round(float(dea.iloc[i]), 4) if not pd.isna(dea.iloc[i]) else None,
                        'macd': round(float(macd.iloc[i]), 4) if not pd.isna(macd.iloc[i]) else None,
                        'ema12': round(float(ema12.iloc[i]), 4) if not pd.isna(ema12.iloc[i]) else None,
                        'ema26': round(float(ema26.iloc[i]), 4) if not pd.isna(ema26.iloc[i]) else None
                    })
            
            return results
        except Exception as e:
            logger.error(f"批量计算MACD指标时出错: {str(e)}")
            return []

