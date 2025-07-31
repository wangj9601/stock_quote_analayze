#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查ZIP包内容的脚本
"""

import zipfile
import os

def check_zip_content(zip_path):
    """检查ZIP包内容"""
    with zipfile.ZipFile(zip_path, 'r') as z:
        # 获取所有文件列表
        all_files = z.namelist()
        
        print(f"ZIP包总文件数: {len(all_files)}")
        print("\n=== Backend API 文件 ===")
        
        # 检查backend_api目录下的所有文件
        backend_api_files = [f for f in all_files if f.startswith('backend_api/')]
        print(f"Backend API 文件总数: {len(backend_api_files)}")
        
        # 检查根目录下的Python文件
        root_py_files = [f for f in backend_api_files if f.endswith('.py') and f.count('/') == 1]
        print(f"Backend API 根目录Python文件: {len(root_py_files)}")
        for f in sorted(root_py_files):
            print(f"  {f}")
        
        # 检查子目录下的Python文件
        subdir_py_files = [f for f in backend_api_files if f.endswith('.py') and f.count('/') > 1]
        print(f"\nBackend API 子目录Python文件: {len(subdir_py_files)}")
        for f in sorted(subdir_py_files):
            print(f"  {f}")
        
        # 检查其他文件
        other_files = [f for f in backend_api_files if not f.endswith('.py')]
        print(f"\nBackend API 其他文件: {len(other_files)}")
        for f in sorted(other_files):
            print(f"  {f}")

if __name__ == "__main__":
    # 查找最新的ZIP包
    dist_dir = "dist"
    if os.path.exists(dist_dir):
        zip_files = [f for f in os.listdir(dist_dir) if f.endswith('.zip')]
        if zip_files:
            latest_zip = max(zip_files, key=lambda x: os.path.getctime(os.path.join(dist_dir, x)))
            zip_path = os.path.join(dist_dir, latest_zip)
            print(f"检查ZIP包: {zip_path}")
            check_zip_content(zip_path)
        else:
            print("未找到ZIP包文件")
    else:
        print("dist目录不存在") 