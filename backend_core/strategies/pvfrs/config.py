"""
PVFRS策略配置管理
提供默认配置和配置验证功能
"""

import json
import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from .interfaces import IConfigManager
from .models import ConfigurationException


class PVFRSConfigManager(IConfigManager):
    """PVFRS配置管理器"""
    
    def __init__(self, config_file: str = "pvfrs_config.json"):
        self.config_file = config_file
        self.default_config_path = os.path.join(
            os.path.dirname(__file__), 
            self.config_file
        )
        self._current_config = None
        self._config_loaded = False
        self.logger = logging.getLogger(__name__)
        
        # 配置变更回调函数列表
        self._config_change_callbacks = []
    def get_default_config(self) -> Dict:
        """获取默认策略参数"""
        return {
            # === 基础PVFRS四维度条件 ===
            'buy_macro_displacement_min': 0,      # 宏观位移最小值
            'buy_instant_deviation_min': 0,       # 即时强度最小值
            'buy_rising_days_advantage': True,    # 上涨天数优势
            'buy_efficiency_min': 0,              # 效率指标最小值
            
            # === 增强买入条件 ===
            'buy_bias_min': 0.02,                 # 最小偏离度2%
            'buy_relative_displacement_min': 0.05, # 最小相对位移5%
            'buy_consecutive_days': 2,            # 连续确认天数
            'buy_price_above_ma5': False,         # 价格必须在5日均线之上
            'buy_ma5_above_ma20': False,          # 5日均线必须在20日均线之上
            
            # === 卖出条件 ===
            'sell_below_ma20': True,              # 收盘价跌破20日均线卖出
            'stop_loss': -0.06,                   # 止损-6%
            'take_profit': 0.25,                  # 止盈25%
            'max_holding_days': 45,               # 最大持有天数
            
            # === 风险管理 ===
            'max_position_size': 0.1,             # 最大仓位10%
            'sell_divergence_days': 3,            # 价涨量缩背离天数
            'sell_bias_max': 0.15,                # 最大偏离度15%
            'sell_instant_deviation_max': 0.10,   # 最大即时强度10%
            
            # === 动态风险管理 ===
            'profit_stage1': 0.15,                # 盈利阶段1: 15%
            'sell_reversal_conditions_low_profit': 3,  # 低盈利时需要的反转条件数
            'sell_reversal_conditions_high_profit': 2, # 高盈利时需要的反转条件数
            'max_holding_days_base': 45,          # 基础最大持有天数
            
            # === 回测参数 ===
            'initial_capital': 100000,            # 初始资金
            'commission_rate': 0.0003,            # 手续费率
            'slippage_rate': 0.001,              # 滑点率
            'market_type': 'CN',                  # 市场类型（CN=中国A股）
            
            # === 数据参数 ===
            'observation_period': 20,             # 观察周期（天）
            'min_data_points': 25,                # 最少数据点数
            'price_change_threshold': 0.001,      # 价格变化阈值
            'volume_change_threshold': 0.1,       # 成交量变化阈值
        }
    
    def load_config(self, config_path: Optional[str] = None) -> Dict:
        """加载配置
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
            
        Returns:
            Dict: 配置字典
            
        Raises:
            ConfigurationException: 配置加载或验证失败
        """
        if config_path is None:
            config_path = self.default_config_path
        
        # 先获取默认配置
        default_config = self.get_default_config()
        
        # 如果配置文件不存在，创建默认配置文件
        if not os.path.exists(config_path):
            self.logger.info(f"配置文件不存在，创建默认配置: {config_path}")
            try:
                self.save_config(default_config, config_path)
            except Exception as e:
                self.logger.warning(f"无法创建默认配置文件: {e}")
            self._current_config = default_config
            self._config_loaded = True
            return default_config
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 合并默认配置（确保所有必需的参数都存在）
            merged_config = default_config.copy()
            merged_config.update(config)
            
            # 验证配置
            if not self.validate_config(merged_config):
                raise ConfigurationException(f"配置文件无效: {config_path}")
            
            self._current_config = merged_config
            self._config_loaded = True
            self.logger.info(f"成功加载配置文件: {config_path}")
            
            return merged_config
            
        except json.JSONDecodeError as e:
            raise ConfigurationException(f"配置文件JSON格式错误: {e}")
        except Exception as e:
            # 如果加载失败，返回默认配置
            self.logger.error(f"加载配置文件失败，使用默认配置: {e}")
            self._current_config = default_config
            self._config_loaded = True
            return default_config
    
    def save_config(self, config: Dict, config_path: Optional[str] = None) -> bool:
        """保存配置
        
        Args:
            config: 要保存的配置字典
            config_path: 配置文件路径，如果为None则使用默认路径
            
        Returns:
            bool: 保存是否成功
            
        Raises:
            ConfigurationException: 配置验证或保存失败
        """
        if config_path is None:
            config_path = self.default_config_path
        
        try:
            # 验证配置
            if not self.validate_config(config):
                raise ConfigurationException("配置参数无效")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # 添加保存时间戳
            config_with_metadata = config.copy()
            config_with_metadata['_metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            # 原子性写入：先写入临时文件，然后重命名
            temp_path = config_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config_with_metadata, f, indent=2, ensure_ascii=False)
            
            # 重命名为最终文件
            os.replace(temp_path, config_path)
            
            # 更新当前配置
            self._current_config = config
            self._config_loaded = True
            
            # 通知配置变更
            self._notify_config_change(config)
            
            self.logger.info(f"配置已保存到: {config_path}")
            return True
            
        except Exception as e:
            # 清理临时文件
            temp_path = config_path + '.tmp'
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise ConfigurationException(f"保存配置文件失败: {e}")
    
    def validate_config(self, config: Dict) -> bool:
        """验证配置有效性"""
        try:
            # 检查必需的参数（只检查核心参数）
            required_params = [
                'stop_loss',
                'take_profit',
                'max_position_size',
                'max_holding_days',
                'observation_period'
            ]
            
            for param in required_params:
                if param not in config:
                    raise ValueError(f"缺少必需参数: {param}")
            
            # 验证数值范围
            validations = [
                ('stop_loss', lambda x: -1 <= x <= 0, "止损比例必须在-100%到0%之间"),
                ('take_profit', lambda x: x > 0, "止盈比例必须大于0"),
                ('max_position_size', lambda x: 0 < x <= 1, "最大仓位必须在0-100%之间"),
                ('max_holding_days', lambda x: x > 0, "最大持有天数必须大于0"),
                ('observation_period', lambda x: x >= 5, "观察周期必须至少5天"),
                ('buy_consecutive_days', lambda x: x >= 1, "连续确认天数必须至少1天"),
                ('commission_rate', lambda x: 0 <= x <= 0.01, "手续费率必须在0-1%之间"),
                ('slippage_rate', lambda x: 0 <= x <= 0.01, "滑点率必须在0-1%之间"),
            ]
            
            for param, validator, message in validations:
                if param in config and not validator(config[param]):
                    raise ValueError(f"{message}: {config[param]}")
            
            # 验证逻辑关系
            if config.get('buy_bias_min', 0) < 0:
                raise ValueError("最小偏离度不能为负")
            
            if config.get('buy_relative_displacement_min', 0) < 0:
                raise ValueError("最小相对位移不能为负")
            
            if abs(config.get('stop_loss', 0)) >= config.get('take_profit', 1):
                raise ValueError("止损幅度不应大于等于止盈幅度")
            
            return True
            
        except Exception as e:
            raise ConfigurationException(f"配置验证失败: {e}")
    
    def update_config(self, updates: Dict, config_path: Optional[str] = None) -> Dict:
        """更新配置
        
        Args:
            updates: 要更新的配置项
            config_path: 配置文件路径
            
        Returns:
            Dict: 更新后的完整配置
            
        Raises:
            ConfigurationException: 配置更新失败
        """
        # 如果还没有加载配置，先加载
        if not self._config_loaded:
            current_config = self.load_config(config_path)
        else:
            current_config = self._current_config.copy()
        
        # 应用更新
        current_config.update(updates)
        
        # 验证并保存
        if self.validate_config(current_config):
            self.save_config(current_config, config_path)
            self.logger.info(f"配置已更新: {list(updates.keys())}")
        
        return current_config
    
    def reset_to_default(self, config_path: Optional[str] = None) -> Dict:
        """重置为默认配置
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            Dict: 默认配置
        """
        default_config = self.get_default_config()
        self.save_config(default_config, config_path)
        self.logger.info("配置已重置为默认值")
        return default_config
    
    def get_current_config(self) -> Dict:
        """获取当前配置
        
        Returns:
            Dict: 当前配置，如果未加载则返回默认配置
        """
        if not self._config_loaded:
            return self.load_config()
        return self._current_config.copy()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取单个配置值
        
        Args:
            key: 配置键名
            default: 默认值
            
        Returns:
            Any: 配置值
        """
        config = self.get_current_config()
        return config.get(key, default)
    
    def set_config_value(self, key: str, value: Any, config_path: Optional[str] = None) -> None:
        """设置单个配置值
        
        Args:
            key: 配置键名
            value: 配置值
            config_path: 配置文件路径
        """
        self.update_config({key: value}, config_path)
    
    def add_config_change_callback(self, callback):
        """添加配置变更回调函数
        
        Args:
            callback: 回调函数，接收新配置作为参数
        """
        if callback not in self._config_change_callbacks:
            self._config_change_callbacks.append(callback)
    
    def remove_config_change_callback(self, callback):
        """移除配置变更回调函数
        
        Args:
            callback: 要移除的回调函数
        """
        if callback in self._config_change_callbacks:
            self._config_change_callbacks.remove(callback)
    
    def _notify_config_change(self, new_config: Dict):
        """通知配置变更
        
        Args:
            new_config: 新的配置
        """
        for callback in self._config_change_callbacks:
            try:
                callback(new_config)
            except Exception as e:
                self.logger.error(f"配置变更回调执行失败: {e}")
    
    def backup_config(self, config_path: Optional[str] = None, backup_suffix: str = None) -> str:
        """备份当前配置
        
        Args:
            config_path: 配置文件路径
            backup_suffix: 备份文件后缀，默认使用时间戳
            
        Returns:
            str: 备份文件路径
        """
        if config_path is None:
            config_path = self.default_config_path
        
        if backup_suffix is None:
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        backup_path = f"{config_path}.backup_{backup_suffix}"
        
        if os.path.exists(config_path):
            import shutil
            shutil.copy2(config_path, backup_path)
            self.logger.info(f"配置已备份到: {backup_path}")
        
        return backup_path
    
    def restore_config(self, backup_path: str, config_path: Optional[str] = None) -> Dict:
        """从备份恢复配置
        
        Args:
            backup_path: 备份文件路径
            config_path: 目标配置文件路径
            
        Returns:
            Dict: 恢复的配置
        """
        if config_path is None:
            config_path = self.default_config_path
        
        if not os.path.exists(backup_path):
            raise ConfigurationException(f"备份文件不存在: {backup_path}")
        
        import shutil
        shutil.copy2(backup_path, config_path)
        
        # 重新加载配置
        restored_config = self.load_config(config_path)
        self.logger.info(f"配置已从备份恢复: {backup_path}")
        
        return restored_config