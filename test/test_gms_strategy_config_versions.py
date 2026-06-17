"""GMS 策略参数多版本管理单元测试"""

import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_core.strategies.gms.config import GMSConfigManager


class TestGMSConfigManagerMultiVersion:
    def test_get_default_config_structure(self):
        cfg = GMSConfigManager().get_default_config()
        assert "left_buy" in cfg
        assert "scoring" in cfg
        assert "exit" in cfg

    def test_deep_merge_preserves_nested(self):
        mgr = GMSConfigManager()
        base = mgr.get_default_config()
        merged = mgr._deep_merge(base, {"left_buy": {"ratio_d20_abs_max": 0.02}})
        assert merged["left_buy"]["ratio_d20_abs_max"] == 0.02
        assert merged["left_buy"]["volume_ratio_max"] == base["left_buy"]["volume_ratio_max"]

    def test_compare_configs_detects_diff(self):
        mgr = GMSConfigManager()
        a = mgr.get_default_config()
        b = copy.deepcopy(a)
        b["left_buy"]["ratio_d20_abs_max"] = 0.99
        monkey_a = lambda cid=None: a
        monkey_b = lambda cid=None: b
        orig_get = mgr.get_config
        calls = {"n": 0}

        def fake_get(cid=None):
            calls["n"] += 1
            return a if calls["n"] == 1 else b

        mgr.get_config = fake_get  # type: ignore
        try:
            result = mgr.compare_configs(1, 2)
            paths = [d["path"] for d in result["diffs"]]
            assert "left_buy.ratio_d20_abs_max" in paths
        finally:
            mgr.get_config = orig_get

    def test_config_to_flat_form_roundtrip_keys(self):
        mgr = GMSConfigManager()
        cfg = mgr.get_default_config()
        cfg["scoring"]["weight_acc_fz"] = 31
        flat = mgr.config_to_flat_form(cfg)
        assert flat["weight_acc_fz"] == 31
        assert flat["ratio_d20_max"] == cfg["left_buy"]["ratio_d20_abs_max"]
        patch = mgr.flat_form_to_config_patch(flat)
        assert patch["scoring"]["weight_acc_fz"] == 31

    def test_should_use_trace_logic_without_db(self, monkeypatch):
        mgr = GMSConfigManager()

        class _Row:
            is_default = True
            precompute_enabled = False

        class _FakeQuery:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return _Row()

        class _FakeDb:
            def query(self, model):
                return _FakeQuery()

            def close(self):
                pass

        monkeypatch.setattr(mgr, "_session", lambda: _FakeDb())
        monkeypatch.setattr(mgr, "resolve_config_id", lambda cid=None: 1)
        assert mgr.should_use_trace(1) is True


@pytest.mark.skipif(
    os.getenv("SKIP_DB_TESTS", "").lower() in ("1", "true", "yes"),
    reason="需要 PostgreSQL 连接",
)
class TestGMSStrategyConfigApi:
    def test_list_strategy_configs_endpoint(self):
        from fastapi.testclient import TestClient
        from backend_api.main import app

        client = TestClient(app)
        res = client.get("/api/admin/gms/strategy-configs")
        if res.status_code == 401:
            pytest.skip("需要管理员认证")
        assert res.status_code in (200, 401, 403)
        if res.status_code == 200:
            body = res.json()
            assert body.get("success") is True
            assert isinstance(body.get("data"), list)
