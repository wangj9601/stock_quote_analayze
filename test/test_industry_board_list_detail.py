# -*- coding: utf-8 -*-
"""行业板行情列表 / 详情（含批量斜率）单元测试。"""

import json
from datetime import date, datetime
from types import SimpleNamespace

from backend_core.strategies.gms.board_resonance import evaluate_board_weak_judgment


def test_evaluate_board_weak_judgment_summary():
    from backend_core.strategies.gms.board_resonance import evaluate_board_environment

    weak = evaluate_board_weak_judgment(sector_slope_v=-0.01, board_change_percent=2.0)
    assert weak["board_weak"] is True
    assert weak["board_strong"] is False
    assert weak["board_env"] == "weak"
    assert weak["board_weak_reason"] == "sector_slope_negative"
    assert "斜率" in weak["board_weak_summary"]

    strong = evaluate_board_environment(
        sector_slope_v=0.0015, board_change_percent=-1.0
    )
    assert strong["board_strong"] is True
    assert strong["board_weak"] is False
    assert strong["board_env"] == "strong"
    assert strong["board_env_label"] == "走强"

    neutral = evaluate_board_environment(
        sector_slope_v=0.0003, board_change_percent=1.0
    )
    assert neutral["board_env"] == "neutral"
    assert neutral["board_strong"] is False

    fallback = evaluate_board_weak_judgment(
        sector_slope_v=None, board_change_percent=-1.5
    )
    assert fallback["board_weak"] is True
    assert fallback["board_strong"] is False
    assert fallback["board_weak_reason"] == "realtime_change_negative"
    assert "实时涨跌" in fallback["board_weak_summary"]


def test_looks_like_board_index_price():
    from backend_api.utils import industry_board_query as q

    assert q.looks_like_board_index_price(1628.37, -36.14) is True
    assert q.looks_like_board_index_price(31.34, None) is False
    assert q.looks_like_board_index_price(82.81, None) is False
    # 少数低点位但带涨跌额，仍视为东财指数行
    assert q.looks_like_board_index_price(88.5, 1.2) is True


def test_quote_fields_strip_avg_price_as_index():
    """均价残留不得作为指数字段返回。"""
    from backend_api.utils import industry_board_query as q

    fields = q._quote_fields_from_row(
        {
            "board_code": "BK0727",
            "latest_price": 31.34,
            "change_amount": None,
            "change_percent": 8.34,
        }
    )
    assert fields.get("latest_price") is None
    assert fields.get("change_percent") == 8.34


def test_prefer_board_quote_picks_index_over_avg_price():
    """同花顺代码下若误存均价，应优先选用同名东财指数行情。"""
    from backend_api.utils import industry_board_query as q

    avg_like = {
        "latest_price": 82.81,
        "change_amount": None,
        "change_percent": 3.37,
        "quote_board_code": "881121",
    }
    index_like = {
        "latest_price": 1628.37,
        "change_amount": -36.14,
        "change_percent": -2.17,
        "quote_board_code": "BK1036",
    }
    picked = q._prefer_board_quote(avg_like, index_like)
    assert picked["latest_price"] == 1628.37
    assert picked["change_amount"] == -36.14
    only_avg = q._prefer_board_quote(avg_like, None)
    assert q.looks_like_board_index_price(
        only_avg.get("latest_price"), only_avg.get("change_amount")
    ) is False


def test_fetch_industry_board_list_with_metrics_merges_quote_and_slope(monkeypatch):
    from backend_api.utils import industry_board_query as q

    catalog = [
        {
            "board_code": "881101",
            "board_name": "半导体",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 128,
            "member_count": 128,
        },
        {
            "board_code": "881102",
            "board_name": "银行",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 40,
            "member_count": 40,
        },
    ]
    monkeypatch.setattr(
        q,
        "fetch_industry_board_catalog",
        lambda db, **kwargs: catalog,
    )
    monkeypatch.setattr(
        q,
        "_load_industry_realtime_quote_indexes",
        lambda db: (
            {},
            {
                "半导体": {
                    "change_percent": 3.5,
                    "amount": 1.2e10,
                    "latest_price": 1200.0,
                    "quote_board_code": "BK0477",
                }
            },
        ),
    )

    class _FakeSlopeStore:
        @staticmethod
        def load_board_sector_slopes(db, codes, board_kind="industry"):
            assert "881101" in codes
            return {
                "881101": {
                    "sector_slope": -0.012345,
                    "sector_slope_window": 60,
                    "slope_asof_date": date(2026, 8, 7),
                    "member_count_used": 100,
                }
            }

    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        _FakeSlopeStore.load_board_sector_slopes,
    )

    out = q.fetch_industry_board_list_with_metrics(SimpleNamespace(), board_code_source="tonghuashun")
    assert len(out) == 2
    by_code = {x["board_code"]: x for x in out}
    semi = by_code["881101"]
    assert semi["change_percent"] == 3.5
    assert semi["latest_price"] == 1200.0  # 板块指数点位（非均价）
    assert semi["sector_slope"] == -0.012345
    assert semi["slope_asof_date"] == "2026-08-07"
    assert semi["member_count_used"] == 100
    assert semi["member_count"] == 128
    bank = by_code["881102"]
    assert bank["sector_slope"] is None
    assert bank.get("change_percent") is None
    # 有斜率的板排在无斜率之前（走强优先；本例为走弱但有斜率）
    assert out[0]["board_code"] == "881101"


