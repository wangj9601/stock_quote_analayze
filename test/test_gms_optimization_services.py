"""GMS 优化相关服务单元测试：快照 scope/hash、trace meta、任务统计。"""

from __future__ import annotations

from backend_api.services.gms_job_tracker import note_screening_request, screening_stats_summary
from backend_api.services.gms_selection_snapshot import (
    build_param_hash,
    build_scope_key,
    enrich_trace_meta,
)


def test_build_scope_key_cn_segment():
    assert build_scope_key("cn", cn_board_segment="MAIN") == "cn:MAIN"
    assert build_scope_key("cn", cn_board_segment="ALL") == "cn"
    assert build_scope_key("industry_board", industry_board_codes=["BK0475", "BK0001"]) == "industry:BK0001,BK0475"


def test_build_param_hash_stable():
    h1 = build_param_hash({"min_score": 60, "exclude_st": True})
    h2 = build_param_hash({"exclude_st": True, "min_score": 60})
    h3 = build_param_hash({"min_score": 60, "exclude_st": False})
    assert h1 == h2
    assert h1 != h3


def test_enrich_trace_meta_cache_layers():
    m = enrich_trace_meta({"requested_count": 100, "from_trace_count": 100})
    assert m["trace_hit_rate"] == 1.0
    assert m["cache_layer"] == "trace"

    m2 = enrich_trace_meta({"requested_count": 10, "from_trace_count": 0, "computed_count": 10, "from_snapshot": True})
    assert m2["cache_layer"] == "snapshot"

    m3 = enrich_trace_meta({"requested_count": 10, "from_trace_count": 5, "computed_count": 5})
    assert m3["cache_layer"] == "mixed"


def test_screening_stats_summary():
    note_screening_request({"requested_count": 100, "from_trace_count": 90})
    note_screening_request({"requested_count": 50, "from_trace_count": 25}, timed_out=True)
    s = screening_stats_summary()
    assert s["request_count"] >= 2
    assert s["timeout_count"] >= 1
    assert s["avg_trace_hit_rate"] is not None
