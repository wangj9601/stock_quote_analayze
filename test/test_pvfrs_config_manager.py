"""
PVFRS配置管理器测试
测试配置加载、保存、验证和更新功能
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend_core.strategies.pvfrs import (
    PVFRSConfigManager,
    ConfigurationException
)


class TestPVFRSConfigManager:
    """PVFRS配置管理器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        self.config_manager = PVFRSConfigManager(self.config_file)
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_get_default_config(self):
        """测试获取默认配置"""
        config = self.config_manager.get_default_config()
        
        # 验证必需的配置项存在
        assert 'stop_loss' in config
        assert 'take_profit' in config
        assert 'max_position_size' in config
        assert 'observation_period' in config
        
        # 验证默认值合理性
        assert config['stop_loss'] < 0
        assert config['take_profit'] > 0
        assert 0 < config['max_position_size'] <= 1
        assert config['observation_period'] >= 5
    
    def test_load_config_default(self):
        """测试加载默认配置（文件不存在）"""
        config = self.config_manager.load_config()
        
        # 应该返回默认配置
        default_config = self.config_manager.get_default_config()
        assert config == default_config
        
        # 应该创建配置文件
        assert os.path.exists(self.config_file)
    
    def test_save_and_load_config(self):
        """测试保存和加载配置"""
        # 创建测试配置
        test_config = self.config_manager.get_default_config()
        test_config['stop_loss'] = -0.08
        test_config['take_profit'] = 0.20
        
        # 保存配置
        result = self.config_manager.save_config(test_config)
        assert result is True
        
        # 加载配置
        loaded_config = self.config_manager.load_config()
        assert loaded_config['stop_loss'] == -0.08
        assert loaded_config['take_profit'] == 0.20
    
    def test_validate_config_valid(self):
        """测试有效配置验证"""
        valid_config = self.config_manager.get_default_config()
        assert self.config_manager.validate_config(valid_config) is True
    
    def test_validate_config_invalid_stop_loss(self):
        """测试无效止损配置验证"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['stop_loss'] = 0.1  # 止损应该为负
        
        with pytest.raises(ConfigurationException):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_config_invalid_position_size(self):
        """测试无效仓位大小配置验证"""
        invalid_config = self.config_manager.get_default_config()
        invalid_config['max_position_size'] = 1.5  # 仓位不能超过100%
        
        with pytest.raises(ConfigurationException):
            self.config_manager.validate_config(invalid_config)
    
    def test_validate_config_missing_required(self):
        """测试缺少必需参数的配置验证"""
        invalid_config = {'some_param': 'value'}  # 缺少必需参数
        
        with pytest.raises(ConfigurationException):
            self.config_manager.validate_config(invalid_config)
    
    def test_update_config(self):
        """测试更新配置"""
        # 先保存初始配置
        initial_config = self.config_manager.get_default_config()
        self.config_manager.save_config(initial_config)
        
        # 更新配置
        updates = {
            'stop_loss': -0.05,
            'take_profit': 0.30
        }
        updated_config = self.config_manager.update_config(updates)
        
        # 验证更新结果
        assert updated_config['stop_loss'] == -0.05
        assert updated_config['take_profit'] == 0.30
        
        # 验证其他配置项未变
        assert updated_config['max_position_size'] == initial_config['max_position_size']
    
    def test_get_current_config(self):
        """测试获取当前配置"""
        # 首次调用应该加载默认配置
        config = self.config_manager.get_current_config()
        default_config = self.config_manager.get_default_config()
        assert config == default_config
    
    def test_get_set_config_value(self):
        """测试获取和设置单个配置值"""
        # 设置配置值
        self.config_manager.set_config_value('stop_loss', -0.07)
        
        # 获取配置值
        value = self.config_manager.get_config_value('stop_loss')
        assert value == -0.07
        
        # 获取不存在的配置值
        value = self.config_manager.get_config_value('non_existent', 'default')
        assert value == 'default'
    
    def test_config_change_callback(self):
        """测试配置变更回调"""
        callback_called = False
        new_config = None
        
        def test_callback(config):
            nonlocal callback_called, new_config
            callback_called = True
            new_config = config
        
        # 添加回调
        self.config_manager.add_config_change_callback(test_callback)
        
        # 更新配置
        test_config = self.config_manager.get_default_config()
        test_config['stop_loss'] = -0.09
        self.config_manager.save_config(test_config)
        
        # 验证回调被调用
        assert callback_called is True
        assert new_config['stop_loss'] == -0.09
        
        # 移除回调
        self.config_manager.remove_config_change_callback(test_callback)
    
    def test_backup_and_restore_config(self):
        """测试配置备份和恢复"""
        # 创建初始配置
        initial_config = self.config_manager.get_default_config()
        initial_config['stop_loss'] = -0.06
        self.config_manager.save_config(initial_config)
        
        # 备份配置
        backup_path = self.config_manager.backup_config()
        assert os.path.exists(backup_path)
        
        # 修改配置
        modified_config = initial_config.copy()
        modified_config['stop_loss'] = -0.10
        self.config_manager.save_config(modified_config)
        
        # 恢复配置
        restored_config = self.config_manager.restore_config(backup_path)
        assert restored_config['stop_loss'] == -0.06
    
    def test_reset_to_default(self):
        """测试重置为默认配置"""
        # 修改配置
        modified_config = self.config_manager.get_default_config()
        modified_config['stop_loss'] = -0.12
        self.config_manager.save_config(modified_config)
        
        # 重置为默认
        default_config = self.config_manager.reset_to_default()
        
        # 验证重置结果
        expected_default = self.config_manager.get_default_config()
        assert default_config == expected_default
        
        # 验证文件也被重置
        loaded_config = self.config_manager.load_config()
        # 移除元数据进行比较
        loaded_config_clean = {k: v for k, v in loaded_config.items() if k != '_metadata'}
        assert loaded_config_clean == expected_default
    
    def test_invalid_json_file(self):
        """测试无效JSON文件处理"""
        # 创建无效JSON文件
        with open(self.config_file, 'w') as f:
            f.write("invalid json content")
        
        # 应该抛出异常
        with pytest.raises(ConfigurationException):
            self.config_manager.load_config()
    
    def test_save_config_invalid(self):
        """测试保存无效配置"""
        invalid_config = {'stop_loss': 0.1}  # 无效配置
        
        with pytest.raises(ConfigurationException):
            self.config_manager.save_config(invalid_config)


if __name__ == "__main__":
    pytest.main([__file__])