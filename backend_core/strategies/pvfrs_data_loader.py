"""
PVFRS策略数据加载器
从数据库加载PVFRS指标数据和价格数据进行回测
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from sqlalchemy import cast, Date as SA_Date

# 导入模型
from backend_api.models import (
    MeanFrequencyResonanceIndicators, HistoricalQuotes, HistoricalQuotesHK
)
from backend_api.database import get_db

logger = logging.getLogger(__name__)

class PVFRSDataLoader:
    """PVFRS策略数据加载器"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def load_stock_data(
        self, 
        code: str, 
        market_type: str, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """
        加载指定股票的PVFRS指标数据和价格数据
        
        Args:
            code: 股票代码
            market_type: 市场类型 ('CN' 或 'HK')
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            包含PVFRS指标和价格数据的DataFrame
        """
        logger.info(f"加载股票数据: {code} ({market_type}), {start_date} 到 {end_date}")
        
        # 加载PVFRS指标数据
        pvfrs_data = self._load_pvfrs_data(code, market_type, start_date, end_date)
        
        # 加载价格数据
        price_data = self._load_price_data(code, market_type, start_date, end_date)

        # 统一日期格式，避免 date 字段格式不一致导致无法合并
        if not pvfrs_data.empty and 'date' in pvfrs_data.columns:
            pvfrs_data['date'] = pvfrs_data['date'].astype(str).str[:10]
        if not price_data.empty and 'date' in price_data.columns:
            price_data['date'] = price_data['date'].astype(str).str[:10]
        
        # 合并数据
        merged_data = self._merge_data(pvfrs_data, price_data)
        
        logger.info(f"成功加载 {len(merged_data)} 条数据记录")
        
        return merged_data
    
    def _load_pvfrs_data(
        self, 
        code: str, 
        market_type: str, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """加载PVFRS指标数据"""
        try:
            query = self.db.query(MeanFrequencyResonanceIndicators).filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type,
                MeanFrequencyResonanceIndicators.date >= start_date,
                MeanFrequencyResonanceIndicators.date <= end_date
            ).order_by(asc(MeanFrequencyResonanceIndicators.date))
            
            results = query.all()
            
            if not results:
                logger.warning(f"未找到股票 {code} 的PVFRS指标数据")
                return pd.DataFrame()
            
            # 转换为DataFrame
            data = []
            for item in results:
                data.append({
                    'date': str(item.date)[:10] if item.date is not None else None,
                    'macro_displacement_delta': item.macro_displacement_delta or 0,
                    'instant_deviation': item.instant_deviation or 0,
                    'rising_days_z': item.rising_days_z or 0,
                    'falling_days_f': item.falling_days_f or 0,
                    'efficiency_m20_minus_m': item.efficiency_m20_minus_m or 0,
                    'ma20_d': item.ma20_d or 0,
                    'mavol20_m': item.mavol20_m or 0,
                    'bias': item.bias or 0
                })
            
            return pd.DataFrame(data)
            
        except Exception as e:
            logger.error(f"加载PVFRS数据失败: {e}")
            return pd.DataFrame()
    
    def _load_price_data(
        self, 
        code: str, 
        market_type: str, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """加载价格数据"""
        try:
            if market_type == "CN":
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_col = cast(HistoricalQuotes.date, SA_Date)
                # A股数据
                query = self.db.query(HistoricalQuotes).filter(
                    HistoricalQuotes.code == code,
                    date_col >= start_dt,
                    date_col <= end_dt
                ).order_by(asc(date_col))
                
                results = query.all()
                
                if not results:
                    logger.warning(f"未找到股票 {code} 的A股价格数据")
                    return pd.DataFrame()
                
                # 转换为DataFrame
                data = []
                for item in results:
                    data.append({
                        'date': str(item.date)[:10] if item.date is not None else None,
                        'open': item.open or 0,
                        'high': item.high or 0,
                        'low': item.low or 0,
                        'close': item.close or 0,
                        'volume': item.volume or 0
                    })
                
            else:  # HK
                # 港股数据
                query = self.db.query(HistoricalQuotesHK).filter(
                    HistoricalQuotesHK.code == code,
                    HistoricalQuotesHK.date >= start_date,
                    HistoricalQuotesHK.date <= end_date
                ).order_by(asc(HistoricalQuotesHK.date))
                
                results = query.all()
                
                if not results:
                    logger.warning(f"未找到股票 {code} 的港股价格数据")
                    return pd.DataFrame()
                
                # 转换为DataFrame
                data = []
                for item in results:
                    data.append({
                        'date': item.date,
                        'open': item.open or 0,
                        'high': item.high or 0,
                        'low': item.low or 0,
                        'close': item.close or 0,
                        'volume': item.volume or 0
                    })
            
            return pd.DataFrame(data)
            
        except Exception as e:
            logger.error(f"加载价格数据失败: {e}")
            return pd.DataFrame()
    
    def _merge_data(self, pvfrs_data: pd.DataFrame, price_data: pd.DataFrame) -> pd.DataFrame:
        """合并PVFRS数据和价格数据"""
        if pvfrs_data.empty or price_data.empty:
            logger.warning("PVFRS数据或价格数据为空，无法合并")
            return pd.DataFrame()
        
        # 按日期合并
        merged = pd.merge(
            price_data, 
            pvfrs_data, 
            on='date', 
            how='inner'
        )
        
        # 按日期排序
        merged = merged.sort_values('date').reset_index(drop=True)
        
        # 检查数据完整性
        missing_data = merged.isnull().sum()
        if missing_data.sum() > 0:
            logger.warning(f"合并数据中存在缺失值: {missing_data[missing_data > 0].to_dict()}")
        
        return merged
    
    def get_available_stocks(self, market_type: str) -> List[str]:
        """获取指定市场中有PVFRS数据的股票列表"""
        try:
            query = self.db.query(MeanFrequencyResonanceIndicators.code).filter(
                MeanFrequencyResonanceIndicators.market_type == market_type
            ).distinct()
            
            results = query.all()
            return [item[0] for item in results]
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def get_data_range(self, code: str, market_type: str) -> Dict[str, str]:
        """获取指定股票的数据日期范围"""
        try:
            # 获取最早日期
            min_date_query = self.db.query(MeanFrequencyResonanceIndicators.date).filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type
            ).order_by(asc(MeanFrequencyResonanceIndicators.date)).first()
            
            # 获取最晚日期
            max_date_query = self.db.query(MeanFrequencyResonanceIndicators.date).filter(
                MeanFrequencyResonanceIndicators.code == code,
                MeanFrequencyResonanceIndicators.market_type == market_type
            ).order_by(desc(MeanFrequencyResonanceIndicators.date)).first()
            
            return {
                'start_date': min_date_query[0] if min_date_query else None,
                'end_date': max_date_query[0] if max_date_query else None
            }
            
        except Exception as e:
            logger.error(f"获取数据范围失败: {e}")
            return {'start_date': None, 'end_date': None}
    
    def validate_data_quality(self, data: pd.DataFrame) -> Dict[str, any]:
        """验证数据质量"""
        validation_result = {
            'total_records': len(data),
            'missing_values': {},
            'data_types': {},
            'date_range': {},
            'quality_score': 0
        }
        
        if data.empty:
            return validation_result
        
        # 检查缺失值
        validation_result['missing_values'] = data.isnull().sum().to_dict()
        
        # 检查数据类型
        validation_result['data_types'] = data.dtypes.astype(str).to_dict()
        
        # 检查日期范围
        if 'date' in data.columns:
            validation_result['date_range'] = {
                'start': data['date'].min(),
                'end': data['date'].max(),
                'trading_days': len(data)
            }
        
        # 计算质量分数
        total_cells = len(data) * len(data.columns)
        missing_cells = data.isnull().sum().sum()
        completeness = (total_cells - missing_cells) / total_cells if total_cells > 0 else 0
        
        validation_result['quality_score'] = completeness
        
        return validation_result

