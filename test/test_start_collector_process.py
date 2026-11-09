"""采集进程必须用当前解释器启动，不能调用 PATH 上的 python。"""

from unittest.mock import MagicMock, patch

import backend_core


def test_start_collector_process_uses_current_interpreter():
    popen = MagicMock()
    with patch("backend_core.subprocess.Popen", return_value=popen) as mocked:
        proc = backend_core.start_collector_process()

    assert proc is popen
    mocked.assert_called_once_with(
        [backend_core.sys.executable, "-m", "backend_core.data_collectors.main"],
    )
    args, kwargs = mocked.call_args
    assert kwargs.get("shell", False) is False
    assert "python" not in args[0][1:]
