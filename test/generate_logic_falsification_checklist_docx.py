#!/usr/bin/env python3
"""生成逻辑证伪应对系统股票交易执行清单 Word 文档（无章节编号）。"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MD = PROJECT_ROOT / "docs" / "逻辑证伪应对系统_股票交易执行清单.md"
OUT = PROJECT_ROOT / "exported_docs" / "逻辑证伪应对系统_股票交易执行清单.docx"


def main() -> int:
    if not MD.is_file():
        print(f"[失败] 找不到源文件: {MD}")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "pandoc",
        str(MD),
        "-o",
        str(OUT),
        "--toc",
        "--toc-depth=3",
    ]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("[失败] 未找到 pandoc，请先安装: https://pandoc.org/installing.html")
        return 1
    except subprocess.CalledProcessError as e:
        print(f"[失败] 导出失败: {e}")
        print("若提示 permission denied，请先关闭已打开的 Word 文档后重试。")
        return 1

    print(f"[OK] 已生成: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
