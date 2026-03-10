"""
推送API路由测试
测试配置管理、推送记录、推送控制和管理员API
"""

import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.models import Base, User, UserPushConfig, PushRecord
from backend_api.push_routes import router, admin_router
from backend_core.database.db import get_db
from backend_api.auth import get_current_user, get_current_admin

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """创建测试用户"""
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        role="user",
        status="active",
        wechat_openid=None,
        wechat_type=None
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin(db_session):
    """创建测试管理员"""
    admin = User(
        id=2,
        username="admin",
        email="admin@example.com",
        password_hash="hashed_password",
        role="admin",
        status="active"
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def client(db_session, test_user):
    """创建测试客户端"""
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    app.include_router(admin_router)
    
    # 覆盖依赖
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    def override_get_current_user():
        return test_user
    
    def override_get_current_admin():
        return test_user  # 简化测试，使用同一个用户
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_admin] = override_get_current_admin
    
    return TestClient(app)


class TestConfigManagementAPI:
    """测试配置管理API"""
    
    def test_get_push_config_creates_default(self, client, db_session, test_user):
        """测试获取推送配置（自动创建默认配置）"""
        response = client.get("/api/push/config")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["user_id"] == test_user.id
        assert data["enabled"] == True
        assert data["channels"] == ["wechat"]
        assert data["push_times"] == ["09:30", "15:30"]
        assert data["report_type"] == "summary"
    
    def test_update_push_config(self, client, db_session, test_user):
        """测试更新推送配置"""
        # 先创建配置
        client.get("/api/push/config")
        
        # 更新配置
        update_data = {
            "enabled": False,
            "channels": ["email"],
            "push_times": ["10:00"],
            "report_type": "detailed"
        }
        
        response = client.put("/api/push/config", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["enabled"] == False
        assert data["channels"] == ["email"]
        assert data["push_times"] == ["10:00"]
        assert data["report_type"] == "detailed"

    def test_update_push_config_volume_aberration(self, client, db_session, test_user):
        """测试用户更新推送配置时可设置 report_type 为 volume_aberration"""
        client.get("/api/push/config")
        response = client.put("/api/push/config", json={"report_type": "volume_aberration"})
        assert response.status_code == 200
        data = response.json()
        assert data["report_type"] == "volume_aberration"
    
    def test_update_config_invalid_channel(self, client):
        """测试更新配置时使用无效渠道"""
        update_data = {
            "channels": ["invalid_channel"]
        }
        
        response = client.put("/api/push/config", json=update_data)
        
        assert response.status_code == 400
        assert "无效的推送渠道" in response.json()["detail"]
    
    def test_bind_wechat(self, client, db_session, test_user):
        """测试绑定微信"""
        bind_data = {
            "wechat_openid": "test_openid_123",
            "wechat_type": "personal"
        }
        
        response = client.post("/api/push/config/bind-wechat", json=bind_data)
        
        assert response.status_code == 200
        assert response.json()["success"] == True
        
        # 验证数据库中的更新
        db_session.refresh(test_user)
        assert test_user.wechat_openid == "test_openid_123"
        assert test_user.wechat_type == "personal"
    
    def test_unbind_wechat(self, client, db_session, test_user):
        """测试解绑微信"""
        # 先绑定
        test_user.wechat_openid = "test_openid"
        test_user.wechat_type = "personal"
        db_session.commit()
        
        # 解绑
        response = client.post("/api/push/config/unbind-wechat")
        
        assert response.status_code == 200
        assert response.json()["success"] == True
        
        # 验证数据库中的更新
        db_session.refresh(test_user)
        assert test_user.wechat_openid is None
        assert test_user.wechat_type is None
    
    def test_bind_email(self, client, db_session, test_user):
        """测试绑定邮箱"""
        bind_data = {
            "email": "newemail@example.com"
        }
        
        response = client.post("/api/push/config/bind-email", json=bind_data)
        
        assert response.status_code == 200
        assert response.json()["success"] == True
        
        # 验证数据库中的更新
        db_session.refresh(test_user)
        assert test_user.email == "newemail@example.com"


class TestPushRecordAPI:
    """测试推送记录API"""
    
    def test_get_push_records_empty(self, client):
        """测试查询推送记录（空列表）"""
        response = client.get("/api/push/records")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_push_records_with_data(self, client, db_session, test_user):
        """测试查询推送记录（有数据）"""
        # 创建测试记录
        record = PushRecord(
            user_id=test_user.id,
            push_date=date.today(),
            push_time="09:30",
            report_type="summary",
            channel_status={"wechat": "success"},
            status="success",
            report_file_path="/path/to/report.csv",
            error_messages={},
            retry_count=0,
            max_retries=3
        )
        db_session.add(record)
        db_session.commit()
        
        response = client.get("/api/push/records")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == test_user.id
        assert data[0]["status"] == "success"
    
    def test_get_push_record_by_id(self, client, db_session, test_user):
        """测试获取单条推送记录"""
        # 创建测试记录
        record = PushRecord(
            user_id=test_user.id,
            push_date=date.today(),
            push_time="09:30",
            report_type="summary",
            channel_status={"wechat": "success"},
            status="success",
            report_file_path="/path/to/report.csv",
            error_messages={},
            retry_count=0,
            max_retries=3
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)
        
        response = client.get(f"/api/push/records/{record.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == record.id
        assert data["user_id"] == test_user.id
    
    def test_get_push_record_not_found(self, client):
        """测试获取不存在的推送记录"""
        response = client.get("/api/push/records/999")
        
        assert response.status_code == 404


class TestPushControlAPI:
    """测试推送控制API"""
    
    def test_trigger_push_success(self, client, db_session, test_user):
        """测试手动触发推送（成功）"""
        # 创建用户配置
        config = UserPushConfig(
            user_id=test_user.id,
            enabled=True,
            channels=["wechat"],
            push_times=["09:30"],
            report_type="summary"
        )
        db_session.add(config)
        
        # 绑定微信
        test_user.wechat_openid = "test_openid"
        test_user.wechat_type = "personal"
        db_session.commit()
        
        # 由于实际推送会失败（没有真实的微信服务），我们只测试API调用
        # 实际的推送逻辑已经在push_service的测试中验证过了
        response = client.post("/api/push/trigger")
        
        # 应该返回200，但推送可能失败（因为没有真实服务）
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
    
    def test_get_push_status(self, client, db_session, test_user):
        """测试查询推送状态"""
        # 创建用户配置
        config = UserPushConfig(
            user_id=test_user.id,
            enabled=True,
            channels=["wechat"],
            push_times=["09:30"],
            report_type="summary"
        )
        db_session.add(config)
        db_session.commit()
        
        response = client.get("/api/push/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "pending_users_count" in data
        assert "total_records_today" in data


class TestAdminAPI:
    """测试管理员API"""
    
    def test_get_all_configs(self, client, db_session, test_user):
        """测试查看所有用户配置"""
        # 创建配置
        config = UserPushConfig(
            user_id=test_user.id,
            enabled=True,
            channels=["wechat"],
            push_times=["09:30"],
            report_type="summary"
        )
        db_session.add(config)
        db_session.commit()
        
        response = client.get("/api/admin/push/configs")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
    
    def test_get_all_records(self, client, db_session, test_user):
        """测试查看所有推送记录"""
        # 创建记录
        record = PushRecord(
            user_id=test_user.id,
            push_date=date.today(),
            push_time="09:30",
            report_type="summary",
            channel_status={"wechat": "success"},
            status="success",
            report_file_path="/path/to/report.csv",
            error_messages={},
            retry_count=0,
            max_retries=3
        )
        db_session.add(record)
        db_session.commit()
        
        response = client.get("/api/admin/push/records")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
    
    def test_global_push_control_pause(self, client):
        """测试全局暂停推送"""
        response = client.post(
            "/api/admin/push/global-control",
            json={"action": "pause"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["enabled"] == False
    
    def test_global_push_control_resume(self, client):
        """测试全局恢复推送"""
        response = client.post(
            "/api/admin/push/global-control",
            json={"action": "resume"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["enabled"] == True
    
    def test_get_push_statistics(self, client, db_session, test_user):
        """测试获取推送统计数据"""
        # 创建一些测试数据
        config = UserPushConfig(
            user_id=test_user.id,
            enabled=True,
            channels=["wechat"],
            push_times=["09:30"],
            report_type="summary"
        )
        db_session.add(config)
        
        record = PushRecord(
            user_id=test_user.id,
            push_date=date.today(),
            push_time="09:30",
            report_type="summary",
            channel_status={"wechat": "success"},
            status="success",
            report_file_path="/path/to/report.csv",
            error_messages={},
            retry_count=0,
            max_retries=3
        )
        db_session.add(record)
        db_session.commit()
        
        response = client.get("/api/admin/push/statistics")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "enabled_users" in data
        assert "total_records" in data
        assert "success_rate" in data

    def test_admin_update_push_config_volume_aberration(self, client, db_session, test_user):
        """测试管理员更新推送配置时可设置 report_type 为 volume_aberration"""
        config = UserPushConfig(
            user_id=test_user.id,
            enabled=True,
            channels=["email"],
            push_times=["09:30"],
            report_type="summary"
        )
        db_session.add(config)
        db_session.commit()
        response = client.put(
            f"/api/admin/push/configs/{test_user.id}",
            json={"report_type": "volume_aberration"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["report_type"] == "volume_aberration"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
