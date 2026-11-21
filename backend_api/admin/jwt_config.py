"""
改进的JWT配置模块
提供更安全和可配置的JWT设置
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JWTConfig:
    """JWT配置类"""
    
    def __init__(self):
        # 从环境变量获取配置，如果没有则使用默认值
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24小时
        self.refresh_token_expire_days = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
        
        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证JWT配置"""
        if not self.secret_key or self.secret_key == "your-secret-key-here":
            raise ValueError(
                "JWT_SECRET_KEY 必须设置为非默认强密钥（与 backend_api.config 一致）"
            )
        
        if self.algorithm not in ["HS256", "HS384", "HS512"]:
            logger.error(f"❌ 不支持的JWT算法: {self.algorithm}")
            raise ValueError(f"不支持的JWT算法: {self.algorithm}")
        
        if self.access_token_expire_minutes <= 0:
            logger.error(f"❌ 无效的访问令牌过期时间: {self.access_token_expire_minutes}")
            raise ValueError(f"无效的访问令牌过期时间: {self.access_token_expire_minutes}")
        
        logger.info(f"✅ JWT配置验证通过:")
        logger.info(f"   算法: {self.algorithm}")
        logger.info(f"   访问令牌过期时间: {self.access_token_expire_minutes} 分钟")
        logger.info(f"   刷新令牌过期时间: {self.refresh_token_expire_days} 天")
    
    def get_token_expiry(self, token_type: str = "access") -> datetime:
        """获取令牌过期时间"""
        if token_type == "access":
            return datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        elif token_type == "refresh":
            return datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        else:
            raise ValueError(f"未知的令牌类型: {token_type}")
    
    def create_token_data(self, username: str, token_type: str = "access") -> Dict[str, Any]:
        """创建令牌数据"""
        now = datetime.utcnow()
        exp = self.get_token_expiry(token_type)
        
        return {
            "sub": username,
            "type": token_type,
            "iat": now,
            "exp": exp,
            "iss": "stock_analysis_system",
            "aud": "admin_users"
        }
    
    def is_token_expired(self, exp_timestamp: int) -> bool:
        """检查令牌是否过期"""
        if not exp_timestamp:
            return True
        
        exp_time = datetime.fromtimestamp(exp_timestamp)
        current_time = datetime.utcnow()
        return current_time > exp_time

# 创建全局JWT配置实例
jwt_config = JWTConfig()

# 导出配置常量（保持向后兼容）
SECRET_KEY = jwt_config.secret_key
ALGORITHM = jwt_config.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = jwt_config.access_token_expire_minutes
