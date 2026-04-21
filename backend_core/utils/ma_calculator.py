"""
MA移动平均线指标计算工具类
支持MA5, MA10, MA20, MA30, MA60, MA120, MA200
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MACalculator:
    """MA移动平均线指标计算器"""
    
    @staticmethod
    def calculate_ma_for_dataframe(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 30, 60, 120, 200]) -> pd.DataFrame:
        """
        为DataFrame计算MA指标。
        Args:
            df: 包含'close'列的DataFrame，日期应已排序。
            periods: MA周期列表，默认[5, 10, 20, 30, 60, 120, 200]
        Returns:
            DataFrame: 包含'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120', 'ma200'列的原始DataFrame。
        """
        if 'close' not in df.columns:
            raise ValueError("DataFrame必须包含'close'列")
        
        df = df.copy()
        
        # 计算各个周期的MA
        for period in periods:
            col_name = f'ma{period}'
            df[col_name] = df['close'].rolling(window=period, min_periods=period).mean()
        
        # 仅对数值列做 round，避免 datetime 列触发无效告警
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df.loc[:, numeric_cols] = df.loc[:, numeric_cols].round(4)
        return df
    
    @staticmethod
    def calculate_ma_for_list(closes: List[float], periods: List[int] = [5, 10, 20, 30, 60, 120, 200]) -> Dict[str, Optional[float]]:
        """
        为收盘价列表计算MA指标（返回最后一个值）。
        Args:
            closes: 收盘价列表（按日期升序排列）
            periods: MA周期列表
        Returns:
            包含各个周期MA值的字典
        """
        if not closes:
            return {f'ma{period}': None for period in periods}
        
        try:
            close_series = pd.Series(closes)
            result = {}
            
            for period in periods:
                ma_value = close_series.rolling(window=period, min_periods=period).mean().iloc[-1]
                result[f'ma{period}'] = round(float(ma_value), 4) if not pd.isna(ma_value) else None
            
            return result
        except Exception as e:
            logger.error(f"计算MA指标时出错: {str(e)}")
            return {f'ma{period}': None for period in periods}
    
    @staticmethod
    def calculate_ma_batch(closes: List[float], periods: List[int] = [5, 10, 20, 30, 60, 120, 200]) -> List[Dict[str, Optional[float]]]:
        """
        批量计算MA指标（返回所有日期的MA值）。
        Args:
            closes: 收盘价列表（按日期升序排列）
            periods: MA周期列表
        Returns:
            MA指标列表，每个元素包含各个周期的MA值
        """
        if not closes:
            return []
        
        try:
            close_series = pd.Series(closes)
            results = []
            
            for i in range(len(closes)):
                result_item = {}
                for period in periods:
                    # 使用rolling计算，min_periods=1确保即使数据不足也能计算
                    ma_value = close_series.iloc[:i+1].rolling(window=period, min_periods=period).mean().iloc[-1]
                    result_item[f'ma{period}'] = round(float(ma_value), 4) if not pd.isna(ma_value) else None
                results.append(result_item)
            
            return results
        except Exception as e:
            logger.error(f"批量计算MA指标时出错: {str(e)}")
            return []