def test_industry_board_list_sorts_strong_before_weak(monkeypatch):
    """列表默认：走强优先，同档内斜率降序。"""
    from backend_api.utils import industry_board_query as q

    catalog = [
        {
            "board_code": "881A",
            "board_name": "弱板高涨幅",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 10,
            "member_count": 10,
        },
        {
            "board_code": "881B",
            "board_name": "强板",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 10,
            "member_count": 10,
        },
        {
            "board_code": "881C",
            "board_name": "更强板",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 10,
            "member_count": 10,
        },
    ]
    monkeypatch.setattr(q, "fetch_industry_board_catalog", lambda db, **kwargs: catalog)
    monkeypatch.setattr(
        q,
        "_load_industry_realtime_quote_indexes",
        lambda db: (
            {
                "881A": {"change_percent": 5.0, "amount": 1e9, "latest_price": 100.0},
                "881B": {"change_percent": 1.0, "amount": 1e9, "latest_price": 100.0},
                "881C": {"change_percent": 0.5, "amount": 1e9, "latest_price": 100.0},
            },
            {},
        ),
    )

    def _slopes(db, codes, board_kind="industry"):
        return {
            "881A": {"sector_slope": -0.0049, "sector_slope_window": 60},
            "881B": {"sector_slope": 0.0080, "sector_slope_window": 60},
            "881C": {"sector_slope": 0.0100, "sector_slope_window": 60},
        }

    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        _slopes,
    )

    out = q.fetch_industry_board_list_with_metrics(SimpleNamespace(), board_code_source="tonghuashun")
    assert [x["board_code"] for x in out] == ["881C", "881B", "881A"]
    assert out[0]["board_env"] == "strong"
    assert out[1]["board_env"] == "strong"
    assert out[2]["board_env"] == "weak"


def test_fetch_industry_board_detail_weak_and_roles(monkeypatch):
    from backend_api.utils import industry_board_query as q

    monkeypatch.setattr(
        q,
        "resolve_board_for_roles",
        lambda db, btype, code, board_code_source=None, board_name=None: {
            "board_type": "industry",
            "board_code": "881101",
            "board_name": "半导体",
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
        },
    )
    monkeypatch.setattr(
        q,
        "_load_industry_realtime_quote_indexes",
        lambda db: (
            {"881101": {"change_percent": -1.2, "amount": 100.0, "latest_price": 10.0}},
            {},
        ),
    )

    class _DB:
        def execute(self, sql, params=None):
            return SimpleNamespace(fetchone=lambda: (88,))

    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        lambda db, codes, board_kind="industry": {
            "881101": {
                "sector_slope": None,
                "sector_slope_window": 60,
                "slope_asof_date": None,
                "member_count_used": None,
            }
        },
    )
    # 本用例验证「有涨跌、无斜率」时的走弱回退；关闭详情现算以免改写斜率字段
    monkeypatch.setattr(
        "backend_core.board_roles.service.fetch_board_roles_payload",
        lambda *a, **k: {"ok": True},
    )
    # 与 extract_leader_mid_from_payload 真实返回形状一致（leaders/mids 列表）
    monkeypatch.setattr(
        "backend_core.board_roles.service.extract_leader_mid_from_payload",
        lambda payload: {
            "leaders": [
                {"code": "688981", "name": "中芯国际", "change_percent": 2.0},
                {"code": "688012", "name": "中微公司", "change_percent": 1.5},
            ],
            "mids": [
                {"code": "603501", "name": "韦尔股份", "change_percent": 1.0},
            ],
            "board_change_percent_est": -0.8,
        },
    )

    detail = q.fetch_industry_board_detail(
        _DB(), "881101", include_roles=True, compute_slope_if_missing=False
    )
    assert detail is not None
    assert detail["board_code"] == "881101"
    assert detail["member_count"] == 88
    assert detail["board_weak"] is True
    assert detail["board_weak_reason"] == "realtime_change_negative"
    assert "实时涨跌" in detail["board_weak_summary"]
    assert [x["code"] for x in detail["leaders"]] == ["688981", "688012"]
    assert [x["code"] for x in detail["mids"]] == ["603501"]
    # 兼容字段：首条龙头/中军
    assert detail["leader"]["code"] == "688981"
    assert detail["mid"]["name"] == "韦尔股份"
    assert detail["roles"]["leaders"][0]["code"] == "688981"
    assert detail.get("slope_filled_on_demand") is False


