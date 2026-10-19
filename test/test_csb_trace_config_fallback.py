# -*- coding: utf-8 -*-
"""历史追溯：请求了不存在的参数版本时改用默认版本。"""

from unittest.mock import MagicMock

from backend_api.stock.csb_frontend_routes import _resolve_config_id


def _db_with_default(config_id=3):
    row = MagicMock()
    row.id = config_id
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
    return db


def test_unknown_config_id_falls_back_to_default():
    cm = MagicMock()
    cm.get_config_row.return_value = None
    cid, warning = _resolve_config_id(_db_with_default(3), cm, 600863)
    assert cid == 3
    assert warning is not None
    assert "600863" in warning
    cm.ensure_default_row.assert_called_once()


def test_known_config_id_is_kept():
    cm = MagicMock()
    cm.get_config_row.return_value = MagicMock()
    cid, warning = _resolve_config_id(MagicMock(), cm, 7)
    assert cid == 7
    assert warning is None
