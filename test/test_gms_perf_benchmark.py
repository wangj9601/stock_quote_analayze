"""
GMS 全 A 股筛选性能基准（轻量）。

默认使用 mock 统计逻辑验证基准脚本结构；设置环境变量 GMS_PERF_LIVE=1 且数据库可用时，
可对单股或小范围 scope 做真实探测（避免 CI 长时间阻塞）。
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import pytest

from backend_api.services.gms_selection_snapshot import enrich_trace_meta


def _simulate_screening_batch(
    total: int,
    trace_hit: int,
    *,
    batch_size: int = 200,
) -> Dict[str, Any]:
    """模拟 trace 命中 + 增量计算，返回与接口 meta 兼容的统计。"""
    t0 = time.perf_counter()
    computed = max(0, total - trace_hit)
    batches = (computed + batch_size - 1) // batch_size if computed else 0
    # 模拟每批少量固定开销
    for _ in range(batches):
        time.sleep(0.001)
    elapsed = time.perf_counter() - t0
    meta = enrich_trace_meta(
        {
            "requested_count": total,
            "from_trace_count": trace_hit,
            "computed_count": computed,
            "batch_size": batch_size,
            "elapsed_sec": round(elapsed, 4),
        }
    )
    return meta


def test_perf_benchmark_trace_high_hit_p95_budget():
    """trace 覆盖率 ≥90% 时，模拟耗时应远低于全量计算预算（30s 验收参考）。"""
    total = 5000
    trace_hit = int(total * 0.92)
    meta = _simulate_screening_batch(total, trace_hit)
    assert meta["trace_hit_rate"] >= 0.9
    assert meta["cache_layer"] in ("trace", "mixed")
    assert float(meta["elapsed_sec"]) < 30.0


def test_perf_benchmark_trace_miss_reports_computed_layer():
    total = 100
    meta = _simulate_screening_batch(total, 0)
    assert meta["trace_hit_rate"] == 0.0
    assert meta["cache_layer"] == "computed"


@pytest.mark.skipif(os.getenv("GMS_PERF_LIVE") != "1", reason="设置 GMS_PERF_LIVE=1 启用真实 DB 探测")
def test_perf_live_db_smoke():
    """可选：真实环境小范围探测（需数据库与 GMS 模块）。"""
    from backend_api.database import SessionLocal
    from backend_core.strategies.gms.config import GMSConfigManager

    db = SessionLocal()
    try:
        mgr = GMSConfigManager()
        config_id = mgr.resolve_config_id(None)
        assert config_id is not None
    finally:
        db.close()
