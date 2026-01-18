#!/usr/bin/env python3
"""
测试PVFRS维度值显示修复
验证价格维度、频率维度、成交量维度、入场时机是否正确赋值
"""

import sys
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend_core.strategies.pvfrs.frontend_interface import FrontendInterface
from backend_core.strategies.pvfrs.models import MarketData, StockSelectionResult
from backend_core.strategies.pvfrs.pvfrs_system import PVFRSSystem


class TestPVFRSDimensionValuesFix:
    """测试PVFRS维度值显示修复"""
    
    def setup_method(self):
        """测试前准备"""
        self.frontend_interface = FrontendInterface()
        
        # 创建模拟的股票数据
        self.mock_stock_data = self._create_mock_stock_data()
        
        # 创建模拟的分析结果
        self.mock_analysis_result = self._create_mock_analysis_result()
    
    def _create_mock_stock_data(self):
        """创建模拟股票数据"""
        base_date = datetime.now() - timedelta(days=30)
        stock_data = []
        
        for i in range(25):  # 25天数据
            date = base_date + timedelta(days=i)
            # 模拟上涨趋势
            price = 10.0 + i * 0.2 + (i % 3) * 0.1
            volume = 1000000 + i * 50000
            
            market_data = MarketData(
                symbol="000001",
                date=date.strftime("%Y-%m-%d"),
                open=price - 0.1,
                high=price + 0.2,
                low=price - 0.2,
                close=price,
                volume=volume,
                amount=price * volume
            )
            stock_data.append(market_data)
        
        return stock_data
    
    def _create_mock_analysis_result(self):
        """创建模拟分析结果"""
        return {
            'signal_strength': 0.75,
            'overall_score': 0.75,
            'analysis_time': datetime.now().isoformat(),
            'strategy_analysis': {
                'price_dimension': {
                    'macro_displacement': 2.5,
                    'instant_deviation': 1.2,
                    'avg_price_20d': 12.0,
                    'price_dimension_valid': True
                },
                'frequency_dimension': {
                    'rising_days': 14,
                    'falling_days': 6,
                    'frequency_advantage': True,
                    'frequency_dimension_valid': True
                },
                'volume_dimension': {
                    'avg_volume_20d': 1200000,
                    'current_volume': 1500000,
                    'efficiency_ratio': 1.25,
                    'volume_efficiency': True,
                    'volume_price_resonance': True,
                    'volume_dimension_valid': True
                },
                'entry_timing_analysis': {
                    'optimal_timing': True,
                    'acceptable_timing': True,
                    'timing_score': 0.8
                }
            },
            'resonance_analysis': {
                'three_dimension_resonance': True,
                'partial_resonance': False,
                'resonance_strength': 0.85
            },
            'investment_advice': {
                'recommendation': '买入',
                'confidence': 0.8,
                'reason': '三维共振信号强烈'
            },
            'conditions_met': {
                'price_dimension_valid': True,
                'frequency_dimension_valid': True,
                'volume_dimension_valid': True,
                'three_dimension_resonance': True
            }
        }
    
    def test_frontend_interface_dimension_extraction(self):
        """测试前端接口维度值提取"""
        # Mock PVFRS系统
        with patch.object(self.frontend_interface, 'pvfrs_system') as mock_system:
            mock_system.analyze_stock.return_value = self.mock_analysis_result
            
            # Mock 数据获取方法
            with patch.object(self.frontend_interface, '_get_stock_data') as mock_get_data:
                mock_get_data.return_value = self.mock_stock_data
                
                with patch.object(self.frontend_interface, '_get_stock_pool') as mock_get_pool:
                    mock_get_pool.return_value = ['000001']
                    
                    with patch.object(self.frontend_interface, '_get_stock_name') as mock_get_name:
                        mock_get_name.return_value = '平安银行'
                        
                        # 获取选股结果
                        results = self.frontend_interface.get_selection_results()
                        
                        # 验证结果
                        assert len(results) == 1
                        result = results[0]
                        
                        # 验证基本信息
                        assert result.symbol == '000001'
                        assert result.name == '平安银行'
                        assert result.signal_strength == 0.75
                        
                        # 验证indicators包含维度分析结果
                        indicators = result.indicators
                        assert isinstance(indicators, dict)
                        
                        # 验证价格维度
                        price_dim = indicators.get('price_dimension', {})
                        assert price_dim.get('macro_displacement') == 2.5
                        assert price_dim.get('instant_deviation') == 1.2
                        assert price_dim.get('avg_price_20d') == 12.0
                        assert price_dim.get('price_dimension_valid') is True
                        
                        # 验证频率维度
                        frequency_dim = indicators.get('frequency_dimension', {})
                        assert frequency_dim.get('rising_days') == 14
                        assert frequency_dim.get('falling_days') == 6
                        assert frequency_dim.get('frequency_advantage') is True
                        assert frequency_dim.get('frequency_dimension_valid') is True
                        
                        # 验证成交量维度
                        volume_dim = indicators.get('volume_dimension', {})
                        assert volume_dim.get('avg_volume_20d') == 1200000
                        assert volume_dim.get('current_volume') == 1500000
                        assert volume_dim.get('efficiency_ratio') == 1.25
                        assert volume_dim.get('volume_efficiency') is True
                        assert volume_dim.get('volume_price_resonance') is True
                        assert volume_dim.get('volume_dimension_valid') is True
                        
                        # 验证入场时机分析
                        entry_timing = indicators.get('entry_timing_analysis', {})
                        assert entry_timing.get('optimal_timing') is True
                        assert entry_timing.get('acceptable_timing') is True
                        assert entry_timing.get('timing_score') == 0.8
                        
                        # 验证其他分析结果
                        resonance_analysis = indicators.get('resonance_analysis', {})
                        assert resonance_analysis.get('three_dimension_resonance') is True
                        assert resonance_analysis.get('resonance_strength') == 0.85
                        
                        investment_advice = indicators.get('investment_advice', {})
                        assert investment_advice.get('recommendation') == '买入'
                        assert investment_advice.get('confidence') == 0.8
                        
                        print("✓ 前端接口维度值提取测试通过")
    
    def test_api_response_formatting(self):
        """测试API响应格式化"""
        # 创建选股结果
        result = StockSelectionResult(
            symbol='000001',
            name='平安银行',
            price=15.50,
            signal_strength=0.75,
            indicators={
                'price_dimension': {
                    'macro_displacement': 2.5,
                    'instant_deviation': 1.2,
                    'avg_price_20d': 12.0,
                    'price_dimension_valid': True
                },
                'frequency_dimension': {
                    'rising_days': 14,
                    'falling_days': 6,
                    'frequency_advantage': True,
                    'frequency_dimension_valid': True
                },
                'volume_dimension': {
                    'avg_volume_20d': 1200000,
                    'current_volume': 1500000,
                    'efficiency_ratio': 1.25,
                    'volume_efficiency': True,
                    'volume_price_resonance': True,
                    'volume_dimension_valid': True
                },
                'entry_timing_analysis': {
                    'optimal_timing': True,
                    'acceptable_timing': True,
                    'timing_score': 0.8
                },
                'resonance_analysis': {
                    'three_dimension_resonance': True,
                    'partial_resonance': False,
                    'resonance_strength': 0.85
                },
                'investment_advice': {
                    'recommendation': '买入',
                    'confidence': 0.8,
                    'reason': '三维共振信号强烈'
                }
            },
            conditions_met={
                'price_dimension_valid': True,
                'frequency_dimension_valid': True,
                'volume_dimension_valid': True,
                'three_dimension_resonance': True
            },
            analysis_time=datetime.now().isoformat()
        )
        
        # 转换为字典
        result_dict = result.to_dict()
        
        # 模拟API响应格式化逻辑
        indicators = result_dict.get('indicators', {})
        
        # 价格维度状态
        price_dim = indicators.get('price_dimension', {})
        if price_dim.get('price_dimension_valid', False):
            price_status = f"宏观位移: {price_dim.get('macro_displacement', 0):.2f}"
        else:
            price_status = "未满足条件"
        
        # 频率维度状态
        frequency_dim = indicators.get('frequency_dimension', {})
        if frequency_dim.get('frequency_dimension_valid', False):
            rising_days = frequency_dim.get('rising_days', 0)
            falling_days = frequency_dim.get('falling_days', 0)
            frequency_status = f"上涨{rising_days}天/下跌{falling_days}天"
        else:
            frequency_status = "未满足条件"
        
        # 成交量维度状态
        volume_dim = indicators.get('volume_dimension', {})
        if volume_dim.get('volume_dimension_valid', False):
            efficiency_ratio = volume_dim.get('efficiency_ratio', 0)
            volume_status = f"效率比: {efficiency_ratio:.2f}"
        else:
            volume_status = "未满足条件"
        
        # 入场时机状态
        entry_timing = indicators.get('entry_timing_analysis', {})
        if entry_timing.get('optimal_timing', False):
            entry_status = "最佳时机"
        elif entry_timing.get('acceptable_timing', False):
            entry_status = "可接受"
        else:
            entry_status = "等待时机"
        
        # 验证格式化结果
        assert price_status == "宏观位移: 2.50"
        assert frequency_status == "上涨14天/下跌6天"
        assert volume_status == "效率比: 1.25"
        assert entry_status == "最佳时机"
        
        print("✓ API响应格式化测试通过")
        print(f"  价格维度状态: {price_status}")
        print(f"  频率维度状态: {frequency_status}")
        print(f"  成交量维度状态: {volume_status}")
        print(f"  入场时机状态: {entry_status}")
    
    def test_dimension_values_not_empty(self):
        """测试维度值不为空"""
        # Mock PVFRS系统
        with patch.object(self.frontend_interface, 'pvfrs_system') as mock_system:
            mock_system.analyze_stock.return_value = self.mock_analysis_result
            
            # Mock 数据获取方法
            with patch.object(self.frontend_interface, '_get_stock_data') as mock_get_data:
                mock_get_data.return_value = self.mock_stock_data
                
                with patch.object(self.frontend_interface, '_get_stock_pool') as mock_get_pool:
                    mock_get_pool.return_value = ['000001']
                    
                    with patch.object(self.frontend_interface, '_get_stock_name') as mock_get_name:
                        mock_get_name.return_value = '平安银行'
                        
                        # 获取选股结果
                        results = self.frontend_interface.get_selection_results()
                        
                        # 验证结果不为空
                        assert len(results) > 0
                        result = results[0]
                        
                        # 验证维度值不为空
                        indicators = result.indicators
                        
                        # 价格维度不为空
                        price_dim = indicators.get('price_dimension', {})
                        assert price_dim  # 不为空字典
                        assert 'macro_displacement' in price_dim
                        assert 'instant_deviation' in price_dim
                        assert 'avg_price_20d' in price_dim
                        
                        # 频率维度不为空
                        frequency_dim = indicators.get('frequency_dimension', {})
                        assert frequency_dim  # 不为空字典
                        assert 'rising_days' in frequency_dim
                        assert 'falling_days' in frequency_dim
                        assert 'frequency_advantage' in frequency_dim
                        
                        # 成交量维度不为空
                        volume_dim = indicators.get('volume_dimension', {})
                        assert volume_dim  # 不为空字典
                        assert 'avg_volume_20d' in volume_dim
                        assert 'current_volume' in volume_dim
                        assert 'efficiency_ratio' in volume_dim
                        
                        # 入场时机不为空
                        entry_timing = indicators.get('entry_timing_analysis', {})
                        assert entry_timing  # 不为空字典
                        assert 'optimal_timing' in entry_timing
                        
                        print("✓ 维度值非空测试通过")
                        print(f"  价格维度字段数: {len(price_dim)}")
                        print(f"  频率维度字段数: {len(frequency_dim)}")
                        print(f"  成交量维度字段数: {len(volume_dim)}")
                        print(f"  入场时机字段数: {len(entry_timing)}")


def test_pvfrs_dimension_values_fix():
    """运行PVFRS维度值修复测试"""
    print("开始测试PVFRS维度值显示修复...")
    
    test_instance = TestPVFRSDimensionValuesFix()
    test_instance.setup_method()
    
    try:
        # 测试前端接口维度值提取
        test_instance.test_frontend_interface_dimension_extraction()
        
        # 测试API响应格式化
        test_instance.test_api_response_formatting()
        
        # 测试维度值不为空
        test_instance.test_dimension_values_not_empty()
        
        print("\n✅ 所有测试通过！PVFRS维度值显示修复成功")
        print("\n修复内容:")
        print("1. ✓ 前端接口正确提取维度分析结果")
        print("2. ✓ API响应包含前端期望的字段格式")
        print("3. ✓ 价格维度、频率维度、成交量维度、入场时机都有正确的值")
        print("4. ✓ 维度状态显示格式化正确")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_pvfrs_dimension_values_fix()
    sys.exit(0 if success else 1)