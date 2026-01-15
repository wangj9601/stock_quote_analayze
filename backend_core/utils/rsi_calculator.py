"""
RSI指标计算工具类
标准参数：N=6, 12, 24
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class RSICalculator:
    """RSI指标计算器"""
    
    def __init__(self, periods: List[int] = [6, 12, 24]):
        """
        初始化RSI计算器
        
        Args:
            periods: RSI计算周期列表，默认[6, 12, 24]
        """
        self.periods = periods
    
    def calculate_rsi_batch(self, closes: List[float]) -> List[Dict[str, float]]:
        """
        批量计算RSI指标（返回所有日期的RSI值）
        
        Args:
            closes: 收盘价列表（按日期升序排列）
            
        Returns:
            RSI指标列表，每个元素包含rsi6, rsi12, rsi24等
        """
        if not closes or len(closes) < 2:
            return []
        
        try:
            # 转换为pandas Series
            close_series = pd.Series(closes)
            
            # 计算价格变动
            delta = close_series.diff()
            
            # 分离上涨和下跌幅度
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            
            rsi_results = {}
            
            for period in self.periods:
                # 使用Wilder's Smoothing (alpha = 1/N)
                # pandas ewm adjust=False, alpha=1/period 对应 Wilder's MA
                avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
                
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                
                # 处理由于avg_loss为0导致的NaN或Inf
                rsi = rsi.fillna(100) # 如果没有下跌，RSI为100
                
                # 前period-1个数据可能不准确，通常视为NaN或保留
                # 但pandas ewm会从头开始计算，只是初期权重不同。为了保持数据完整性，保留所有值
                
                rsi_results[period] = rsi
            
            # 构建结果列表
            results = []
            max_len = len(closes)
            
            for i in range(max_len):
                item = {}
                for period in self.periods:
                    key = f'rsi{period}'
                    val = rsi_results[period].iloc[i]
                    # 确保在计算初期（数据不足周期）返回 None
                    if i < period or pd.isna(val) or np.isinf(val):
                        item[key] = None
                    else:
                        item[key] = round(float(val), 4)
                results.append(item)
            
            return results
        except Exception as e:
            logger.error(f"批量计算RSI指标时出错: {str(e)}")
            return []
