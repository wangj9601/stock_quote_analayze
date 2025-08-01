#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证管理后台独立性的脚本
检查admin目录是否完全独立于frontend目录
"""

import os
import re
from pathlib import Path

def check_file_references(file_path, search_patterns):
    """检查文件中是否包含对frontend的引用"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for pattern in search_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True, pattern
        return False, None
    except Exception as e:
        return False, f"读取文件失败: {e}"

def verify_admin_independence():
    """验证admin目录的独立性"""
    print("=" * 60)
    print("           管理后台独立性验证")
    print("=" * 60)
    
    admin_dir = Path('admin')
    if not admin_dir.exists():
        print("❌ admin目录不存在")
        return False
    
    # 定义要检查的文件类型
    file_extensions = ['.html', '.js', '.css', '.md']
    
    # 定义要搜索的模式
    search_patterns = [
        r'\.\./frontend',           # 相对路径引用
        r'frontend/',               # 直接引用
        r'frontend\.',              # 文件名引用
        r'\.\./\.\./frontend',      # 多级相对路径
        r'frontend\.css',           # CSS文件引用
        r'frontend\.js',            # JS文件引用
        r'frontend\.html',          # HTML文件引用
    ]
    
    # 检查的文件列表
    files_to_check = []
    for ext in file_extensions:
        files_to_check.extend(admin_dir.rglob(f'*{ext}'))
    
    print(f"📁 检查目录: {admin_dir.absolute()}")
    print(f"🔍 检查文件数量: {len(files_to_check)}")
    print("-" * 60)
    
    # 检查每个文件
    issues_found = []
    files_checked = 0
    
    for file_path in files_to_check:
        files_checked += 1
        relative_path = file_path.relative_to(admin_dir)
        
        has_reference, pattern = check_file_references(file_path, search_patterns)
        
        if has_reference:
            issues_found.append((relative_path, pattern))
            print(f"❌ {relative_path} - 发现引用: {pattern}")
        else:
            print(f"✅ {relative_path}")
    
    print("-" * 60)
    print(f"📊 检查结果:")
    print(f"   检查文件数: {files_checked}")
    print(f"   发现问题数: {len(issues_found)}")
    
    if issues_found:
        print("\n❌ 发现以下问题:")
        for file_path, pattern in issues_found:
            print(f"   - {file_path}: {pattern}")
        print("\n💡 建议修复这些问题以确保完全独立")
        return False
    else:
        print("\n✅ 恭喜！管理后台完全独立，无任何frontend依赖")
        return True

def check_admin_resources():
    """检查admin目录资源完整性"""
    print("\n" + "=" * 60)
    print("           资源完整性检查")
    print("=" * 60)
    
    admin_dir = Path('admin')
    required_files = [
        'index.html',
        'config.js',
        'css/admin.css',
        'js/common.js',
        'js/admin.js',
        'js/quotes.js',
        'js/dashboard.js'
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in required_files:
        full_path = admin_dir / file_path
        if full_path.exists():
            existing_files.append(file_path)
            print(f"✅ {file_path}")
        else:
            missing_files.append(file_path)
            print(f"❌ {file_path} - 缺失")
    
    print("-" * 60)
    print(f"📊 资源检查结果:")
    print(f"   存在文件: {len(existing_files)}")
    print(f"   缺失文件: {len(missing_files)}")
    
    if missing_files:
        print("\n❌ 以下文件缺失:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    else:
        print("\n✅ 所有必要资源文件都存在")
        return True

def check_startup_scripts():
    """检查启动脚本"""
    print("\n" + "=" * 60)
    print("           启动脚本检查")
    print("=" * 60)
    
    startup_scripts = [
        'start_admin_standalone.py',
        'start_admin.py'
    ]
    
    for script in startup_scripts:
        if Path(script).exists():
            print(f"✅ {script}")
        else:
            print(f"❌ {script} - 缺失")
    
    return True

def main():
    """主函数"""
    print("开始验证管理后台独立性...")
    
    # 检查独立性
    independence_ok = verify_admin_independence()
    
    # 检查资源完整性
    resources_ok = check_admin_resources()
    
    # 检查启动脚本
    startup_ok = check_startup_scripts()
    
    print("\n" + "=" * 60)
    print("           验证总结")
    print("=" * 60)
    
    if independence_ok and resources_ok and startup_ok:
        print("🎉 管理后台验证通过！")
        print("✅ 完全独立于frontend目录")
        print("✅ 所有必要资源文件完整")
        print("✅ 启动脚本可用")
        print("\n💡 可以使用以下命令启动独立管理后台:")
        print("   python start_admin_standalone.py")
        print("\n🌐 访问地址: http://localhost:8001")
    else:
        print("❌ 管理后台验证失败")
        if not independence_ok:
            print("   - 存在frontend依赖")
        if not resources_ok:
            print("   - 缺少必要资源文件")
        if not startup_ok:
            print("   - 启动脚本缺失")
    
    print("=" * 60)

if __name__ == '__main__':
    main() 