class PVFRSDataValidator:
    """PVFRS数据验证器"""
    
    @staticmethod
    def validate_pvfrs_data(data: pd.DataFrame) -> Dict[str, any]:
        """验证PVFRS数据的合理性"""
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'statistics': {}
        }
        
        if data.empty:
            validation_result['is_valid'] = False
            validation_result['errors'].append("数据为空")
            return validation_result
        
        # 检查必要字段
        required_fields = [
            'date', 'close', 'volume',
            'macro_displacement_delta', 'instant_deviation',
            'rising_days_z', 'falling_days_f',
            'efficiency_m20_minus_m', 'ma20_d', 'mavol20_m', 'bias'
        ]
        
        missing_fields = [field for field in required_fields if field not in data.columns]
        if missing_fields:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"缺少必要字段: {missing_fields}")
        
        # 检查数据合理性
        if 'close' in data.columns:
            if (data['close'] <= 0).any():
                validation_result['warnings'].append("存在非正价格")
        
        if 'volume' in data.columns:
            if (data['volume'] < 0).any():
                validation_result['warnings'].append("存在负成交量")
        
        if 'rising_days_z' in data.columns and 'falling_days_f' in data.columns:
            # 检查Z+F是否合理
            z_plus_f = data['rising_days_z'] + data['falling_days_f']
            if (z_plus_f > 20).any():
                validation_result['warnings'].append("存在Z+F大于20的异常数据")
        
        # 计算统计信息
        if validation_result['is_valid']:
            validation_result['statistics'] = {
                'total_records': len(data),
                'date_range': {
                    'start': data['date'].min(),
                    'end': data['date'].max()
                },
                'price_stats': {
                    'min': data['close'].min(),
                    'max': data['close'].max(),
                    'mean': data['close'].mean(),
                    'std': data['close'].std()
                } if 'close' in data.columns else {},
                'volume_stats': {
                    'min': data['volume'].min(),
                    'max': data['volume'].max(),
                    'mean': data['volume'].mean(),
                    'std': data['volume'].std()
                } if 'volume' in data.columns else {}
            }
        
        return validation_result

# 便捷函数
def load_pvfrs_data(code: str, market_type: str, start_date: str, end_date: str) -> pd.DataFrame:
    """便捷函数：加载PVFRS数据"""
    db = next(get_db())
    try:
        loader = PVFRSDataLoader(db)
        return loader.load_stock_data(code, market_type, start_date, end_date)
    finally:
        db.close()

def get_pvfrs_stocks(market_type: str) -> List[str]:
    """便捷函数：获取有PVFRS数据的股票列表"""
    db = next(get_db())
    try:
        loader = PVFRSDataLoader(db)
        return loader.get_available_stocks(market_type)
    finally:
        db.close()
