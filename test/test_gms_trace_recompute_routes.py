"""GMS 信号追溯：强制重算异步任务与进度"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.stock import gms_trace_routes


class TestGmsTraceRecomputeTasks:
    def setup_method(self):
        with gms_trace_routes._trace_recompute_lock:
            gms_trace_routes._trace_recompute_tasks.clear()

    def test_find_running_trace_recompute(self):
        with gms_trace_routes._trace_recompute_lock:
            gms_trace_routes._trace_recompute_tasks["t1"] = {
                "task_id": "t1",
                "status": "running",
                "code": "002106",
                "config_id": 1,
            }
        assert gms_trace_routes._find_running_trace_recompute("002106", 1) == "t1"
        assert gms_trace_routes._find_running_trace_recompute("002106", 2) is None

    def test_get_trace_recompute_task_missing(self):
        assert gms_trace_routes._get_trace_recompute_task("missing") is None

    @patch("backend_api.database.SessionLocal")
    @patch.object(gms_trace_routes, "_compute_gms_trace_for_stock", return_value=3)
    def test_background_task_updates_progress(self, mock_compute, mock_session_local):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        task_id = "test_task_1"
        with gms_trace_routes._trace_recompute_lock:
            gms_trace_routes._trace_recompute_tasks[task_id] = {
                "task_id": task_id,
                "status": "pending",
                "progress": 0,
                "code": "002106",
                "config_id": 1,
            }

        def _fake_compute(db, code, market_type, config, config_id, progress_cb=None):
            if progress_cb:
                progress_cb(2, 4, "正在计算 2026-01-02（2/4）")
            return 3

        mock_compute.side_effect = _fake_compute

        gms_trace_routes._run_trace_recompute_background(
            task_id,
            "002106",
            "CN",
            1,
            {"scoring": {}},
            "default",
        )

        task = gms_trace_routes._get_trace_recompute_task(task_id)
        assert task["status"] == "completed"
        assert task["progress"] == 100
        assert task["saved_count"] == 3
        mock_db.close.assert_called_once()
