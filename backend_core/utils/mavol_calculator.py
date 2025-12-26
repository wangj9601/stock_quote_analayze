"""
MAVOL成交量移动平均线指标计算工具类
支持MAVOL5, MAVOL10, MAVOL20, MAVOL30, MAVOL60, MAVOL120, MAVOL200
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MAVOLCalculator:
    """MAVOL成交量移动平均线指标计算器"""
    
    @staticmethod
    def calculate_mavol_for_dataframe(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 30, 60, 120, 200]) -> pd.DataFrame:
        """
        为DataFrame计算MAVOL指标。
        Args:
            df: 包含'volume'列的DataFrame，日期应已排序。
            periods: MAVOL周期列表，默认[5, 10, 20, 30, 60, 120, 200]
        Returns:
            DataFrame: 包含'mavol5', 'mavol10', 'mavol20', 'mavol30', 'mavol60', 'mavol120', 'mavol200'列的原始DataFrame。
        """
        if 'volume' not in df.columns:
            raise ValueError("DataFrame必须包含'volume'列")
        
        df = df.copy()
        
        # 计算各个周期的MAVOL
        for period in periods:
            col_name = f'mavol{period}'
            df[col_name] = df['volume'].rolling(window=period, min_periods=1).mean()
        
        return df.round(2)  # 成交量保留2位小数即可
    
    @staticmethod
    def calculate_mavol_for_list(volumes: List[float], periods: List[int] = [5, 10, 20, 30, 60, 120, 200]) -> Dict[str, Optional[float]]:
        """
        为成交量列表计算MAVOL指标（返回最后一个值）。
        Args:
            volumes: 成交量列表（按日期升序排列）
            periods: MAVOL周期列表
        Returns:
            包含各个周期MAVOL值的字典
        """
        if not volumes:
            return {f'mavol{period}': None for period in periods}
        
        try:
            volume_series = pd.Series(volumes)
            result = {}
            
            for period in periods:
                ma_value = volume_series.rolling(window=period, min_periods=1).mean().iloc[-1]
                result[f'mavol{period}'] = round(float(ma_value), 2) if not pd.isna(ma_value) else None
            
            return result
        except Exception as e:
            logger.error(f"计算MAVOL指标时出错: {str(e)}")
            return {f'mavol{period}': None for period in periods}
    
    @staticmethod
    def calculate_mavol_batch(volumes: List[float], periods: List[int] = [5, 10, 20, 30, 60, 120, 200]) -> List[Dict[str, Optional[float]]]:
        """
        批量计算MAVOL指标（返回所有日期的MAVOL值）。
        Args:
            volumes: 成交量列表（按日期升序排列）
            periods: MAVOL周期列表
        Returns:
            MAVOL指标列表，每个元素包含各个周期的MAVOL值
        """
        if not volumes:
            return []
        
        try:
            volume_series = pd.Series(volumes)
            results = []
            
            # 预计算所有MA值以提高效率
            ma_dict = {}
            for period in periods:
                ma_dict[f'mavol{period}'] = volume_series.rolling(window=period, min_periods=1).mean()
            
            for i in range(len(volumes)):
                result_item = {}
                for period in periods:
                    ma_value = ma_dict[f'mavol{period}'].iloc[i]
                    result_item[f'mavol{period}'] = round(float(ma_value), 2) if not pd.isna(ma_value) else None
                results.append(result_item)
            
            return results
        except Exception as e:
            logger.error(f"批量计算MAVOL指标时出错: {str(e)}")
            return []
