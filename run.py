"""
启动脚本
用于运行FastAPI应用
"""

import uvicorn
import os
import sys
from pathlib import Path
import traceback
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入数据库初始化函数
#from backend_api.database import init_db

def main():
    """主函数"""
    print("=" * 50)
    print("📈 股票分析系统后端服务")
    print("=" * 50)
    
    # 检查依赖
    print("🔍 检查依赖包...")
    try:
        import fastapi
        import sqlalchemy
        import akshare
        import pandas
        print("✅ 依赖包检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return
    
    # 已取消数据库初始化操作
    
    
    print("\n🚀 启动服务器...")
    print("📱 API地址: http://localhost:5000")
    print("📚 API文档: http://localhost:5000/docs")
    print("=" * 50)
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    # 启动应用
    uvicorn.run(
        "backend_api.main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,  # 开发模式下启用热重载
        reload_dirs=["backend_api"]  # 指定需要监视的目录
    )

if __name__ == "__main__":
    main() 