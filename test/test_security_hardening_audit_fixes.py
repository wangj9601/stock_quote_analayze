# -*- coding: utf-8 -*-
"""已确认安全审计项的加固回归测试（不依赖真实 DB / 网络）。"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 确保导入 backend_api.config 时密钥合法（本文件再单独测拒绝逻辑）
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF",
)
os.environ.setdefault("TESTING", "1")

from backend_api import config as cfg  # noqa: E402
from backend_api import auth  # noqa: E402
from backend_api.permissions import require_permission  # noqa: E402
from backend_api.env_sync.remote_http import assert_url_allowed_for_outbound  # noqa: E402
from backend_core.data_collectors.tushare.historical_import_from_file import (  # noqa: E402
    HistoricalQuoteImportFromFileCollector,
)


def test_jwt_secret_rejects_default(monkeypatch):
    monkeypatch.delenv("ALLOW_INSECURE_DEFAULT_JWT", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "your-secret-key-here")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        cfg._require_jwt_secret()


def test_jwt_secret_accepts_strong(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF",
    )
    assert len(cfg._require_jwt_secret()) >= 32


def test_require_permission_anonymous_401():
    checker = require_permission("channel.analyze.tab.stock_ai")

    async def _run():
        await checker(current_user=None, db=MagicMock())

    with pytest.raises(Exception) as ei:
        asyncio.run(_run())
    assert getattr(ei.value, "status_code", None) == 401


def test_remote_http_blocks_private_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ENV_SYNC_ALLOW_PRIVATE_URLS", raising=False)
    with pytest.raises(ValueError, match="禁止访问"):
        assert_url_allowed_for_outbound("http://127.0.0.1:5000/api")
    with pytest.raises(ValueError, match="禁止访问"):
        assert_url_allowed_for_outbound("http://192.168.1.1/")
    with pytest.raises(ValueError, match="禁止访问"):
        assert_url_allowed_for_outbound("http://10.0.0.5/secret")


def test_remote_http_allows_private_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert_url_allowed_for_outbound("http://127.0.0.1:5000/api")


def test_parse_insert_rejects_other_tables_and_upserts_params():
    c = HistoricalQuoteImportFromFileCollector.__new__(
        HistoricalQuoteImportFromFileCollector
    )
    bad = "INSERT INTO users (id) VALUES (1);"
    assert c._parse_insert_line_to_row(bad) is None

    good = (
        "INSERT INTO mkt_stk_basicinfo (ts_code,trade_date,close) "
        "VALUES ('000001.SZ','20240101',10.5);"
    )
    row = c._parse_insert_line_to_row(good)
    assert row is not None
    assert row["ts_code"] == "000001.SZ"
    assert row["close"] == 10.5

    session = MagicMock()
    assert c._upsert_basicinfo_row(session, row) is True
    args, _kwargs = session.execute.call_args
    sql = str(args[0])
    assert "MKT_STK_BASICINFO" in sql.upper()
    assert args[1]["ts_code"] == "000001.SZ"


def test_create_access_token_has_jti_and_revoke():
    token = auth.create_access_token({"sub": "alice"})
    payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload.get("jti")
    auth.revoke_token_jti(payload["jti"])
    assert auth.is_jti_revoked(payload["jti"])
