"""
backend_api 独立启动脚本
可直接运行，自动初始化数据库，支持热重载

数据库初始化走项目根部的 `init_db.py`（Alembic 统一入口）：
  * 空库   → create_all + 历史脚本 + stamp 基线 + upgrade head
  * 已纳管 → upgrade head（只补未执行的 revision）
  * 既有库未纳管 → 仅 stamp 基线，不执行 DDL

设 `SKIP_DB_INIT=1` 可跳过初始化（例如库由外部流程单独管理时）。
"""

import os
import sys
from pathlib import Path

import uvicorn

# 项目根入 sys.path，使 `backend_api.main:app` 与根部 `init_db` 都能解析
# （原实现插入的是 backend_api/ 自身，只有 cwd 恰为根目录时才碰巧可用）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "backend_api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def init_db() -> bool:
    """引导数据库（委托给根部 ``init_db.py``）。

    历史问题：这里原本是 ``from backend_api.database import init_db``，
    但 ``backend_api/database.py`` 里**并没有** ``init_db``，于是
    ImportError 一路走到 ``except`` 兜底的空函数——数据库其实从未被初始化。
    """
    try:
        import init_db as init_db_module
    except ImportError as exc:
        print(f"❌ 无法导入根部 init_db 模块: {exc}")
        return False

    rc = init_db_module.main(["--yes"])
    if rc != 0:
        print(f"❌ 数据库引导失败（退出码 {rc}），详见 logs/init_db.log")
        return False
    return True


def main() -> None:
    print("=" * 50)
    print("📈 backend_api 独立服务启动")
    print("=" * 50)

    print("🔍 检查依赖包...")
    try:
        import akshare  # noqa: F401
        import fastapi  # noqa: F401
        import pandas  # noqa: F401
        import sqlalchemy  # noqa: F401

        print("✅ 依赖包检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r backend_api/requirements-minimal.txt")
        print("（部署/生产与 release 一致请用: pip install -r requirements-prod.txt）")
        return

    if (os.getenv("SKIP_DB_INIT") or "").strip().lower() in ("1", "true", "yes"):
        print("\n💾 已按 SKIP_DB_INIT 跳过数据库初始化。")
    else:
        print("\n💾 初始化数据库（Alembic 统一入口）...")
        if not init_db():
            return

    print("\n🚀 启动 backend_api 服务...")
    print("📱 API地址: http://localhost:5000")
    print("📚 API文档: http://localhost:5000/docs")
    print("=" * 50)
    print("按 Ctrl+C 停止服务")
    print("=" * 50)

    uvicorn.run(
        "backend_api.main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        # 含 backend_core：采集/指标逻辑在此；排除 test/admin，避免误 reload 打断任务
        reload_dirs=[
            str(PROJECT_ROOT / "backend_api"),
            str(PROJECT_ROOT / "backend_core"),
        ],
        reload_excludes=["*.xls", "*.xlsx", "*.csv", "*.pyc", "*__pycache__*"],
    )


if __name__ == "__main__":
    main()
