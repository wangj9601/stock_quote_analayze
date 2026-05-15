"""
ConfigService 单元测试
测试配置服务的核心功能
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend_api.models import Base, User, UserPushConfig
from backend_api.services.config_service import ConfigService, ConfigUpdate


# 测试数据库设置
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def test_db():
    """创建测试数据库"""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSessionLocal()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_user(test_db):
    """创建示例用户"""
    user = User(
        username="test_user",
        email="test@example.com",
        password_hash="hashed_password",
        role="user",
        status="active"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def config_service(test_db):
    """创建配置服务实例"""
    return ConfigService(test_db)


def test_create_default_config(config_service, sample_user):
    """测试创建默认配置"""
    config = config_service.create_default_config(sample_user.id)
    
    assert config.user_id == sample_user.id
    assert config.enabled == True
    assert config.channels == ["email"]
    assert config.push_times == ["09:00", "15:00"]
    assert config.report_type == "summary"
    assert config.stock_codes is None


def test_create_default_config_user_not_exist(config_service):
    """测试为不存在的用户创建配置"""
    with pytest.raises(ValueError, match="用户不存在"):
        config_service.create_default_config(99999)


def test_create_default_config_allows_multiple_tasks(config_service, sample_user):
    """同一用户可有多条推送任务，重复调用 create_default_config 会再插入一条。"""
    c1 = config_service.create_default_config(sample_user.id)
    c2 = config_service.create_default_config(sample_user.id)
    assert c1.id != c2.id
    assert c1.user_id == sample_user.id and c2.user_id == sample_user.id


def test_get_user_config(config_service, sample_user):
    """测试获取用户配置"""
    # 创建配置
    created_config = config_service.create_default_config(sample_user.id)
    
    # 获取配置
    config = config_service.get_user_config(sample_user.id)
    
    assert config is not None
    assert config.id == created_config.id
    assert config.user_id == sample_user.id


def test_get_user_config_not_exist(config_service, sample_user):
    """测试获取不存在的配置"""
    config = config_service.get_user_config(sample_user.id)
    assert config is None


def test_update_user_config_enabled(config_service, sample_user):
    """测试更新配置 - 启用/禁用"""
    config_service.create_default_config(sample_user.id)
    
    # 禁用推送
    update = ConfigUpdate(enabled=False)
    updated_config = config_service.update_user_config(sample_user.id, update)
    
    assert updated_config.enabled == False
    assert updated_config.channels == ["email"]  # 其他字段不变


def test_update_user_config_channels(config_service, sample_user):
    """测试更新配置 - 推送渠道"""
    config_service.create_default_config(sample_user.id)
    
    # 更新渠道
    update = ConfigUpdate(channels=["wechat", "email"])
    updated_config = config_service.update_user_config(sample_user.id, update)
    
    assert updated_config.channels == ["wechat", "email"]


def test_update_user_config_push_times(config_service, sample_user):
    """测试更新配置 - 推送时间"""
    config_service.create_default_config(sample_user.id)
    
    # 更新推送时间
    update = ConfigUpdate(push_times=["10:00", "16:00"])
    updated_config = config_service.update_user_config(sample_user.id, update)
    
    assert updated_config.push_times == ["10:00", "16:00"]


def test_update_user_config_report_type(config_service, sample_user):
    """测试更新配置 - 报告类型"""
    config_service.create_default_config(sample_user.id)
    
    # 更新报告类型
    update = ConfigUpdate(report_type="detailed")
    updated_config = config_service.update_user_config(sample_user.id, update)
    
    assert updated_config.report_type == "detailed"


def test_update_user_config_stock_codes(config_service, sample_user):
    """测试更新配置 - 股票范围"""
    config_service.create_default_config(sample_user.id)
    
    # 更新股票范围
    update = ConfigUpdate(stock_codes=["000001", "600000"])
    updated_config = config_service.update_user_config(sample_user.id, update)
    
    assert updated_config.stock_codes == ["000001", "600000"]


def test_update_user_config_multiple_fields(config_service, sample_user):
    """测试更新配置 - 多个字段"""
    config_service.create_default_config(sample_user.id)
    
    # 同时更新多个字段
    update = ConfigUpdate(
        enabled=False,
        channels=["email"],
        report_type="detailed",
        stock_codes=["000001"]
    )
    updated_config = config_service.update_user_config(sample_user.id, update)
    
    assert updated_config.enabled == False
    assert updated_config.channels == ["email"]
    assert updated_config.report_type == "detailed"
    assert updated_config.stock_codes == ["000001"]


def test_update_user_config_auto_create(config_service, sample_user):
    """测试更新配置 - 自动创建不存在的配置"""
    # 不先创建配置，直接更新
    update = ConfigUpdate(enabled=False)
    updated_config = config_service.update_user_config(sample_user.id, update)
    
    # 应该自动创建配置并应用更新
    assert updated_config is not None
    assert updated_config.enabled == False
    assert updated_config.channels == ["email"]  # 默认值（create_default_config / 自动创建）


def test_update_user_config_user_not_exist(config_service):
    """测试更新不存在用户的配置"""
    update = ConfigUpdate(enabled=False)
    
    with pytest.raises(ValueError, match="用户不存在"):
        config_service.update_user_config(99999, update)


def test_get_users_for_push_time(config_service, test_db):
    """测试获取指定时间点需要推送的用户"""
    # 创建多个用户和配置
    user1 = User(username="user1", email="user1@example.com", 
                 password_hash="hash1", status="active")
    user2 = User(username="user2", email="user2@example.com", 
                 password_hash="hash2", status="active")
    user3 = User(username="user3", email="user3@example.com", 
                 password_hash="hash3", status="active")
    user4 = User(username="user4", email="user4@example.com", 
                 password_hash="hash4", status="inactive")  # 非活跃用户
    
    test_db.add_all([user1, user2, user3, user4])
    test_db.commit()
    
    # 创建配置
    config1 = UserPushConfig(user_id=user1.id, enabled=True, 
                            push_times=["09:30", "15:30"])
    config2 = UserPushConfig(user_id=user2.id, enabled=True, 
                            push_times=["09:30"])
    config3 = UserPushConfig(user_id=user3.id, enabled=False, 
                            push_times=["09:30"])  # 禁用推送
    config4 = UserPushConfig(user_id=user4.id, enabled=True, 
                            push_times=["09:30"])  # 非活跃用户
    
    test_db.add_all([config1, config2, config3, config4])
    test_db.commit()
    
    # 获取09:30需要推送的用户
    users = config_service.get_users_for_push_time("09:30")
    
    # 应该只包含user1和user2（启用推送且活跃）
    assert len(users) == 2
    user_ids = [u.id for u in users]
    assert user1.id in user_ids
    assert user2.id in user_ids
    assert user3.id not in user_ids  # 禁用推送
    assert user4.id not in user_ids  # 非活跃用户


def test_get_users_for_push_time_no_users(config_service):
    """测试获取推送用户 - 没有用户"""
    users = config_service.get_users_for_push_time("09:30")
    assert len(users) == 0


def test_get_users_for_push_time_different_times(config_service, test_db):
    """测试不同时间点的推送用户"""
    # 创建用户
    user1 = User(username="user1", email="user1@example.com", 
                 password_hash="hash1", status="active")
    user2 = User(username="user2", email="user2@example.com", 
                 password_hash="hash2", status="active")
    
    test_db.add_all([user1, user2])
    test_db.commit()
    
    # user1只在09:30推送，user2只在15:30推送
    config1 = UserPushConfig(user_id=user1.id, enabled=True, 
                            push_times=["09:30"])
    config2 = UserPushConfig(user_id=user2.id, enabled=True, 
                            push_times=["15:30"])
    
    test_db.add_all([config1, config2])
    test_db.commit()
    
    # 测试09:30
    users_morning = config_service.get_users_for_push_time("09:30")
    assert len(users_morning) == 1
    assert users_morning[0].id == user1.id
    
    # 测试15:30
    users_afternoon = config_service.get_users_for_push_time("15:30")
    assert len(users_afternoon) == 1
    assert users_afternoon[0].id == user2.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