def test_fetch_industry_board_detail_maps_leaders_mids_from_real_extract(monkeypatch):
    """回归：详情须把 extract 的 leaders/mids 列表落到顶层，而非错误读 leader/mid。"""
    from backend_api.utils import industry_board_query as q
    from backend_core.board_roles.classify import ROLE_LEADER, ROLE_MID
    from backend_core.board_roles.service import extract_leader_mid_from_payload

    monkeypatch.setattr(
        q,
        "resolve_board_for_roles",
        lambda db, btype, code, board_code_source=None, board_name=None: {
            "board_type": "industry",
            "board_code": "881101",
            "board_name": "半导体",
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
        },
    )
    monkeypatch.setattr(
        q,
        "_load_industry_realtime_quote_indexes",
        lambda db: ({"881101": {"change_percent": 0.5}}, {}),
    )

    class _DB:
        def execute(self, sql, params=None):
            return SimpleNamespace(fetchone=lambda: (10,))

    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        lambda db, codes, board_kind="industry": {
            "881101": {"sector_slope": 0.01, "sector_slope_window": 60}
        },
    )
    monkeypatch.setattr(
        "backend_core.board_roles.service.fetch_board_roles_payload",
        lambda *a, **k: {
            "board_code": "881101",
            "board_name": "半导体",
            "board_code_source": "tonghuashun",
            "board_change_percent_est": 1.2,
            "stocks": [
                {
                    "code": "688981",
                    "name": "中芯国际",
                    "change_percent": 2.0,
                    "board_role": ROLE_LEADER,
                    "board_role_score": 90,
                },
                {
                    "code": "688012",
                    "name": "中微公司",
                    "change_percent": 1.8,
                    "board_role": ROLE_LEADER,
                    "board_role_score": 85,
                },
                {
                    "code": "603501",
                    "name": "韦尔股份",
                    "change_percent": 1.0,
                    "board_role": ROLE_MID,
                    "board_role_score": 80,
                },
                {
                    "code": "002371",
                    "name": "北方华创",
                    "change_percent": 0.9,
                    "board_role": ROLE_MID,
                    "board_role_score": 75,
                },
                {
                    "code": "600584",
                    "name": "长电科技",
                    "change_percent": 0.8,
                    "board_role": ROLE_MID,
                    "board_role_score": 70,
                },
            ],
        },
    )
    # 故意不 mock extract：确保与生产同一函数形状对接
    monkeypatch.setattr(
        "backend_core.board_roles.service.extract_leader_mid_from_payload",
        extract_leader_mid_from_payload,
    )

    detail = q.fetch_industry_board_detail(
        _DB(), "881101", include_roles=True, compute_slope_if_missing=False
    )
    # 有几只透传几只，不得截成只返回第一只
    assert [x["code"] for x in detail["leaders"]] == ["688981", "688012"]
    assert [x["code"] for x in detail["mids"]] == ["603501", "002371", "600584"]
    assert len(detail["leaders"]) == 2
    assert len(detail["mids"]) == 3
    assert detail["leader"]["name"] == "中芯国际"
    assert detail["mid"]["name"] == "韦尔股份"
    assert detail["board_change_percent_est"] == 1.2


def test_fetch_industry_board_detail_computes_and_stores_missing_slope(monkeypatch):
    """详情打开时若库无斜率：现算全成分并 upsert，再返回数值。"""
    from backend_api.utils import industry_board_query as q

    monkeypatch.setattr(
        q,
        "resolve_board_for_roles",
        lambda db, btype, code, board_code_source=None, board_name=None: {
            "board_type": "industry",
            "board_code": "881101",
            "board_name": "半导体",
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
        },
    )
    monkeypatch.setattr(
        q,
        "_load_industry_realtime_quote_indexes",
        lambda db: ({"881101": {"change_percent": 1.0}}, {}),
    )

    class _DB:
        def execute(self, sql, params=None):
            return SimpleNamespace(fetchone=lambda: (50,))

        def rollback(self):
            pass

    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        lambda db, codes, board_kind="industry": {},
    )
    called = {}

    def _ensure(db, code, **kwargs):
        called["code"] = code
        called["kwargs"] = kwargs
        return {
            "sector_slope": 0.0123,
            "sector_slope_window": 60,
            "slope_asof_date": date(2026, 8, 7),
            "member_count_used": 48,
        }

    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.ensure_board_sector_slope",
        _ensure,
    )
    monkeypatch.setattr(
        "backend_core.board_roles.service.fetch_board_roles_payload",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        "backend_core.board_roles.service.extract_leader_mid_from_payload",
        lambda payload: {"leaders": [], "mids": []},
    )

    detail = q.fetch_industry_board_detail(_DB(), "881101", include_roles=False)
    assert called["code"] == "881101"
    assert called["kwargs"].get("commit") is True
    assert detail["sector_slope"] == 0.0123
    assert detail["slope_asof_date"] == "2026-08-07"
    assert detail["member_count_used"] == 48
    assert detail["slope_filled_on_demand"] is True
    assert detail["board_weak"] is False
    assert detail["board_strong"] is True
    assert detail["board_env"] == "strong"
    assert detail["board_weak_reason"] == "sector_slope_strong"
    assert detail["leaders"] == []
    assert detail["mids"] == []
    assert detail["leader"] is None
    assert detail["mid"] is None


