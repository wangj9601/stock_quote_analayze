"""
启动脚本
用于运行 backend_core 定时采集服务
"""

import sys

# 须在任何 print / 其它 import 之前：NSSM 重定向下 stdout 默认 GBK，首行输出含非 GBK 字符会崩在 UTF-8 初始化之前。
if sys.platform == "win32":
    for _boot_stream in (sys.stdout, sys.stderr):
        _boot_fn = getattr(_boot_stream, "reconfigure", None)
        if callable(_boot_fn):
            try:
                _boot_fn(encoding="utf-8", errors="replace")
            except Exception:
                pass

import os


def _reconfigure_stdio_utf8() -> None:
    """NSSM 服务下 stdout 常为 GBK；优先设为 UTF-8，避免 print 含符号时崩溃。"""
    if sys.platform != "win32":
        return
    for _stream in (sys.stdout, sys.stderr):
        _fn = getattr(_stream, "reconfigure", None)
        if callable(_fn):
            try:
                _fn(encoding="utf-8", errors="replace")
            except Exception:
                pass


# 须在 main() 之前执行：旧版若仍有 emoji print，先切 UTF-8 可避免进程首行即崩。
_reconfigure_stdio_utf8()


def main():
    _reconfigure_stdio_utf8()
    # Windows 服务/NSSM 下 stdout 常为 GBK，勿用 emoji
    print("=" * 50)
    print("[START] backend_core 定时采集服务")
    print("=" * 50)

    # 检查依赖
    print("[CHECK] 检查依赖包...")
    try:
        import apscheduler
        import akshare
        import tushare
        import pandas
        print("[OK] 依赖包检查通过")
    except ImportError as e:
        print(f"[ERROR] 缺少依赖包: {e}")
        print("请运行: pip install -r backend_core/requirements-minimal.txt")
        print("（部署/生产与 release 一致请用: pip install -r requirements-prod.txt）")
        print("若需机器学习等完整依赖: pip install -r backend_core/requirements.txt")
        return

    # 启动 backend_core（自动拉起定时采集进程）
    print("\n[RUN] 启动定时采集进程...")
    try:
        import backend_core
        backend_core.start_collector_process()
        print("[OK] backend_core 已启动，定时采集进程已在后台运行")
        print("如需查看日志，请查看 backend_core/logs/ 目录")
        print("按 Ctrl+C 停止服务")
        print("=" * 50)
        # 阻塞主线程，保持进程存活
        import time
        while True:
            time.sleep(60)
    except Exception as e:
        print(f"[ERROR] 启动 backend_core 失败: {e}")

if __name__ == "__main__":
    main() 