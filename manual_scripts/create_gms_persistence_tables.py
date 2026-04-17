#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建 GMS 运行时配置与回测任务表（gms_runtime_config、gms_backtest_tasks）。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend_api.database import engine  # noqa: E402
from backend_api.models import Base, GMSRuntimeConfig, GMSBacktestTask  # noqa: E402


def main():
    Base.metadata.create_all(
        bind=engine,
        tables=[GMSRuntimeConfig.__table__, GMSBacktestTask.__table__],
    )
    print("OK: gms_runtime_config, gms_backtest_tasks")


if __name__ == "__main__":
    main()
