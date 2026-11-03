"""环境同步异步 Job：产物目录、分片、网关与管理端接口。"""
from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend_api.auth import get_current_admin
from backend_api.database import get_db
from backend_api.env_sync.artifacts import resolve_artifact_root, ensure_job_dirs, read_manifest
from backend_api.env_sync.auth import hash_sync_key
from backend_api.env_sync.gateway_routes import router as gateway_router
from backend_api.env_sync.admin_routes import router as admin_router
from backend_api.env_sync.job_store import create_job, get_job, claim_running_slot, release_running_slot
from backend_api.env_sync.part_io import build_export_parts, read_part_json, write_part_json
from backend_api.models import Base, EnvSyncServerConfig, User


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_user(db):
    u = User(
        id=9001,
        username="admin_async",
        email="admin_async@example.com",
        password_hash="x",
        role="admin",
        status="active",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_resolve_artifact_root_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_SYNC_ARTIFACT_ROOT", str(tmp_path / "arts"))
    root = resolve_artifact_root()
    assert root == (tmp_path / "arts").resolve()


def test_create_job_pending(db):
    row = create_job(db, direction="async_push", modules=["gms_strategy_configs"], created_by="t")
    got = get_job(db, row.id)
    assert got is not None
    assert got.status == "pending"
    assert got.direction == "async_push"


def test_claim_running_slot_mutex():
    assert claim_running_slot("async_push", "a1")
    assert not claim_running_slot("async_push", "a2")
    assert claim_running_slot("async_pull", "b1")
    release_running_slot("async_push", "a1")
    assert claim_running_slot("async_push", "a2")
    release_running_slot("async_push", "a2")
    release_running_slot("async_pull", "b1")


def test_write_read_part_json(tmp_path):
    p = tmp_path / "0001.test.json.gz"
    digest = write_part_json(p, {"bundles": {"x": {"items": {"a": [1, 2]}}}})
    assert len(digest) == 64
    data = read_part_json(p)
    assert data["bundles"]["x"]["items"]["a"] == [1, 2]


def test_build_export_parts_undated(db, tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_SYNC_JOB_MAX_PARTS", "50")
    dest = tmp_path / "job1"
    dest.mkdir()
    # 无策略数据时仍应写出空/少内容 manifest
    with patch(
        "backend_api.env_sync.part_io.export_modules",
        return_value={
            "modules": ["gms_strategy_configs"],
            "bundles": {
                "strategy_configs": {
                    "module": "strategy_configs",
                    "items": {"gms_strategy_configs": [{"id": 1, "name": "t"}]},
                }
            },
        },
    ):
        manifest = build_export_parts(
            db,
            ["gms_strategy_configs"],
            start_date=None,
            end_date=None,
            dest=dest,
        )
    assert manifest["part_count"] >= 1
    part = manifest["parts"][0]
    payload = read_part_json(dest / "parts" / part["name"])
    assert "bundles" in payload
    assert read_manifest(dest)["part_count"] == manifest["part_count"]


def test_build_export_parts_max_parts(db, tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_SYNC_JOB_MAX_PARTS", "1")
    dest = tmp_path / "job2"
    dest.mkdir()

    def fake_export(db, modules, start_date=None, end_date=None):
        return {
            "modules": modules,
            "bundles": {
                "quotes": {
                    "module": "quotes",
                    "items": {"historical_quotes": [{"code": "1"}, {"code": "2"}]},
                }
            },
            "date_range": {"start_date": start_date, "end_date": end_date},
        }

    with patch("backend_api.env_sync.part_io.export_modules", side_effect=fake_export):
        with pytest.raises(ValueError, match="分片数超过上限"):
            build_export_parts(
                db,
                ["historical_quotes"],
                start_date="2026-11-01",
                end_date="2026-11-03",
                dest=dest,
            )


@pytest.fixture
def gateway_client(db):
    app = FastAPI()
    app.include_router(gateway_router)

    def _db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _db
    # enable server key
    raw = "test-sync-key-async-xyz"
    db.add(
        EnvSyncServerConfig(
            id=1, enabled=True, sync_key_hash=hash_sync_key(raw), key_hint="test"
        )
    )
    db.commit()
    client = TestClient(app)
    client.sync_key = raw  # type: ignore
    return client


def test_gateway_export_job_requires_key(gateway_client):
    r = gateway_client.post("/api/env-sync/v1/jobs/export", json={"modules": ["gms_strategy_configs"]})
    assert r.status_code == 401


def test_gateway_export_job_and_part_download(gateway_client, db, tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_SYNC_ARTIFACT_ROOT", str(tmp_path))
    key = gateway_client.sync_key  # type: ignore

    with patch(
        "backend_api.env_sync.admin_routes.start_thread",
        side_effect=lambda target, *, name: None,
    ), patch(
        "backend_api.env_sync.gateway_routes.start_thread",
        side_effect=lambda target, *, name: None,
    ), patch(
        "backend_api.env_sync.part_io.export_modules",
        return_value={
            "modules": ["gms_strategy_configs"],
            "bundles": {
                "strategy_configs": {
                    "module": "strategy_configs",
                    "items": {"gms_strategy_configs": [{"id": 1}]},
                }
            },
        },
    ), patch(
        "backend_api.env_sync.job_runner.SessionLocal",
        TestingSessionLocal,
    ):
        r = gateway_client.post(
            "/api/env-sync/v1/jobs/export",
            json={"modules": ["gms_strategy_configs"]},
            headers={"X-Env-Sync-Key": key},
        )
        assert r.status_code == 200, r.text
        job_id = r.json()["job_id"]

        from backend_api.env_sync.job_runner import run_server_export_job

        run_server_export_job(job_id)

    st = gateway_client.get(
        f"/api/env-sync/v1/jobs/{job_id}",
        headers={"X-Env-Sync-Key": key},
    )
    assert st.status_code == 200
    body = st.json()
    assert body["status"] == "succeeded", body
    parts = ((body.get("summary") or {}).get("manifest") or {}).get("parts") or []
    assert parts
    name = parts[0]["name"]
    dl = gateway_client.get(
        f"/api/env-sync/v1/jobs/{job_id}/parts/{name}",
        headers={"X-Env-Sync-Key": key},
    )
    assert dl.status_code == 200
    assert dl.content[:2] == b"\x1f\x8b"  # gzip magic


@pytest.fixture
def admin_client(db, admin_user):
    app = FastAPI()
    app.include_router(admin_router)

    def _db():
        try:
            yield db
        finally:
            pass

    def _admin():
        return admin_user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_admin] = _admin
    return TestClient(app)


def test_admin_async_push_accepted(admin_client, db, monkeypatch):
    from backend_api.models import EnvSyncClientConfig

    db.add(
        EnvSyncClientConfig(
            id=1,
            enabled=True,
            prod_base_url="https://example.invalid",
            sync_key="k",
        )
    )
    db.commit()

    started = []

    def fake_start(target, *, name):
        started.append(name)

    with patch("backend_api.env_sync.admin_routes.start_thread", side_effect=fake_start):
        r = admin_client.post(
            "/api/admin/env-sync/jobs/push",
            json={"modules": ["gms_strategy_configs"]},
        )
    assert r.status_code == 200, r.text
    assert "job_id" in r.json()
    assert started
