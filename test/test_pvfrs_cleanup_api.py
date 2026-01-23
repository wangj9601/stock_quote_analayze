"""
PVFRS 清理/删除接口验证脚本

注意：
- 需要先启动后端服务（例如 http://localhost:5000 或 8000）
- 该脚本不会自动启动服务，仅用于手工验证接口是否可用
"""

import os
import requests


def _base_url() -> str:
    return os.environ.get("PVFRS_BASE_URL", "http://localhost:5000")


def main():
    base = _base_url().rstrip("/")
    print(f"Base URL: {base}")

    # 1) 列出任务（用于确认有无数据）
    print("\n1) GET /api/admin/pvfrs/backtest/tasks")
    r = requests.get(f"{base}/api/admin/pvfrs/backtest/tasks", params={"page": 1, "pageSize": 5})
    print("status:", r.status_code)
    print(r.text[:500])

    # 2) 列出报告
    print("\n2) GET /api/admin/pvfrs/reports")
    r = requests.get(f"{base}/api/admin/pvfrs/reports", params={"page": 1, "pageSize": 5})
    print("status:", r.status_code)
    print(r.text[:500])

    # 3) 危险操作示例（默认不执行，避免误删）
    print("\n3) 危险操作接口（默认不执行）")
    print("- DELETE /api/admin/pvfrs/backtest/tasks/completed   # 清理已完成任务(级联删结果/交易/曲线)")
    print("- DELETE /api/admin/pvfrs/backtest/tasks/{task_id}   # 删除单个任务(级联)")
    print("- DELETE /api/admin/pvfrs/backtest/tasks?confirm=true  # 删除全部任务/报告等相关数据(清库)")
    print("- DELETE /api/admin/pvfrs/reports/{report_id}        # 删除单个报告(级联删结果/交易/曲线)")
    print("- DELETE /api/admin/pvfrs/reports?confirm=true       # 清空全部报告(不删任务)")

    print("\n如果要在脚本里执行危险操作，请自行取消注释并确保指向正确环境。")


if __name__ == "__main__":
    main()

