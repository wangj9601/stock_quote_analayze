"""
PVFRS配置管理测试
测试配置加载、保存、验证等功能
"""

import pytest
import json
import os
import tempfile
from backend_core.strategies.pvfrs.config import PVFRSConfigManager
from backend_core.strategies.pvfrs.models import ConfigurationException


class TestPVFRSConfigManager:
    """PVFRS配置管理器测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.config_manager = PVFRSConfigManager()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_config_file = os.path.join(self.temp_dir, "test_config.json")
    
    def teardown_method(self):
        """测试后清理"""
        if os.path.exists(self.temp_config_file):
            os.remove(self.temp_config_file)
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_get_default_config(self):
        """测试获取默认配置"""
        config = self.config_manager.get_default_config()
        
        # 检查必需的参数
        required_params = [
            'buy_macro_displacement_min',
            'buy_instant_deviation_min',
            'buy_efficiency_min',
            'stop_loss',
            'take_profit',
            'max_position_size',
            'max_holding_days',
            'observation_period'
        ]
        
        for param in required_params:
            assert param in config, f"缺少必需参数: {param}"
        
        # 检查默认值
        assert config['buy_macro_displacement_min'] == 0
        assert config['buy_instant_deviation_min'] == 0
        assert config['buy_efficiency_min'] == 0
        assert config['stop_loss'] == -0.06
        assert config['take_profit'] == 0.25
        assert config['max_position_size'] == 0.1
        assert config['max_holding_days'] == 45
        assert config['observation_period'] == 20
    
    def test_validate_valid_config(self):
        """测试验证有效配置"""
        valid_config = self.config_manager.get_default_config()
        assert self.config_manager.validate_config(valid_config) is True
    
    def test_validate_missing_required_param(self):
        """测试验证缺少必需参数的配置"""
        invalid_config = self.config_manager.get_default_config()
        del invalid_config['stop_loss']
        
        with pytest.raises(ConfigurationException, match="缺少必需参数"):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_invalid_stop_loss(self):
        """测试验证无效止损参数"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['stop_loss'] = 0.1  # 止损应该为负值
        
        with pytest.raises(ConfigurationException, match="止损比例必须在-100%到0%之间"):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_invalid_take_profit(self):
        """测试验证无效止盈参数"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['take_profit'] = -0.1  # 止盈应该为正值
        
        with pytest.raises(ConfigurationException, match="止盈比例必须大于0"):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_invalid_position_size(self):
        """测试验证无效仓位大小"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['max_position_size'] = 1.5  # 仓位不能超过100%
        
        with pytest.raises(ConfigurationException, match="最大仓位必须在0-100%之间"):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_invalid_holding_days(self):
        """测试验证无效持有天数"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['max_holding_days'] = 0  # 持有天数必须大于0
        
        with pytest.raises(ConfigurationException, match="最大持有天数必须大于0"):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_invalid_observation_period(self):
        """测试验证无效观察周期"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['observation_period'] = 3  # 观察周期至少5天
        
        with pytest.raises(ConfigurationException, match="观察周期必须至少5天"):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_logical_relationship(self):
        """测试验证逻辑关系"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['stop_loss'] = -0.3
        invalid_config['take_profit'] = 0.2  # 止损幅度大于止盈幅度
        
        with pytest.raises(ConfigurationException, match="止损幅度不应大于等于止盈幅度"):
            self.config_manager.validate_config(invalid_config)
    
    def test_save_and_load_config(self):
        """测试保存和加载配置"""
        original_config = self.config_manager.get_default_config()
        original_config['stop_loss'] = -0.08  # 修改一个参数
        
        # 保存配置
        success = self.config_manager.save_config(original_config, self.temp_config_file)
        assert success is True
        assert os.path.exists(self.temp_config_file)
        
        # 加载配置
        loaded_config = self.config_manager.load_config(self.temp_config_file)
        assert loaded_config['stop_loss'] == -0.08
        
        # 验证所有默认参数都存在（合并功能）
        default_config = self.config_manager.get_default_config()
        for key in default_config:
            assert key in loaded_config
    
    def test_load_nonexistent_config(self):
        """测试加载不存在的配置文件"""
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.json")
        config = self.config_manager.load_config(nonexistent_file)
        
        # 应该返回默认配置
        default_config = self.config_manager.get_default_config()
        assert config == default_config
    
    def test_load_invalid_json_config(self):
        """测试加载无效JSON配置文件"""
        # 创建无效JSON文件
        with open(self.temp_config_file, 'w') as f:
            f.write("{ invalid json }")
        
        with pytest.raises(ConfigurationException, match="配置文件JSON格式错误"):
            self.config_manager.load_config(self.temp_config_file)
    
    def test_save_invalid_config(self):
        """测试保存无效配置"""
        invalid_config = {'invalid': 'config'}
        
        with pytest.raises(ConfigurationException, match="保存配置文件失败"):
            self.config_manager.save_config(invalid_config, self.temp_config_file)
    
    def test_update_config(self):
        """测试更新配置"""
        # 先保存一个基础配置
        base_config = self.config_manager.get_default_config()
        self.config_manager.save_config(base_config, self.temp_config_file)
        
        # 更新配置
        updates = {
            'stop_loss': -0.08,
            'take_profit': 0.3,
            'max_position_size': 0.15
        }
        
        updated_config = self.config_manager.update_config(updates, self.temp_config_file)
        
        assert updated_config['stop_loss'] == -0.08
        assert updated_config['take_profit'] == 0.3
        assert updated_config['max_position_size'] == 0.15
        
        # 验证文件已更新
        loaded_config = self.config_manager.load_config(self.temp_config_file)
        assert loaded_config['stop_loss'] == -0.08
    
    def test_reset_to_default(self):
        """测试重置为默认配置"""
        # 先保存一个修改过的配置
        modified_config = self.config_manager.get_default_config()
        modified_config['stop_loss'] = -0.08
        self.config_manager.save_config(modified_config, self.temp_config_file)
        
        # 重置为默认配置
        reset_config = self.config_manager.reset_to_default(self.temp_config_file)
        default_config = self.config_manager.get_default_config()
        
        assert reset_config == default_config
        
        # 验证文件已重置
        loaded_config = self.config_manager.load_config(self.temp_config_file)
        assert loaded_config['stop_loss'] == default_config['stop_loss']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])