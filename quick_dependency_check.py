#!/usr/bin/env python3
"""
快速依赖检查脚本
用于快速验证关键依赖的可用性
"""

import importlib
import sys
from typing import List, Tuple

def check_package(package_name: str) -> Tuple[bool, str]:
    """检查包是否可用"""
    try:
        importlib.import_module(package_name)
        return True, "✅ 可用"
    except ImportError as e:
        return False, f"❌ 不可用: {e}"

def main():
    """主函数"""
    print("=== 快速依赖检查 ===\n")
    
    # 关键依赖列表
    critical_packages = [
        # Web框架
        ("fastapi", "FastAPI Web框架"),
        ("uvicorn", "ASGI服务器"),
        ("python-multipart", "文件上传支持"),
        ("python-jose", "JWT处理"),
        ("passlib", "密码哈希"),
        ("email-validator", "邮箱验证"),
        
        # 数据库
        ("sqlalchemy", "ORM框架"),
        ("alembic", "数据库迁移"),
        ("psycopg2", "PostgreSQL驱动"),
        ("aiosqlite", "异步SQLite驱动"),
        
        # 数据处理
        ("pandas", "数据处理"),
        ("numpy", "数值计算"),
        ("akshare", "金融数据接口"),
        ("openpyxl", "Excel文件处理"),
        
        # 工具
        ("python-dotenv", "环境变量"),
        ("pydantic", "数据验证"),
        ("requests", "HTTP请求"),
        ("aiohttp", "异步HTTP"),
        ("tenacity", "重试机制"),
        
        # JWT认证
        ("jwt", "JWT处理"),
        
        # 定时任务
        ("apscheduler", "任务调度"),
        
        # 日志
        ("loguru", "日志系统"),
        
        # 配置
        ("yaml", "YAML配置"),
        
        # 进度条
        ("tqdm", "进度条"),
        
        # 开发工具
        ("black", "代码格式化"),
        ("isort", "导入排序"),
        ("flake8", "代码检查"),
        ("pytest", "测试框架"),
        ("httpx", "HTTP测试"),
    ]
    
    print("检查关键依赖包...\n")
    
    available_count = 0
    total_count = len(critical_packages)
    
    for package_name, description in critical_packages:
        is_available, status = check_package(package_name)
        if is_available:
            available_count += 1
        
        print(f"{package_name:20} - {description:15} {status}")
    
    print(f"\n📊 检查结果:")
    print(f"   可用: {available_count}/{total_count}")
    print(f"   缺失: {total_count - available_count}/{total_count}")
    
    if available_count == total_count:
        print("\n🎉 所有关键依赖都可用！")
        return True
    else:
        print(f"\n⚠️ 有 {total_count - available_count} 个依赖缺失")
        print("建议运行: pip install -r requirements.txt")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 