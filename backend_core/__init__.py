#backend_core包
#供股票分析系统的核心功能

import subprocess
import sys


def start_collector_process():
    """拉起定时采集。必须用当前解释器，不能走 PATH 上的 `python`。

    Ubuntu 公网机没有 `python` 命令，`os.system('python -m ...')` 会立刻
    `python: not found`，主进程却继续 sleep，systemd 仍显示 active。
    """
    return subprocess.Popen(
        [sys.executable, "-m", "backend_core.data_collectors.main"],
    )


__version__ = '0.1.0'