def test_fetch_industry_board_catalog_source_filter_sql():
    from backend_api.utils.industry_board_query import fetch_industry_board_catalog

    seen = {}

    class _DB:
        def execute(self, sql, params=None):
            seen["sql"] = str(sql)
            seen["params"] = params
            return SimpleNamespace(fetchall=lambda: [])

    out = fetch_industry_board_catalog(_DB(), board_code_source="tonghuashun")
    assert out == []
    assert "board_code_source" in seen["sql"]
    assert seen["params"]["source"] == "tonghuashun"


def test_quote_fields_serialize_datetime_for_json():
    """realtime_quotes.update_time 常为 datetime，须先转字符串再走 JSONResponse。"""
    from backend_api.utils.industry_board_query import _quote_fields_from_row

    row = {
        "board_code": "BK0477",
        "change_percent": 1.5,
        "update_time": datetime(2026, 8, 7, 20, 1, 1),
    }
    fields = _quote_fields_from_row(row)
    assert fields["update_time"] == "2026-08-07 20:01:01"
    assert isinstance(fields["update_time"], str)
    json.dumps(fields)  # 不应抛 TypeError


def test_list_with_metrics_degrades_when_slope_load_fails(monkeypatch):
    """斜率读库失败（缺表/事务 abort）时仍返回板列表，斜率为 null。"""
    from backend_api.utils import industry_board_query as q

    catalog = [
        {
            "board_code": "881101",
            "board_name": "半导体",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 10,
            "member_count": 10,
        }
    ]
    monkeypatch.setattr(q, "fetch_industry_board_catalog", lambda db, **kwargs: catalog)
    monkeypatch.setattr(
        q,
        "_load_industry_realtime_quote_indexes",
        lambda db: (
            {
                "881101": {
                    "change_percent": 2.0,
                    "update_time": "2026-08-07 20:01:01",
                }
            },
            {},
        ),
    )

    class _DB:
        def rollback(self):
            self.rolled_back = True

    db = _DB()

    def _boom(*_a, **_k):
        raise RuntimeError("relation \"industry_board_daily_metrics\" does not exist")

    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        _boom,
    )

    out = q.fetch_industry_board_list_with_metrics(db, board_code_source="tonghuashun")
    assert len(out) == 1
    assert out[0]["board_code"] == "881101"
    assert out[0]["change_percent"] == 2.0
    assert out[0]["sector_slope"] is None
    assert out[0]["slope_asof_date"] is None
    assert getattr(db, "rolled_back", False) is True
    json.dumps(out)


def test_list_with_metrics_empty_slopes_still_json_safe(monkeypatch):
    """空斜率字典时字段齐全且可 JSON 序列化。"""
    from backend_api.utils import industry_board_query as q

    catalog = [
        {
            "board_code": "881102",
            "board_name": "银行",
            "trade_observe_flag": False,
            "board_code_source": "tonghuashun",
            "board_code_source_label": "同花顺",
            "stock_count": 40,
            "member_count": 40,
        }
    ]
    monkeypatch.setattr(q, "fetch_industry_board_catalog", lambda db, **kwargs: catalog)
    monkeypatch.setattr(
        q,
        "_load_industry_realtime_quote_indexes",
        lambda db: (
            {},
            {
                "银行": {
                    "change_percent": -0.5,
                    "update_time": "2026-08-07 15:30:00",
                }
            },
        ),
    )
    monkeypatch.setattr(
        "backend_core.board_metrics.sector_slope_store.load_board_sector_slopes",
        lambda *a, **k: {},
    )

    out = q.fetch_industry_board_list_with_metrics(
        SimpleNamespace(), board_code_source="tonghuashun"
    )
    assert len(out) == 1
    assert out[0]["sector_slope"] is None
    assert out[0]["member_count_used"] is None
    json.dumps(out)
