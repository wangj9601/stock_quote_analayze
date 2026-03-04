"""
配置管理服务
提供用户推送配置的管理功能
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from dataclasses import dataclass
import logging

from backend_api.models import User, UserPushConfig
from backend_core.database.db import get_db

logger = logging.getLogger(__name__)


@dataclass
class ConfigUpdate:
    """配置更新数据类"""
    enabled: Optional[bool] = None
    channels: Optional[List[str]] = None
    push_times: Optional[List[str]] = None
    report_type: Optional[str] = None
    stock_codes: Optional[List[str]] = None


class ConfigService:
    """配置管理服务"""
    
    def __init__(self, db: Session):
        """
        初始化配置服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("配置服务初始化完成")
    
    def get_user_config(self, user_id: int) -> Optional[UserPushConfig]:
        """
        获取用户推送配置
        
        Args:
            user_id: 用户ID
            
        Returns:
            UserPushConfig: 用户推送配置，如果不存在则返回None
        """
        try:
            config = self.db.query(UserPushConfig).filter(
                UserPushConfig.user_id == user_id
            ).first()
            
            if config:
                logger.info(f"获取用户配置成功: user_id={user_id}")
            else:
                logger.warning(f"用户配置不存在: user_id={user_id}")
            
            return config
        
        except Exception as e:
            logger.error(f"获取用户配置失败: user_id={user_id}, error={str(e)}")
            raise

    def get_all_distinct_push_times(self) -> List[str]:
        """
        从 user_push_configs 表获取所有启用配置中出现过的推送时间点（去重、排序）。
        用于 PushScheduler 按表内配置的时间点调度任务。
        """
        try:
            configs = self.db.query(UserPushConfig).filter(UserPushConfig.enabled == True).all()
            times_set = set()
            for c in configs:
                if c.push_times:
                    for t in c.push_times:
                        if t and isinstance(t, str) and self._validate_time_format(t):
                            times_set.add(t)
            result = sorted(times_set)
            logger.info(f"从 user_push_configs 读取到 {len(result)} 个推送时间点: {result}")
            return result
        except Exception as e:
            logger.error(f"获取推送时间点失败: {str(e)}")
            raise

    @staticmethod
    def _validate_time_format(time_str: str) -> bool:
        """校验时间为 HH:MM 格式"""
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            h, m = int(parts[0]), int(parts[1])
            return 0 <= h <= 23 and 0 <= m <= 59
        except (ValueError, AttributeError):
            return False

    def update_user_config(
        self, 
        user_id: int, 
        config_update: ConfigUpdate
    ) -> UserPushConfig:
        """
        更新用户推送配置
        
        Args:
            user_id: 用户ID
            config_update: 配置更新对象
            
        Returns:
            UserPushConfig: 更新后的配置
            
        Raises:
            ValueError: 如果用户不存在或配置不存在
        """
        try:
            # 检查用户是否存在
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                error_msg = f"用户不存在: user_id={user_id}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 获取或创建配置
            config = self.get_user_config(user_id)
            if not config:
                logger.info(f"配置不存在，创建默认配置: user_id={user_id}")
                config = self.create_default_config(user_id)
            
            # 更新配置字段
            if config_update.enabled is not None:
                config.enabled = config_update.enabled
            
            if config_update.channels is not None:
                config.channels = config_update.channels
            
            if config_update.push_times is not None:
                config.push_times = config_update.push_times
            
            if config_update.report_type is not None:
                config.report_type = config_update.report_type
            
            if config_update.stock_codes is not None:
                config.stock_codes = config_update.stock_codes
            
            # 更新时间戳
            config.updated_at = datetime.now()
            
            # 提交更改
            self.db.commit()
            self.db.refresh(config)
            
            logger.info(f"更新用户配置成功: user_id={user_id}")
            return config
        
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"更新用户配置失败: user_id={user_id}, error={str(e)}")
            raise
    
    def create_default_config(self, user_id: int) -> UserPushConfig:
        """
        为用户创建默认推送配置
        
        Args:
            user_id: 用户ID
            
        Returns:
            UserPushConfig: 创建的默认配置
            
        Raises:
            ValueError: 如果用户不存在或配置已存在
        """
        try:
            # 检查用户是否存在
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                error_msg = f"用户不存在: user_id={user_id}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 检查配置是否已存在
            existing_config = self.get_user_config(user_id)
            if existing_config:
                error_msg = f"用户配置已存在: user_id={user_id}"
                logger.warning(error_msg)
                raise ValueError(error_msg)
            
            # 创建默认配置（管理端「邮件推送配置」添加时默认走邮件）
            config = UserPushConfig(
                user_id=user_id,
                enabled=True,
                channels=["email"],
                push_times=["09:00", "15:00"],
                report_type="summary",
                stock_codes=None  # None表示全部自选股
            )
            
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            
            logger.info(f"创建默认配置成功: user_id={user_id}")
            return config
        
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"创建默认配置失败: user_id={user_id}, error={str(e)}")
            raise

    def delete_user_config(self, user_id: int) -> bool:
        """删除用户推送配置（从 user_push_configs 表删除）。无配置时返回 False。"""
        try:
            config = self.get_user_config(user_id)
            if not config:
                logger.warning(f"用户推送配置不存在: user_id={user_id}")
                return False
            self.db.delete(config)
            self.db.commit()
            logger.info(f"删除用户推送配置成功: user_id={user_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"删除用户推送配置失败: user_id={user_id}, error={str(e)}")
            raise

    def get_users_for_push_time(self, push_time: str) -> List[User]:
        """
        获取指定时间点需要推送的用户列表
        
        Args:
            push_time: 推送时间点 (如 "09:30")
            
        Returns:
            List[User]: 需要推送的用户列表
        """
        try:
            # 查询启用推送且包含指定时间点的用户配置
            configs = self.db.query(UserPushConfig).filter(
                UserPushConfig.enabled == True
            ).all()
            
            # 筛选包含指定推送时间的配置
            users = []
            for config in configs:
                if push_time in config.push_times:
                    user = self.db.query(User).filter(
                        User.id == config.user_id,
                        User.status == "active"  # 只包含活跃用户
                    ).first()
                    
                    if user:
                        users.append(user)
            
            logger.info(f"获取推送用户列表成功: push_time={push_time}, count={len(users)}")
            return users
        
        except Exception as e:
            logger.error(f"获取推送用户列表失败: push_time={push_time}, error={str(e)}")
            raise
