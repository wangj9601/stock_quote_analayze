"""
backend_api 独立启动脚本
可直接运行，自动初始化数据库，支持热重载
"""

import uvicorn
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入数据库初始化函数
try:
    from backend_api.database import init_db
except ImportError:
    def init_db():
        print("[警告] 未找到 init_db，跳过数据库初始化。")


def main():
    print("=" * 50)
    print("📈 backend_api 独立服务启动")
    print("=" * 50)
    print("🔍 检查依赖包...")
    try:
        import fastapi
        import sqlalchemy
        import akshare
        import pandas
        print("✅ 依赖包检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r backend_api/requirements-minimal.txt")
        print("（部署/生产与 release 一致请用: pip install -r requirements-prod.txt）")
        return

    print("\n💾 初始化数据库...")
    try:
        init_db()
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
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
        reload_dirs=[str(Path(__file__).parent.resolve())]
    )

if __name__ == "__main__":
    main() 