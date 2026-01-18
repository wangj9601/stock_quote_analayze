"""
PVFRS核心数据模型测试
测试MarketData、PVFRSIndicators、Signal等核心数据类的功能
"""

import pytest
from datetime import datetime
from backend_core.strategies.pvfrs.models import (
    MarketData, PVFRSIndicators, Signal, Trade, BacktestResult,
    SignalType, PVFRSException, DataInsufficientException,
    CalculationException, ConfigurationException, ValidationException
)


class TestMarketData:
    """MarketData数据结构测试"""
    
    def test_valid_market_data_creation(self):
        """测试有效市场数据创建"""
        data = MarketData(
            symbol="000001",
            date="2024-01-15",
            open=10.0,
            high=11.0,
            low=9.5,
            close=10.5,
            volume=1000000,
            amount=10500000.0
        )
        
        assert data.symbol == "000001"
        assert data.date == "2024-01-15"
        assert data.open == 10.0
        assert data.high == 11.0
        assert data.low == 9.5
        assert data.close == 10.5
        assert data.volume == 1000000
        assert data.amount == 10500000.0
    
    def test_invalid_price_data(self):
        """测试无效价格数据"""
        # 测试负价格
        with pytest.raises(ValueError, match="价格数据不能为负或零"):
            MarketData(
                symbol="000001", date="2024-01-15",
                open=-1.0, high=11.0, low=9.5, close=10.5,
                volume=1000000, amount=10500000.0
            )
        
        # 测试零价格
        with pytest.raises(ValueError, match="价格数据不能为负或零"):
            MarketData(
                symbol="000001", date="2024-01-15",
                open=10.0, high=0, low=9.5, close=10.5,
                volume=1000000, amount=10500000.0
            )
    
    def test_inconsistent_price_data(self):
        """测试不一致的价格数据"""
        # 最高价低于收盘价
        with pytest.raises(ValueError, match="价格数据不一致"):
            MarketData(
                symbol="000001", date="2024-01-15",
                open=10.0, high=9.0, low=9.5, close=10.5,
                volume=1000000, amount=10500000.0
            )
        
        # 最低价高于开盘价
        with pytest.raises(ValueError, match="价格数据不一致"):
            MarketData(
                symbol="000001", date="2024-01-15",
                open=10.0, high=11.0, low=10.5, close=10.2,
                volume=1000000, amount=10500000.0
            )
    
    def test_invalid_volume_data(self):
        """测试无效成交量数据"""
        # 负成交量
        with pytest.raises(ValueError, match="成交量或成交额不能为负"):
            MarketData(
                symbol="000001", date="2024-01-15",
                open=10.0, high=11.0, low=9.5, close=10.5,
                volume=-1000, amount=10500000.0
            )
        
        # 负成交额
        with pytest.raises(ValueError, match="成交量或成交额不能为负"):
            MarketData(
                symbol="000001", date="2024-01-15",
                open=10.0, high=11.0, low=9.5, close=10.5,
                volume=1000000, amount=-10500000.0
            )


class TestPVFRSIndicators:
    """PVFRSIndicators指标结构测试"""
    
    def test_valid_indicators_creation(self):
        """测试有效指标创建"""
        indicators = PVFRSIndicators(
            macro_displacement=0.5,
            instant_deviation=0.3,
            avg_price_20d=10.0,
            rising_days=12,
            falling_days=8,
            frequency_advantage=True,
            avg_volume_20d=1000000.0,
            current_volume=1200000.0,
            efficiency_ratio=1.2,
            amplitude_ratio=0.05,
            resonance_strength=0.8
        )
        
        assert indicators.macro_displacement == 0.5
        assert indicators.instant_deviation == 0.3
        assert indicators.avg_price_20d == 10.0
        assert indicators.rising_days == 12
        assert indicators.falling_days == 8
        assert indicators.frequency_advantage is True
        assert indicators.avg_volume_20d == 1000000.0
        assert indicators.current_volume == 1200000.0
        assert indicators.efficiency_ratio == 1.2
        assert indicators.amplitude_ratio == 0.05
        assert indicators.resonance_strength == 0.8
    
    def test_invalid_avg_price(self):
        """测试无效平均价格"""
        with pytest.raises(ValueError, match="20日平均价格必须大于0"):
            PVFRSIndicators(
                macro_displacement=0.5, instant_deviation=0.3, avg_price_20d=0,
                rising_days=12, falling_days=8, frequency_advantage=True,
                avg_volume_20d=1000000.0, current_volume=1200000.0,
                efficiency_ratio=1.2, amplitude_ratio=0.05, resonance_strength=0.8
            )
    
    def test_invalid_days_count(self):
        """测试无效天数统计"""
        with pytest.raises(ValueError, match="涨跌天数不能为负"):
            PVFRSIndicators(
                macro_displacement=0.5, instant_deviation=0.3, avg_price_20d=10.0,
                rising_days=-1, falling_days=8, frequency_advantage=True,
                avg_volume_20d=1000000.0, current_volume=1200000.0,
                efficiency_ratio=1.2, amplitude_ratio=0.05, resonance_strength=0.8
            )
    
    def test_invalid_volume(self):
        """测试无效成交量"""
        with pytest.raises(ValueError, match="成交量不能为负"):
            PVFRSIndicators(
                macro_displacement=0.5, instant_deviation=0.3, avg_price_20d=10.0,
                rising_days=12, falling_days=8, frequency_advantage=True,
                avg_volume_20d=-1000000.0, current_volume=1200000.0,
                efficiency_ratio=1.2, amplitude_ratio=0.05, resonance_strength=0.8
            )
    
    def test_invalid_resonance_strength(self):
        """测试无效共振强度"""
        with pytest.raises(ValueError, match="共振强度必须在0-1之间"):
            PVFRSIndicators(
                macro_displacement=0.5, instant_deviation=0.3, avg_price_20d=10.0,
                rising_days=12, falling_days=8, frequency_advantage=True,
                avg_volume_20d=1000000.0, current_volume=1200000.0,
                efficiency_ratio=1.2, amplitude_ratio=0.05, resonance_strength=1.5
            )


