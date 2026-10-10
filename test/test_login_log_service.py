# -*- coding: utf-8 -*-
"""用户登录日志服务单元测试（SQLite 内存库）。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend_api.models import UserLoginLog
from backend_api.services import login_log_service


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    UserLoginLog.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    monkeypatch.setattr(login_log_service, "SessionLocal", sessionmaker(bind=engine))
    yield session
    session.close()


def test_record_login_log_success(db_session):
    login_log_service.record_login_log(
        channel="user",
        username="alice",
        success=True,
        user_id=7,
        ip="127.0.0.1",
        user_agent="pytest",
    )
    row = db_session.query(UserLoginLog).one()
    assert row.channel == "user"
    assert row.username == "alice"
    assert row.success is True
    assert row.user_id == 7


def test_record_login_log_failure_without_user_id(db_session):
    login_log_service.record_login_log(
        channel="admin",
        username="bob",
        success=False,
        failure_reason="用户名或密码错误",
        ip="10.0.0.1",
    )
    row = db_session.query(UserLoginLog).one()
    assert row.channel == "admin"
    assert row.success is False
    assert row.failure_reason == "用户名或密码错误"
    assert row.user_id is None


def test_query_login_logs_filters_by_channel_and_success(db_session):
    now = datetime.now()
    for i, (ch, ok, name) in enumerate(
        [
            ("user", True, "u1"),
            ("user", False, "u2"),
            ("admin", True, "a1"),
        ]
    ):
        db_session.add(
            UserLoginLog(
                channel=ch,
                username=name,
                success=ok,
                created_at=now - timedelta(minutes=i),
            )
        )
    db_session.commit()

    result = login_log_service.query_login_logs(
        db_session, channel="user", success=True, page=1, page_size=20
    )
    assert result["total"] == 1
    assert result["items"][0]["username"] == "u1"
    assert result["items"][0]["channel"] == "user"
