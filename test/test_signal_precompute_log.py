# -*- coding: utf-8 -*-
"""采集流程里，信号预计算节点要把生成条数写进日志。"""

from backend_core.data_collectors.workflow.adapters import exec_cupb_cn, exec_sepa_cn
from backend_core.data_collectors.workflow.context import WorkflowContext
from backend_core.data_collectors.workflow.signal_count import (
    classify_signal_payload,
    pack_signal_runs,
)


def test_single_written_count_is_signal_phrase():
    decision = classify_signal_payload(
        "SEPA买点信号预计算",
        {"success": True, "written": 17},
    )
    assert decision["failed"] is False
    assert decision["signal_count"] == 17
    assert decision["message"] == "SEPA买点信号预计算完成，信号 17 条"


def test_written_and_hits_both_shown_when_they_differ():
    decision = classify_signal_payload(
        "URT信号预计算(A股)",
        {
            "success": True,
            "results": [
                {"success": True, "written": 40, "hits": 8},
                {"success": True, "written": 5, "hits": 1},
            ],
        },
    )
    assert decision["signal_count"] == 45
    assert decision["hits"] == 9
    assert "写入 45 条，买点 9 条" in decision["message"]


def test_saved_and_entry_count():
    decision = classify_signal_payload(
        "SBBR信号预计算",
        {"ok": True, "saved": 12, "entry_count": 3},
    )
    assert decision["signal_count"] == 12
    assert decision["message"] == "SBBR信号预计算完成，写入 12 条，买点 3 条"


def test_same_stored_and_hits_collapse_to_one_number():
    decision = classify_signal_payload(
        "CUPB信号预计算",
        {"ok": True, "saved": 4, "hit_count": 4},
    )
    assert decision["message"] == "CUPB信号预计算完成，信号 4 条"


def test_explicit_failure_keeps_partial_count():
    decision = classify_signal_payload(
        "GMS信号预计算(A股)",
        {
            "success": False,
            "error": "扫描中断",
            "results": [
                {"success": True, "written": 6},
                {"success": False, "error": "扫描中断", "written": 0},
            ],
        },
    )
    assert decision["failed"] is True
    assert decision["signal_count"] == 6
    assert decision["error"] == "扫描中断"
    assert decision["message"] == "GMS信号预计算(A股)失败，信号 6 条"


def test_skip_does_not_look_like_zero_signals():
    decision = classify_signal_payload(
        "CSB信号预计算",
        {"skipped": True, "reason": "周末跳过"},
    )
    assert decision["skipped"] is True
    assert decision["signal_count"] is None
    assert decision["message"] == "CSB信号预计算已跳过：周末跳过"


def test_pack_empty_is_skip_and_pack_sums_children():
    assert pack_signal_runs([])["skipped"] is True
    packed = pack_signal_runs(
        [
            {"success": True, "written": 2, "hits": 1},
            {"success": False, "error": "无行情", "written": 0, "hits": 0},
        ]
    )
    assert packed["success"] is False
    assert packed["error"] == "无行情"
    decision = classify_signal_payload("CSB信号预计算", packed)
    assert decision["signal_count"] == 2
    assert decision["hits"] == 1


def _ctx() -> WorkflowContext:
    return WorkflowContext(run_id="t", workflow_id=1, trigger_source="manual")


def test_cupb_node_log_includes_count(monkeypatch):
    monkeypatch.setattr(
        "backend_core.strategies.cup_bottom.scheduled_precompute.scheduled_cupb_signals_cn",
        lambda: {"ok": True, "saved": 4, "hit_count": 4},
    )
    result = exec_cupb_cn(_ctx())
    assert result.success
    assert result.message == "CUPB信号预计算完成，信号 4 条"
    assert result.data["signal_count"] == 4


def test_sepa_node_log_includes_written(monkeypatch):
    monkeypatch.setattr(
        "backend_core.analysis.sepa.scheduled_precompute.run_sepa_precompute",
        lambda **kwargs: {"success": True, "written": 9, "trade_date": "2026-11-18"},
    )
    result = exec_sepa_cn(_ctx())
    assert result.success
    assert result.message == "SEPA买点信号预计算完成，信号 9 条"
    assert result.data["signal_count"] == 9


def test_failed_precompute_marks_node_failed(monkeypatch):
    monkeypatch.setattr(
        "backend_core.strategies.sbbr.scheduled_precompute.scheduled_sbbr_signals_cn",
        lambda: {"ok": False, "error": "无行情"},
    )
    from backend_core.data_collectors.workflow.adapters import exec_sbbr_cn

    result = exec_sbbr_cn(_ctx())
    assert result.success is False
    assert result.message == "SBBR信号预计算失败"
    assert result.error == "无行情"
