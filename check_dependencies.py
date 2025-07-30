#!/usr/bin/env python3
"""
依赖检查脚本
用于验证项目中所有依赖的完整性和准确性
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path
from typing import Dict, List, Set, Tuple

def load_requirements_file(file_path: str) -> Dict[str, str]:
    """加载requirements.txt文件"""
    requirements = {}
    if not os.path.exists(file_path):
        return requirements
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # 处理包名和版本
                if '>=' in line:
                    package, version = line.split('>=', 1)
                    requirements[package.strip()] = f">={version.strip()}"
                elif '==' in line:
                    package, version = line.split('==', 1)
                    requirements[package.strip()] = f"=={version.strip()}"
                elif '<' in line:
                    package, version = line.split('<', 1)
                    requirements[package.strip()] = f"<{version.strip()}"
                else:
                    requirements[line] = ""
    
    return requirements

def check_installed_packages() -> Dict[str, str]:
    """检查已安装的包"""
    installed = {}
    try:
        # 使用pip list命令获取已安装的包
        result = subprocess.run([sys.executable, '-m', 'pip', 'list'], 
                              capture_output=True, text=True, check=True)
        
        lines = result.stdout.strip().split('\n')[2:]  # 跳过标题行
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    package_name = parts[0].lower()
                    version = parts[1]
                    installed[package_name] = version
    except subprocess.CalledProcessError:
        print("警告: 无法获取已安装的包列表")
    
    return installed

def check_imports_in_file(file_path: str) -> Set[str]:
    """检查文件中的导入"""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                # 提取包名
                if line.startswith('import '):
                    parts = line[7:].split()
                    if parts:
                        package = parts[0].split('.')[0]
                        imports.add(package.lower())
                elif line.startswith('from '):
                    parts = line[5:].split(' import')
                    if parts:
                        package = parts[0].split('.')[0]
                        imports.add(package.lower())
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {e}")
    
    return imports

def scan_project_imports(project_root: str) -> Set[str]:
    """扫描项目中的所有导入"""
    all_imports = set()
    
    for root, dirs, files in os.walk(project_root):
        # 跳过虚拟环境和缓存目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'env', '.venv']]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                imports = check_imports_in_file(file_path)
                all_imports.update(imports)
    
    return all_imports

def check_package_availability(package_name: str) -> bool:
    """检查包是否可用"""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False

def main():
    """主函数"""
    print("=== 依赖完整性检查 ===\n")
    
    project_root = Path(__file__).parent
    requirements_files = [
        "requirements.txt",
        "backend_api/requirements.txt",
        "backend_core/requirements.txt"
    ]
    
    # 1. 加载所有requirements文件
    all_requirements = {}
    for req_file in requirements_files:
        if os.path.exists(req_file):
            print(f"📋 加载 {req_file}...")
            requirements = load_requirements_file(req_file)
            all_requirements.update(requirements)
            print(f"   找到 {len(requirements)} 个依赖")
    
    print(f"\n📦 总计 {len(all_requirements)} 个唯一依赖")
    
    # 2. 检查已安装的包
    print("\n🔍 检查已安装的包...")
    installed = check_installed_packages()
    print(f"   已安装 {len(installed)} 个包")
    
    # 3. 扫描项目导入
    print("\n🔍 扫描项目导入...")
    project_imports = scan_project_imports(str(project_root))
    print(f"   发现 {len(project_imports)} 个导入的包")
    
    # 4. 检查依赖完整性
    print("\n✅ 检查依赖完整性...")
    missing_in_requirements = []
    missing_installed = []
    version_mismatches = []
    
    for package in project_imports:
        # 跳过标准库
        if package in ['os', 'sys', 'json', 'datetime', 'time', 'logging', 'pathlib', 
                      'typing', 'subprocess', 'threading', 'argparse', 'shutil', 
                      'zipfile', 'tarfile', 'webbrowser', 'urllib', 'http', 'socketserver',
                      'traceback', 'random', 'math', 're', 'collections', 'itertools',
                      'functools', 'contextlib', 'weakref', 'copy', 'pickle', 'hashlib',
                      'base64', 'struct', 'array', 'bisect', 'heapq', 'queue', 'asyncio',
                      'concurrent', 'multiprocessing', 'signal', 'socket', 'select',
                      'ssl', 'email', 'mimetypes', 'html', 'xml', 'csv', 'configparser',
                      'tempfile', 'glob', 'fnmatch', 'linecache', 'codecs', 'locale',
                      'gettext', 'string', 'unicodedata', 'textwrap', 'difflib', 'inspect',
                      'ast', 'symtable', 'token', 'keyword', 'tokenize', 'tabnanny',
                      'py_compile', 'compileall', 'dis', 'pickletools', 'formatter',
                      'msilib', 'msvcrt', 'winreg', 'winsound', 'win32api', 'win32con',
                      'win32gui', 'win32process', 'win32security', 'win32service',
                      'win32serviceutil', 'win32timezone', 'pythoncom', 'pywintypes',
                      'win32com', 'win32com.client', 'win32com.server', 'win32com.server.util']:
            continue
        
        # 检查是否在requirements中
        if package not in all_requirements:
            missing_in_requirements.append(package)
        
        # 检查是否已安装
        if package not in installed:
            missing_installed.append(package)
    
    # 检查版本不匹配
    for package, version_req in all_requirements.items():
        if package in installed:
            installed_version = installed[package]
            # 简单的版本检查（这里可以扩展为更复杂的版本比较）
            if version_req and not version_req.startswith('>='):
                # 对于精确版本要求，检查是否匹配
                if version_req.startswith('==') and installed_version != version_req[2:]:
                    version_mismatches.append((package, version_req, installed_version))
    
    # 5. 输出结果
    print(f"\n📊 检查结果:")
    print(f"   ✅ 依赖完整性: {'通过' if not missing_in_requirements else '失败'}")
    print(f"   ✅ 安装状态: {'通过' if not missing_installed else '失败'}")
    print(f"   ✅ 版本匹配: {'通过' if not version_mismatches else '失败'}")
    
    if missing_in_requirements:
        print(f"\n❌ 缺失的依赖 (在代码中使用但未在requirements.txt中声明):")
        for package in sorted(missing_in_requirements):
            print(f"   - {package}")
    
    if missing_installed:
        print(f"\n❌ 未安装的依赖:")
        for package in sorted(missing_installed):
            print(f"   - {package}")
    
    if version_mismatches:
        print(f"\n⚠️ 版本不匹配:")
        for package, required, installed in version_mismatches:
            print(f"   - {package}: 需要 {required}, 已安装 {installed}")
    
    # 6. 建议
    print(f"\n💡 建议:")
    if missing_in_requirements:
        print("   1. 将缺失的依赖添加到requirements.txt文件中")
    if missing_installed:
        print("   2. 运行 'pip install -r requirements.txt' 安装缺失的依赖")
    if version_mismatches:
        print("   3. 检查版本冲突，确保依赖版本兼容")
    
    if not missing_in_requirements and not missing_installed and not version_mismatches:
        print("   🎉 所有依赖检查通过！")
    
    # 7. 生成依赖报告
    print(f"\n📄 生成依赖报告...")
    report_file = "dependency_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=== 依赖检查报告 ===\n\n")
        f.write(f"项目根目录: {project_root}\n")
        f.write(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("=== 依赖统计 ===\n")
        f.write(f"requirements.txt中的依赖: {len(all_requirements)}\n")
        f.write(f"已安装的包: {len(installed)}\n")
        f.write(f"项目导入的包: {len(project_imports)}\n\n")
        
        f.write("=== 问题详情 ===\n")
        if missing_in_requirements:
            f.write("缺失的依赖:\n")
            for package in sorted(missing_in_requirements):
                f.write(f"  - {package}\n")
            f.write("\n")
        
        if missing_installed:
            f.write("未安装的依赖:\n")
            for package in sorted(missing_installed):
                f.write(f"  - {package}\n")
            f.write("\n")
        
        if version_mismatches:
            f.write("版本不匹配:\n")
            for package, required, installed in version_mismatches:
                f.write(f"  - {package}: 需要 {required}, 已安装 {installed}\n")
            f.write("\n")
    
    print(f"   报告已保存到 {report_file}")
    
    return len(missing_in_requirements) + len(missing_installed) + len(version_mismatches) == 0

if __name__ == "__main__":
    from datetime import datetime
    success = main()
    sys.exit(0 if success else 1) 