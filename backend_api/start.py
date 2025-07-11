#!/usr/bin/env python3
"""
股票分析系统后端启动脚本
"""

import os
import sys
import subprocess
# import sqlite3  # 移除sqlite3

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 7):
        print("错误: 需要Python 3.7或更高版本")
        sys.exit(1)
    print(f"✓ Python版本: {sys.version}")

def install_dependencies():
    """安装依赖包"""
    print("正在安装依赖包...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ 依赖包安装完成")
    except subprocess.CalledProcessError:
        print("❌ 依赖包安装失败")
        sys.exit(1)

def setup_database():
    """设置数据库"""
    print("正在初始化数据库...")
    # 只创建数据库目录（如有必要），不再用sqlite3创建文件
    if not os.path.exists('database'):
        os.makedirs('database')
        print("✓ 创建数据库目录")
    print("✓ 数据库目录检查完成")

def start_server():
    """启动服务器"""
    print("正在启动股票分析系统后端服务...")
    print("服务地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务")
    print("-" * 50)
    
    try:
        # 导入并运行应用
        from backend_api.app_complete import app, init_db        
        # 初始化数据库
        init_db()
        
        # 启动Flask应用
        app.run(debug=True, host='0.0.0.0', port=5000)
        
    except KeyboardInterrupt:
        print("\n服务已停止")
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保所有依赖都已正确安装")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

def main():
    """主函数"""
    print("=" * 50)
    print("      股票分析系统后端启动器")
    print("=" * 50)
    
    # 检查Python版本
    check_python_version()
    
    # 安装依赖
    if not os.path.exists('requirements.txt'):
        print("❌ 未找到requirements.txt文件")
        sys.exit(1)
    
    install_dependencies()
    
    # 设置数据库
    setup_database()
    
    # 启动服务器
    start_server()

if __name__ == "__main__":
    main() 