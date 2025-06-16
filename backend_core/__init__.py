#backend_core包
#供股票分析系统的核心功能

import multiprocessing
import os

def _run_collector_main():
    os.system('python -m backend_core.data_collectors.main')

def start_collector_process():
    multiprocessing.set_start_method('spawn', force=True)
    p = multiprocessing.Process(target=_run_collector_main)
    p.daemon = True
    p.start()
    return p

__version__ = '0.1.0' 