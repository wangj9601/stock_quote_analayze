#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证打包内容的脚本
检查是否包含了所有必要的目录和文件
"""

import zipfile
import os
from pathlib import Path

def verify_package_content(zip_path):
    """验证ZIP包内容"""
    with zipfile.ZipFile(zip_path, 'r') as z:
        all_files = z.namelist()
        
        print(f"ZIP包总文件数: {len(all_files)}")
        
        # 检查核心目录
        core_dirs = ['backend_api', 'backend_core', 'frontend', 'admin']
        print("\n=== 核心目录检查 ===")
        
        for dir_name in core_dirs:
            dir_files = [f for f in all_files if f.startswith(f'{dir_name}/')]
            print(f"{dir_name}: {len(dir_files)} 个文件")
            
            # 检查Python文件
            py_files = [f for f in dir_files if f.endswith('.py')]
            print(f"  Python文件: {len(py_files)} 个")
            
            # 检查根目录下的Python文件
            root_py_files = [f for f in py_files if f.count('/') == 1]
            if root_py_files:
                print(f"  根目录Python文件: {len(root_py_files)} 个")
                for f in sorted(root_py_files):
                    print(f"    {f}")
        
        # 检查重要文件
        print("\n=== 重要文件检查 ===")
        important_files = [
            'requirements.txt',
            'setup.py',
            'README.md',
            'start_system.py',
            'deploy.py',
            'package.py'
        ]
        
        for file_name in important_files:
            if file_name in all_files:
                print(f"✅ {file_name}")
            else:
                print(f"❌ {file_name} (缺失)")
        
        # 检查启动脚本
        print("\n=== 启动脚本检查 ===")
        start_scripts = [f for f in all_files if f.startswith('start_') and f.endswith('.py')]
        for script in sorted(start_scripts):
            print(f"✅ {script}")
        
        # 检查数据库相关文件
        print("\n=== 数据库相关文件检查 ===")
        db_files = [f for f in all_files if 'migrate' in f or 'init' in f or 'database' in f]
        for file_name in sorted(db_files):
            print(f"✅ {file_name}")
        
        # 统计信息
        print(f"\n=== 统计信息 ===")
        py_files = [f for f in all_files if f.endswith('.py')]
        html_files = [f for f in all_files if f.endswith('.html')]
        css_files = [f for f in all_files if f.endswith('.css')]
        js_files = [f for f in all_files if f.endswith('.js')]
        md_files = [f for f in all_files if f.endswith('.md')]
        
        print(f"Python文件: {len(py_files)} 个")
        print(f"HTML文件: {len(html_files)} 个")
        print(f"CSS文件: {len(css_files)} 个")
        print(f"JavaScript文件: {len(js_files)} 个")
        print(f"Markdown文件: {len(md_files)} 个")
        
        # 检查包信息文件
        if 'package_info.json' in all_files:
            print(f"\n✅ 包含包信息文件: package_info.json")
        else:
            print(f"\n❌ 缺少包信息文件: package_info.json")

def main():
    """主函数"""
    # 查找最新的ZIP包
    dist_dir = "dist"
    if os.path.exists(dist_dir):
        zip_files = [f for f in os.listdir(dist_dir) if f.endswith('.zip')]
        if zip_files:
            latest_zip = max(zip_files, key=lambda x: os.path.getctime(os.path.join(dist_dir, x)))
            zip_path = os.path.join(dist_dir, latest_zip)
            print(f"验证ZIP包: {zip_path}")
            verify_package_content(zip_path)
        else:
            print("未找到ZIP包文件")
    else:
        print("dist目录不存在")

if __name__ == "__main__":
    main() 