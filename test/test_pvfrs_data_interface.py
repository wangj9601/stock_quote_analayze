"""
PVFRS数据接口测试
测试数据获取、验证、清洗和标准化功能
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend_core.strategies.pvfrs import (
    PVFRSDataInterface,
    MarketData,
    DataInsufficientException,
    ValidationException
)


class TestPVFRSDataInterface:
    """PVFRS数据接口测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.data_interface = PVFRSDataInterface()
    
    def test_get_market_data_mock(self):
        """测试获取模拟市场数据"""
        symbol = "000001"
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        data = self.data_interface.get_market_data(symbol, start_date, end_date)
        
        # 验证数据基本属性
        assert len(data) >= 20  # 至少20天数据
        assert all(isinstance(item, MarketData) for item in data)
        assert all(item.symbol == symbol for item in data)
        
        # 验证数据按日期排序
        dates = [item.date for item in data]
        assert dates == sorted(dates)
    
    def test_validate_data_valid(self):
        """测试有效数据验证"""
        valid_data = [
            MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000),
            MarketData("000001", "2024-01-02", 10.2, 10.8, 10.0, 10.5, 1200000, 12600000)
        ]
        
        assert self.data_interface.validate_data(valid_data) is True
    
    def test_validate_data_invalid_price(self):
        """测试无效价格数据验证"""
        # 创建有效数据，然后在验证时检测无效情况
        valid_data = [
            MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000)
        ]
        
        # 手动修改数据使其无效（绕过__post_init__验证）
        valid_data[0].__dict__['high'] = 9.5  # high < open
        
        assert self.data_interface.validate_data(valid_data) is False
    
    def test_validate_data_empty(self):
        """测试空数据验证"""
        assert self.data_interface.validate_data([]) is False
    
    def test_clean_data_basic(self):
        """测试基本数据清洗"""
        raw_data = [
            MarketData("000001", "2024-01-02", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000),
            MarketData("000001", "2024-01-01", 9.8, 10.2, 9.5, 10.0, 800000, 8000000)
        ]
        
        cleaned_data = self.data_interface.clean_data(raw_data)
        
        # 验证数据按日期排序
        assert cleaned_data[0].date == "2024-01-01"
        assert cleaned_data[1].date == "2024-01-02"
        
        # 验证数据数量
        assert len(cleaned_data) == 2
    
    def test_get_stock_list_mock(self):
        """测试获取模拟股票列表"""
        cn_stocks = self.data_interface.get_stock_list("CN")
        us_stocks = self.data_interface.get_stock_list("US")
        hk_stocks = self.data_interface.get_stock_list("HK")
        
        assert len(cn_stocks) > 0
        assert len(us_stocks) > 0
        assert len(hk_stocks) > 0
        
        # 验证股票代码格式
        assert "000001" in cn_stocks
        assert "AAPL" in us_stocks
        assert "00700" in hk_stocks
    
    def test_get_trading_calendar(self):
        """测试获取交易日历"""
        start_date = "2024-01-01"
        end_date = "2024-01-07"
        
        calendar = self.data_interface.get_trading_calendar(start_date, end_date)
        
        # 验证返回的是工作日
        for date_str in calendar:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            assert date_obj.weekday() < 5  # 周一到周五
    
    def test_standardize_columns(self):
        """测试列名标准化"""
        raw_data = {
            'trade_date': '2024-01-01',
            'open_price': 10.0,
            'high_price': 10.5,
            'low_price': 9.8,
            'close_price': 10.2,
            'vol': 1000000,
            'turnover': 10200000
        }
        
        standardized = self.data_interface._standardize_columns(raw_data)
        
        assert standardized['date'] == '2024-01-01'
        assert standardized['open'] == 10.0
        assert standardized['high'] == 10.5
        assert standardized['low'] == 9.8
        assert standardized['close'] == 10.2
        assert standardized['volume'] == 1000000
        assert standardized['amount'] == 10200000
    
    def test_validate_price_data(self):
        """测试价格数据验证"""
        # 有效价格数据
        valid_item = MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000)
        assert self.data_interface._validate_price_data(valid_item) is True
        
        # 无效价格数据 - 手动创建无效数据
        invalid_item = MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000)
        invalid_item.__dict__['high'] = 9.5  # high < open
        assert self.data_interface._validate_price_data(invalid_item) is False
        
        # 无效价格数据 - 价格为负（应该在创建时就抛出异常）
        try:
            MarketData("000001", "2024-01-01", -1.0, 10.5, 9.8, 10.2, 1000000, 10200000)
            assert False, "应该抛出异常"
        except ValueError:
            pass
    
    def test_validate_volume_data(self):
        """测试成交量数据验证"""
        # 有效成交量数据
        valid_item = MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000)
        assert self.data_interface._validate_volume_data(valid_item) is True
        
        # 无效成交量数据
        try:
            MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, -1000, 10200000)
            assert False, "应该抛出异常"
        except ValueError:
            pass
    
    def test_validate_date_format(self):
        """测试日期格式验证"""
        assert self.data_interface._validate_date_format("2024-01-01") is True
        assert self.data_interface._validate_date_format("2024/01/01") is False
        assert self.data_interface._validate_date_format("invalid") is False
    
    def test_validate_data_continuity(self):
        """测试数据连续性验证"""
        # 正常数据
        normal_data = [
            MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000),
            MarketData("000001", "2024-01-02", 10.2, 10.8, 10.0, 10.5, 1200000, 12600000)
        ]
        assert self.data_interface._validate_data_continuity(normal_data) is True
        
        # 重复日期数据
        duplicate_data = [
            MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 10200000),
            MarketData("000001", "2024-01-01", 10.2, 10.8, 10.0, 10.5, 1200000, 12600000)
        ]
        assert self.data_interface._validate_data_continuity(duplicate_data) is False
    
    def test_convert_to_market_data(self):
        """测试DataFrame转换为MarketData"""
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'open': [10.0, 10.2],
            'high': [10.5, 10.8],
            'low': [9.8, 10.0],
            'close': [10.2, 10.5],
            'volume': [1000000, 1200000],
            'amount': [10200000, 12600000]
        })
        
        market_data = self.data_interface._convert_to_market_data(df, "000001")
        
        assert len(market_data) == 2
        assert all(isinstance(item, MarketData) for item in market_data)
        assert market_data[0].symbol == "000001"
        assert market_data[0].date == "2024-01-01"
        assert market_data[0].open == 10.0
    
    def test_generate_mock_data(self):
        """测试生成模拟数据"""
        symbol = "000001"
        start_date = "2024-01-01"
        end_date = "2024-01-10"
        
        df = self.data_interface._generate_mock_data(symbol, start_date, end_date)
        
        assert len(df) > 0
        assert 'date' in df.columns
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns
        assert 'amount' in df.columns
        
        # 验证价格逻辑
        for _, row in df.iterrows():
            assert row['high'] >= max(row['open'], row['close'])
            assert row['low'] <= min(row['open'], row['close'])
            assert row['volume'] > 0
            assert row['amount'] > 0
    
    def test_fill_missing_data(self):
        """测试填补缺失数据"""
        # 成交额为0的数据
        item = MarketData("000001", "2024-01-01", 10.0, 10.5, 9.8, 10.2, 1000000, 0)
        
        fixed_item = self.data_interface._fill_missing_data(item, [], 0)
        
        # 应该估算成交额
        expected_amount = 1000000 * 10.2
        assert fixed_item.amount == expected_amount
    
    def test_data_insufficient_exception(self):
        """测试数据不足异常"""
        # 模拟返回少于20天的数据
        with patch.object(self.data_interface, '_generate_mock_data') as mock_generate:
            # 创建少于20天的数据
            short_df = pd.DataFrame({
                'date': ['2024-01-01', '2024-01-02'],
                'open': [10.0, 10.2],
                'high': [10.5, 10.8],
                'low': [9.8, 10.0],
                'close': [10.2, 10.5],
                'volume': [1000000, 1200000],
                'amount': [10200000, 12600000]
            })
            mock_generate.return_value = short_df
            
            with pytest.raises(DataInsufficientException):
                self.data_interface.get_market_data("000001", "2024-01-01", "2024-01-02")
    
    def test_with_external_data_source(self):
        """测试使用外部数据源"""
        # 创建模拟数据源
        mock_data_source = Mock()
        
        # 创建不同日期的数据以避免重复日期问题
        dates = [f"2024-01-{i:02d}" for i in range(1, 26)]
        mock_data_source.get_stock_data.return_value = pd.DataFrame({
            'date': dates,
            'open': [10.0] * 25,
            'high': [10.5] * 25,
            'low': [9.8] * 25,
            'close': [10.2] * 25,
            'volume': [1000000] * 25,
            'amount': [10200000] * 25
        })
        
        data_interface = PVFRSDataInterface(mock_data_source)
        data = data_interface.get_market_data("000001", "2024-01-01", "2024-01-31")
        
        assert len(data) == 25
        mock_data_source.get_stock_data.assert_called_once_with("000001", "2024-01-01", "2024-01-31")


if __name__ == "__main__":
    pytest.main([__file__])