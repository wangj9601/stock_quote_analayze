"""
PVFRS策略标准化数据接口
提供统一的数据获取、清洗和标准化处理功能
"""

import logging
import pandas as pd
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime, timedelta
import numpy as np
from .interfaces import IDataInterface
from .models import MarketData, DataInsufficientException, ValidationException


class PVFRSDataInterface(IDataInterface):
    """PVFRS标准化数据接口"""
    
    def __init__(self, data_source=None):
        """
        初始化数据接口
        
        Args:
            data_source: 数据源对象，可以是数据库连接、API客户端等
        """
        self.data_source = data_source
        self.logger = logging.getLogger(__name__)
        
        # 数据质量阈值
        self.min_price = 0.01  # 最小价格
        self.max_price = 10000  # 最大价格
        self.min_volume = 0  # 最小成交量
        self.max_volume_ratio = 100  # 最大成交量倍数
        self.max_price_change_ratio = 0.2  # 最大单日涨跌幅
    
    def get_market_data(self, symbol: str, start_date: str, end_date: str) -> List[MarketData]:
        """
        获取市场数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            List[MarketData]: 市场数据列表
            
        Raises:
            DataInsufficientException: 数据不足
            ValidationException: 数据验证失败
        """
        try:
            # 如果有数据源，使用数据源获取数据
            if self.data_source:
                raw_data = self._fetch_from_data_source(symbol, start_date, end_date)
            else:
                # 否则使用模拟数据（用于测试）
                raw_data = self._generate_mock_data(symbol, start_date, end_date)
            
            # 转换为标准格式
            market_data = self._convert_to_market_data(raw_data, symbol)
            
            # 验证数据
            if not self.validate_data(market_data):
                raise ValidationException(f"数据验证失败: {symbol}")
            
            # 清洗数据
            cleaned_data = self.clean_data(market_data)
            
            # 检查数据充足性
            if len(cleaned_data) < 20:  # PVFRS需要至少20天数据
                raise DataInsufficientException(
                    f"数据不足，需要至少20天数据，实际获得{len(cleaned_data)}天: {symbol}"
                )
            
            self.logger.info(f"成功获取{symbol}的{len(cleaned_data)}天数据")
            return cleaned_data
            
        except Exception as e:
            self.logger.error(f"获取市场数据失败 {symbol}: {e}")
            raise
    
    def get_historical_data(self, symbol: str, start_date: str, end_date: str) -> List[MarketData]:
        """
        获取历史数据（get_market_data 的别名，用于兼容性）
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            List[MarketData]: 市场数据列表
        """
        return self.get_market_data(symbol, start_date, end_date)
    
    def validate_data(self, data: List[MarketData]) -> bool:
        """
        验证数据完整性
        
        Args:
            data: 市场数据列表
            
        Returns:
            bool: 数据是否有效
        """
        if not data:
            return False
        
        try:
            for item in data:
                # 验证基本数据结构
                if not isinstance(item, MarketData):
                    return False
                
                # 验证价格数据
                if not self._validate_price_data(item):
                    return False
                
                # 验证成交量数据
                if not self._validate_volume_data(item):
                    return False
                
                # 验证日期格式
                if not self._validate_date_format(item.date):
                    return False
            
            # 验证数据连续性
            if not self._validate_data_continuity(data):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"数据验证异常: {e}")
            return False
    
    def clean_data(self, data: List[MarketData]) -> List[MarketData]:
        """
        清洗数据
        
        Args:
            data: 原始市场数据列表
            
        Returns:
            List[MarketData]: 清洗后的数据列表
        """
        if not data:
            return []
        
        cleaned_data = []
        
        for i, item in enumerate(data):
            try:
                # 修复价格异常
                fixed_item = self._fix_price_anomalies(item, data, i)
                
                # 修复成交量异常
                fixed_item = self._fix_volume_anomalies(fixed_item, data, i)
                
                # 填补缺失数据
                fixed_item = self._fill_missing_data(fixed_item, data, i)
                
                cleaned_data.append(fixed_item)
                
            except Exception as e:
                self.logger.warning(f"清洗数据项失败，跳过: {item.date} - {e}")
                continue
        
        # 按日期排序
        cleaned_data.sort(key=lambda x: x.date)
        
        self.logger.info(f"数据清洗完成，保留{len(cleaned_data)}/{len(data)}条记录")
        return cleaned_data
    
    def get_stock_list(self, market: str = "CN") -> List[str]:
        """
        获取股票列表
        
        Args:
            market: 市场代码 (CN=中国A股, US=美股, HK=港股)
            
        Returns:
            List[str]: 股票代码列表
        """
        try:
            if self.data_source and hasattr(self.data_source, 'get_stock_list'):
                return self.data_source.get_stock_list(market)
            else:
                # 返回模拟股票列表
                return self._get_mock_stock_list(market)
                
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return []
    
    def get_trading_calendar(self, start_date: str, end_date: str, market: str = "CN") -> List[str]:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码
            
        Returns:
            List[str]: 交易日期列表
        """
        try:
            if self.data_source and hasattr(self.data_source, 'get_trading_calendar'):
                return self.data_source.get_trading_calendar(start_date, end_date, market)
            else:
                # 生成模拟交易日历（排除周末）
                return self._generate_trading_calendar(start_date, end_date)
                
        except Exception as e:
            self.logger.error(f"获取交易日历失败: {e}")
            return []
    
    def _fetch_from_data_source(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从数据源获取数据"""
        if hasattr(self.data_source, 'get_stock_data'):
            return self.data_source.get_stock_data(symbol, start_date, end_date)
        elif hasattr(self.data_source, 'query'):
            # 数据库查询（SQLAlchemy Session）
            from backend_api.models import HistoricalQuotes, HistoricalQuotesHK
            from sqlalchemy import desc, asc, cast, Date as SA_Date
            from datetime import datetime
            
            # 判断是A股还是港股
            is_hk = symbol.startswith('0') and len(symbol) == 5 or symbol.startswith('HK') or symbol.startswith('hk')
            
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                date_col = cast(HistoricalQuotes.date, SA_Date) if not is_hk else cast(HistoricalQuotesHK.date, SA_Date)
                
                if is_hk:
                    # 港股数据
                    query = self.data_source.query(HistoricalQuotesHK).filter(
                        HistoricalQuotesHK.code == symbol,
                        date_col >= start_dt,
                        date_col <= end_dt
                    ).order_by(asc(date_col))
                else:
                    # A股数据
                    query = self.data_source.query(HistoricalQuotes).filter(
                        HistoricalQuotes.code == symbol,
                        date_col >= start_dt,
                        date_col <= end_dt
                    ).order_by(asc(date_col))
                
                results = query.all()
                
                if not results:
                    self.logger.warning(f"未找到股票 {symbol} 的历史数据 ({start_date} 到 {end_date})")
                    return pd.DataFrame()
                
                # 转换为DataFrame
                data = []
                for item in results:
                    data.append({
                        'date': str(item.date)[:10] if item.date else None,
                        'open': float(item.open) if item.open else 0.0,
                        'high': float(item.high) if item.high else 0.0,
                        'low': float(item.low) if item.low else 0.0,
                        'close': float(item.close) if item.close else 0.0,
                        'volume': int(item.volume) if item.volume else 0,
                        'amount': float(item.amount) if hasattr(item, 'amount') and item.amount else 0.0
                    })
                
                return pd.DataFrame(data)
                
            except Exception as e:
                self.logger.error(f"从数据库获取股票 {symbol} 数据失败: {str(e)}")
                return pd.DataFrame()
        else:
            # 如果没有数据源，尝试直接从数据库获取
            try:
                from backend_api.database import SessionLocal
                from backend_api.models import HistoricalQuotes, HistoricalQuotesHK
                from sqlalchemy import desc, asc, cast, Date as SA_Date
                from datetime import datetime
                
                db = SessionLocal()
                try:
                    # 判断是A股还是港股
                    is_hk = symbol.startswith('0') and len(symbol) == 5 or symbol.startswith('HK') or symbol.startswith('hk')
                    
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                    date_col = cast(HistoricalQuotes.date, SA_Date) if not is_hk else cast(HistoricalQuotesHK.date, SA_Date)
                    
                    if is_hk:
                        query = db.query(HistoricalQuotesHK).filter(
                            HistoricalQuotesHK.code == symbol,
                            date_col >= start_dt,
                            date_col <= end_dt
                        ).order_by(asc(date_col))
                    else:
                        query = db.query(HistoricalQuotes).filter(
                            HistoricalQuotes.code == symbol,
                            date_col >= start_dt,
                            date_col <= end_dt
                        ).order_by(asc(date_col))
                    
                    results = query.all()
                    
                    if not results:
                        self.logger.warning(f"未找到股票 {symbol} 的历史数据 ({start_date} 到 {end_date})")
                        return pd.DataFrame()
                    
                    # 转换为DataFrame
                    data = []
                    for item in results:
                        data.append({
                            'date': str(item.date)[:10] if item.date else None,
                            'open': float(item.open) if item.open else 0.0,
                            'high': float(item.high) if item.high else 0.0,
                            'low': float(item.low) if item.low else 0.0,
                            'close': float(item.close) if item.close else 0.0,
                            'volume': int(item.volume) if item.volume else 0,
                            'amount': float(item.amount) if hasattr(item, 'amount') and item.amount else 0.0
                        })
                    
                    return pd.DataFrame(data)
                    
                finally:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    db.close()
                    
            except Exception as e:
                self.logger.error(f"获取股票 {symbol} 数据失败: {str(e)}")
                raise NotImplementedError(f"无法获取股票数据: {symbol} - {str(e)}")
    
    def _convert_to_market_data(self, df: pd.DataFrame, symbol: str) -> List[MarketData]:
        """将DataFrame转换为MarketData列表"""
        market_data = []
        
        for _, row in df.iterrows():
            try:
                # 标准化列名
                data_dict = self._standardize_columns(row.to_dict())
                
                market_data.append(MarketData(
                    symbol=symbol,
                    date=str(data_dict['date']),
                    open=float(data_dict['open']),
                    high=float(data_dict['high']),
                    low=float(data_dict['low']),
                    close=float(data_dict['close']),
                    volume=int(data_dict.get('volume', 0)),
                    amount=float(data_dict.get('amount', 0))
                ))
            except Exception as e:
                self.logger.warning(f"转换数据行失败: {e}")
                continue
        
        return market_data
    
    def _standardize_columns(self, data_dict: Dict) -> Dict:
        """标准化列名"""
        # 列名映射
        column_mapping = {
            # 日期
            'trade_date': 'date', 'trading_date': 'date', 'dt': 'date',
            # 价格
            'open_price': 'open', 'opening_price': 'open',
            'high_price': 'high', 'highest_price': 'high',
            'low_price': 'low', 'lowest_price': 'low',
            'close_price': 'close', 'closing_price': 'close',
            # 成交量成交额
            'vol': 'volume', 'trading_volume': 'volume',
            'turnover': 'amount', 'trading_amount': 'amount'
        }
        
        standardized = {}
        for key, value in data_dict.items():
            standard_key = column_mapping.get(key.lower(), key.lower())
            standardized[standard_key] = value
        
        return standardized
    
    def _validate_price_data(self, item: MarketData) -> bool:
        """验证价格数据"""
        prices = [item.open, item.high, item.low, item.close]
        
        # 检查价格范围
        for price in prices:
            if not (self.min_price <= price <= self.max_price):
                return False
        
        # 检查价格逻辑关系
        if item.high < max(item.open, item.close) or item.low > min(item.open, item.close):
            return False
        
        return True
    
    def _validate_volume_data(self, item: MarketData) -> bool:
        """验证成交量数据"""
        return item.volume >= self.min_volume and item.amount >= 0
    
    def _validate_date_format(self, date_str: str) -> bool:
        """验证日期格式"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _validate_data_continuity(self, data: List[MarketData]) -> bool:
        """验证数据连续性"""
        if len(data) < 2:
            return True
        
        # 检查是否有重复日期
        dates = [item.date for item in data]
        if len(dates) != len(set(dates)):
            return False
        
        return True
    
    def _fix_price_anomalies(self, item: MarketData, data: List[MarketData], index: int) -> MarketData:
        """修复价格异常"""
        # 如果价格异常，尝试用前一天的收盘价修复
        if index > 0:
            prev_close = data[index - 1].close
            
            # 检查是否有异常的价格跳跃
            price_change = abs(item.close - prev_close) / prev_close
            if price_change > self.max_price_change_ratio:
                # 可能是价格异常，但保持原数据（实际应用中可能需要更复杂的修复逻辑）
                self.logger.warning(f"检测到异常价格变动: {item.symbol} {item.date} {price_change:.2%}")
        
        return item
    
    def _fix_volume_anomalies(self, item: MarketData, data: List[MarketData], index: int) -> MarketData:
        """修复成交量异常"""
        if index > 0:
            prev_volume = data[index - 1].volume
            if prev_volume > 0:
                volume_ratio = item.volume / prev_volume
                if volume_ratio > self.max_volume_ratio:
                    self.logger.warning(f"检测到异常成交量: {item.symbol} {item.date} {volume_ratio:.1f}倍")
        
        return item
    
    def _fill_missing_data(self, item: MarketData, data: List[MarketData], index: int) -> MarketData:
        """填补缺失数据"""
        # 如果成交额为0但成交量不为0，尝试估算成交额
        if item.amount == 0 and item.volume > 0:
            estimated_amount = item.volume * item.close
            return MarketData(
                symbol=item.symbol,
                date=item.date,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
                volume=item.volume,
                amount=estimated_amount
            )
        
        return item
    
    def _generate_mock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """生成模拟数据（用于测试）"""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        # 过滤工作日
        dates = [d for d in dates if d.weekday() < 5]
        
        np.random.seed(hash(symbol) % 2**32)  # 确保相同股票的数据一致
        
        data = []
        base_price = 10.0
        
        for i, date in enumerate(dates):
            # 生成随机价格走势
            change = np.random.normal(0, 0.02)  # 2%的标准差
            base_price *= (1 + change)
            base_price = max(0.1, base_price)  # 确保价格不为负
            
            # 生成OHLC
            open_price = base_price * (1 + np.random.normal(0, 0.005))
            high_price = max(open_price, base_price) * (1 + abs(np.random.normal(0, 0.01)))
            low_price = min(open_price, base_price) * (1 - abs(np.random.normal(0, 0.01)))
            close_price = base_price
            
            # 生成成交量
            volume = int(np.random.lognormal(15, 1))  # 对数正态分布
            amount = volume * close_price
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume,
                'amount': round(amount, 2)
            })
        
        return pd.DataFrame(data)
    
    def _get_mock_stock_list(self, market: str) -> List[str]:
        """获取模拟股票列表"""
        if market == "CN":
            return ["000001", "000002", "600000", "600036", "000858"]
        elif market == "US":
            return ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        elif market == "HK":
            return ["00700", "00941", "01299", "02318", "03690"]
        else:
            return []
    
    def _generate_trading_calendar(self, start_date: str, end_date: str) -> List[str]:
        """生成交易日历（排除周末）"""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        trading_dates = [d.strftime('%Y-%m-%d') for d in dates if d.weekday() < 5]
        return trading_dates