class TestSignal:
    """Signal交易信号测试"""
    
    def test_valid_signal_creation(self):
        """测试有效信号创建"""
        signal = Signal(
            symbol="000001",
            date="2024-01-15",
            signal_type=SignalType.BUY,
            price=10.5,
            strength=0.8,
            reason="三维共振买入信号"
        )
        
        assert signal.symbol == "000001"
        assert signal.date == "2024-01-15"
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 10.5
        assert signal.strength == 0.8
        assert signal.reason == "三维共振买入信号"
        assert signal.conditions_met == {}
    
    def test_invalid_signal_price(self):
        """测试无效信号价格"""
        with pytest.raises(ValueError, match="信号价格必须大于0"):
            Signal(
                symbol="000001", date="2024-01-15",
                signal_type=SignalType.BUY, price=0,
                strength=0.8, reason="测试信号"
            )
    
    def test_invalid_signal_strength(self):
        """测试无效信号强度"""
        with pytest.raises(ValueError, match="信号强度必须在0-1之间"):
            Signal(
                symbol="000001", date="2024-01-15",
                signal_type=SignalType.BUY, price=10.5,
                strength=1.5, reason="测试信号"
            )


class TestTrade:
    """Trade交易记录测试"""
    
    def test_valid_trade_creation(self):
        """测试有效交易记录创建"""
        trade = Trade(
            symbol="000001",
            entry_date="2024-01-15",
            exit_date="2024-01-20",
            entry_price=10.0,
            exit_price=11.0,
            quantity=1000,
            position_size=10000.0,
            pnl=1000.0,
            pnl_percent=0.1,
            exit_reason="止盈"
        )
        
        assert trade.symbol == "000001"
        assert trade.entry_date == "2024-01-15"
        assert trade.exit_date == "2024-01-20"
        assert trade.entry_price == 10.0
        assert trade.exit_price == 11.0
        assert trade.quantity == 1000
        assert trade.position_size == 10000.0
        assert trade.pnl == 1000.0
        assert trade.pnl_percent == 0.1
        assert trade.exit_reason == "止盈"
    
    def test_invalid_trade_price(self):
        """测试无效交易价格"""
        with pytest.raises(ValueError, match="入场价格必须大于0"):
            Trade(
                symbol="000001", entry_date="2024-01-15", exit_date="2024-01-20",
                entry_price=0, exit_price=11.0, quantity=1000, position_size=10000.0
            )
    
    def test_invalid_trade_quantity(self):
        """测试无效交易数量"""
        with pytest.raises(ValueError, match="交易数量必须大于0"):
            Trade(
                symbol="000001", entry_date="2024-01-15", exit_date="2024-01-20",
                entry_price=10.0, exit_price=11.0, quantity=0, position_size=10000.0
            )


class TestBacktestResult:
    """BacktestResult回测结果测试"""
    
    def test_valid_backtest_result_creation(self):
        """测试有效回测结果创建"""
        result = BacktestResult(
            initial_capital=100000.0,
            final_capital=120000.0,
            total_return=0.2,
            annual_return=0.15,
            max_drawdown=-0.05,
            sharpe_ratio=1.5,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            avg_holding_period=15.0,
            trades=[],
            equity_curve=[]
        )
        
        assert result.initial_capital == 100000.0
        assert result.final_capital == 120000.0
        assert result.total_return == 0.2
        assert result.total_trades == 10
        assert result.winning_trades == 6
        assert result.losing_trades == 4
    
    def test_invalid_capital(self):
        """测试无效资金"""
        with pytest.raises(ValueError, match="初始资金必须大于0"):
            BacktestResult(
                initial_capital=0, final_capital=120000.0, total_return=0.2,
                annual_return=0.15, max_drawdown=-0.05, sharpe_ratio=1.5,
                win_rate=0.6, profit_factor=2.0, total_trades=10,
                winning_trades=6, losing_trades=4, avg_holding_period=15.0,
                trades=[], equity_curve=[]
            )
    
    def test_invalid_trade_counts(self):
        """测试无效交易次数"""
        with pytest.raises(ValueError, match="盈利和亏损交易次数之和必须等于总交易次数"):
            BacktestResult(
                initial_capital=100000.0, final_capital=120000.0, total_return=0.2,
                annual_return=0.15, max_drawdown=-0.05, sharpe_ratio=1.5,
                win_rate=0.6, profit_factor=2.0, total_trades=10,
                winning_trades=7, losing_trades=4, avg_holding_period=15.0,
                trades=[], equity_curve=[]
            )


class TestExceptions:
    """异常类测试"""
    
    def test_pvfrs_exception(self):
        """测试PVFRS异常基类"""
        with pytest.raises(PVFRSException):
            raise PVFRSException("测试异常")
    
    def test_data_insufficient_exception(self):
        """测试数据不足异常"""
        with pytest.raises(DataInsufficientException):
            raise DataInsufficientException("数据不足")
    
    def test_calculation_exception(self):
        """测试计算异常"""
        with pytest.raises(CalculationException):
            raise CalculationException("计算错误")
    
    def test_configuration_exception(self):
        """测试配置异常"""
        with pytest.raises(ConfigurationException):
            raise ConfigurationException("配置错误")
    
    def test_validation_exception(self):
        """测试验证异常"""
        with pytest.raises(ValidationException):
            raise ValidationException("验证失败")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])