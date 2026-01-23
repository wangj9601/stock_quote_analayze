"""
PVFRS 报告PDF导出接口验证脚本

说明：
- 需要先启动后端服务
- 默认 base_url=http://localhost:5000，可通过环境变量 PVFRS_BASE_URL 覆盖
- 该脚本会调用导出PDF接口，并检查返回内容是否以 %PDF 开头
"""

import os
import sys
import requests


def _base_url() -> str:
    return os.environ.get("PVFRS_BASE_URL", "http://localhost:5000").rstrip("/")


def main():
    base = _base_url()
    report_id = os.environ.get("PVFRS_REPORT_ID")
    if not report_id:
        print("请先设置环境变量 PVFRS_REPORT_ID=你的report_id（例如 report_xxx_yyy）")
        sys.exit(1)

    url = f"{base}/api/admin/pvfrs/reports/{report_id}/download/pdf"
    print("GET", url)
    r = requests.get(url)
    print("status:", r.status_code)
    if r.status_code != 200:
        print(r.text[:500])
        sys.exit(2)

    content = r.content
    if not content.startswith(b"%PDF"):
        print("❌ 返回内容不是PDF（未以 %PDF 开头）")
        print("前100字节:", content[:100])
        sys.exit(3)

    out = f"pvfrs_report_{report_id}.pdf"
    with open(out, "wb") as f:
        f.write(content)
    print("✅ PDF导出成功，已保存到:", out)


if __name__ == "__main__":
    main()

