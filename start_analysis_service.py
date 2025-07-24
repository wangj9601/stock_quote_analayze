#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能分析服务启动脚本
"""

import os
import sys
import uvicorn
from pathlib import Path

def main():
    """启动智能分析服务"""
    print("=" * 60)
    print("🚀 启动股票智能分析服务")
    print("=" * 60)
    
    # 设置工作目录
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # 检查环境
    print("📋 环境检查:")
    print(f"   项目根目录: {project_root}")
    print(f"   Python版本: {sys.version}")
    
    # 检查必要的文件
    required_files = [
        "backend_api/main.py",
        "backend_api/stock/stock_analysis.py",
        "backend_api/stock/stock_analysis_routes.py"
    ]
    
    print("\n📁 文件检查:")
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✓ {file_path}")
        else:
            print(f"   ✗ {file_path} (缺失)")
            return False
    
    # 启动服务
    print("\n🌐 启动服务...")
    print("   服务地址: http://localhost:8000")
    print("   API文档: http://localhost:8000/docs")
    print("   智能分析API: http://localhost:8000/analysis/stock/{股票代码}")
    print("\n按 Ctrl+C 停止服务")
    print("-" * 60)
    
    try:
        uvicorn.run(
            "backend_api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["backend_api"],
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n🛑 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 