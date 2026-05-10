#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析系统打包脚本
支持多种格式打包，便于分发部署
"""

import os
import sys
import shutil
import zipfile
import tarfile
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Set

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProjectPackager:
    """项目打包器"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.package_name = "stock_quote_analyze"
        self.version = self.get_version()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def get_version(self) -> str:
        """获取项目版本"""
        try:
            with open("setup.py", "r", encoding="utf-8") as f:
                content = f.read()
                if "version=" in content:
                    import re
                    match = re.search(r'version="([^"]+)"', content)
                    if match:
                        return match.group(1)
        except:
            pass
        return "1.0.0"
    
    def get_include_patterns(self) -> List[str]:
        """获取需要包含的文件模式"""
        return [
            # 核心代码目录 - 确保包含所有子目录和文件
            "backend_api/**/*",
            "backend_api/*.py",
            "backend_api/*.txt",
            "backend_core/**/*",
            "backend_core/*.py",
            "backend_core/*.txt",
            "frontend/**/*",
            "frontend/*.html",
            "frontend/*.txt",
            # admin 工程目录不打包（单独构建部署）
            
            # 根目录重要文件
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-prod.txt",
            "setup.py",
            "README.md",
            "START_GUIDE.md",
            "QUICK_DEPLOY.md",
            "DEPLOYMENT_SUMMARY.md",
            "DEPENDENCY_MANAGEMENT_GUIDE.md",
            "POSTGRESQL_MIGRATION_GUIDE.md",
            
            # 启动脚本
            "start_frontend.py",
            "start_backend_core.py",
            "start_backend_api.py",
            "start_scheduler.py",
            "timestamp_stdio.py",
            "uvicorn_log_timestamp.yaml",
            
            # 数据库相关
            "migrate_db.py",
            "init_postgresql_db.py",
            "create_stock_news_table.py",
            "update_historical_quotes_name.py",
            # "database/**/*",  # database目录不打包

            # 部署相关
            "deploy.py",
            "package.py",
            "deploy_config.json",
            "wait-for-it.sh",
            "collect_realtime.bat",
            
            # 检查和测试脚本
            "check_dependencies.py",
            "check_postgresql_env.py",
            "quick_dependency_check.py",
            "test_*.py",
            
            # 文档（不打包docs目录）
            # "*.md",  # md文件不打包
            
            # 配置文件
            ".gitattributes",
        ]
    
    def get_exclude_patterns(self) -> List[str]:
        """获取需要排除的文件模式"""
        return [
            # Python缓存
            "**/__pycache__/**",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.pyd",
            "**/.pytest_cache/**",
            "**/.mypy_cache/**",
            
            # 虚拟环境
            "**/venv/**",
            "**/env/**",
            "**/.venv/**",
            "**/ENV/**",
            
            # IDE文件
            "**/.vscode/**",
            "**/.idea/**",
            "**/*.swp",
            "**/*.swo",
            "**/.DS_Store",
            
            # 日志文件
            "**/*.log",
            "**/logs/**",
            
            # 临时文件
            "**/tmp/**",
            "**/temp/**",
            "**/*.tmp",
            
            # Git文件
            "**/.git/**",
            "**/.gitignore",
            
            # 备份文件
            "**/backup/**",
            "**/*.bak",
            "**/*.backup",
            
            # 编译文件
            "**/*.egg-info/**",
            "**/build/**",
            "**/dist/**",
            
            # admin 工程目录不打包
            "admin",
            "admin/**",
            
            # 其他
            "**/node_modules/**",
            "**/package-lock.json",
            "**/yarn.lock",
            
            # 压缩文件
            "**/*.rar",
            "**/*.zip",
            "**/*.tar.gz",
            
            # 临时文档
            "**/~$*.docx",

            # 测试目录（远程部署包不含）
            "**/test/**",
            "**/tests/**",
        ]
    
    def should_include_file(self, file_path: Path, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
        """判断文件是否应该包含在打包中"""
        file_str = str(file_path.relative_to(self.project_root))
        norm_parts = file_str.replace("\\", "/").split("/")
        if "test" in norm_parts or "tests" in norm_parts:
            return False

        # 检查排除模式
        for pattern in exclude_patterns:
            if self.match_pattern(file_str, pattern):
                return False
        
        # 检查包含模式
        for pattern in include_patterns:
            if self.match_pattern(file_str, pattern):
                return True
        
        return False
    
    def match_pattern(self, file_path: str, pattern: str) -> bool:
        """简单的模式匹配"""
        import fnmatch
        return fnmatch.fnmatch(file_path, pattern)
    
    def collect_files(self) -> List[Path]:
        """收集需要打包的文件"""
        logger.info("📁 收集项目文件...")
        
        include_patterns = self.get_include_patterns()
        exclude_patterns = self.get_exclude_patterns()
        
        files_to_package = []
        
        for root, dirs, files in os.walk(self.project_root):
            root_path = Path(root)
            def _rel(d: str) -> str:
                try:
                    return str((root_path / d).relative_to(self.project_root))
                except ValueError:
                    return str(root_path / d)
            dirs[:] = [
                d for d in dirs
                if not any(p in ("test", "tests") for p in (root_path / d).relative_to(self.project_root).parts)
                and not any(self.match_pattern(_rel(d), pattern) for pattern in exclude_patterns)
            ]
            for file in files:
                file_path = root_path / file
                if self.should_include_file(file_path, include_patterns, exclude_patterns):
                    files_to_package.append(file_path)
        
        logger.info(f"✅ 收集到 {len(files_to_package)} 个文件")
        return files_to_package
    
    def create_package_info(self) -> dict:
        """创建包信息文件"""
        return {
            "package_name": self.package_name,
            "version": self.version,
            "build_time": self.timestamp,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "platform": sys.platform,
            "files_count": 0,
            "total_size": 0,
            "dependencies": self.get_dependencies(),
            "services": {
                "backend": "FastAPI + SQLAlchemy",
                "frontend": "HTML5 + CSS3 + JavaScript",
                "admin": "HTML5 + CSS3 + JavaScript",
                "database": "SQLite/PostgreSQL",
                "data_source": "akshare + tushare"
            },
            "components": {
                "backend_api": "FastAPI后端API服务",
                "backend_core": "核心数据采集和处理模块",
                "frontend": "用户前端界面",
                "admin": "管理员后台界面"
            }
        }
    
    def get_dependencies(self) -> dict:
        """获取项目依赖信息"""
        deps = {}
        
        # 主项目依赖
        if os.path.exists("requirements.txt"):
            try:
                with open("requirements.txt", "r", encoding="utf-8") as f:
                    deps["main"] = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except:
                deps["main"] = []
        
        # backend_core依赖
        if os.path.exists("backend_core/requirements.txt"):
            try:
                with open("backend_core/requirements.txt", "r", encoding="utf-8") as f:
                    deps["backend_core"] = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except:
                deps["backend_core"] = []
        
        # backend_api依赖
        if os.path.exists("backend_api/requirements.txt"):
            try:
                with open("backend_api/requirements.txt", "r", encoding="utf-8") as f:
                    deps["backend_api"] = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except:
                deps["backend_api"] = []
        
        return deps
    
    def create_zip_package(self, files: List[Path], output_dir: str = "dist") -> str:
        """创建ZIP包"""
        logger.info("📦 创建ZIP包...")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        zip_filename = f"{self.package_name}_v{self.version}_{self.timestamp}.zip"
        zip_path = output_dir / zip_filename
        
        total_size = 0
        files_count = 0
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                try:
                    # 计算相对路径
                    arcname = file_path.relative_to(self.project_root)
                    zipf.write(file_path, arcname)
                    
                    # 统计信息
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    files_count += 1
                    
                    logger.debug(f"添加文件: {arcname}")
                    
                except Exception as e:
                    logger.warning(f"添加文件失败 {file_path}: {e}")
        
        # 添加包信息
        package_info = self.create_package_info()
        package_info["files_count"] = files_count
        package_info["total_size"] = total_size
        
        with zipfile.ZipFile(zip_path, 'a') as zipf:
            zipf.writestr("package_info.json", json.dumps(package_info, indent=2, ensure_ascii=False))
        
        logger.info(f"✅ ZIP包创建完成: {zip_path}")
        logger.info(f"📊 文件数量: {files_count}, 总大小: {total_size / 1024 / 1024:.2f} MB")
        
        return str(zip_path)
    
    def create_tar_package(self, files: List[Path], output_dir: str = "dist") -> str:
        """创建TAR包"""
        logger.info("📦 创建TAR包...")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        tar_filename = f"{self.package_name}_v{self.version}_{self.timestamp}.tar.gz"
        tar_path = output_dir / tar_filename
        
        total_size = 0
        files_count = 0
        
        # 创建包信息
        package_info = self.create_package_info()
        
        # 创建临时包信息文件
        info_file = output_dir / "package_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(package_info, f, indent=2, ensure_ascii=False)
        
        # 创建tar包，包含所有文件和包信息
        with tarfile.open(tar_path, 'w:gz') as tar:
            # 添加所有项目文件
            for file_path in files:
                try:
                    # 计算相对路径
                    arcname = file_path.relative_to(self.project_root)
                    tar.add(file_path, arcname=arcname)
                    
                    # 统计信息
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    files_count += 1
                    
                    logger.debug(f"添加文件: {arcname}")
                    
                except Exception as e:
                    logger.warning(f"添加文件失败 {file_path}: {e}")
            
            # 添加包信息文件
            tar.add(info_file, arcname="package_info.json")
        
        # 删除临时文件
        info_file.unlink()
        
        # 更新包信息中的统计信息
        package_info["files_count"] = files_count
        package_info["total_size"] = total_size
        
        logger.info(f"✅ TAR包创建完成: {tar_path}")
        logger.info(f"📊 文件数量: {files_count}, 总大小: {total_size / 1024 / 1024:.2f} MB")
        
        return str(tar_path)
    
    def create_deployment_package(self, output_dir: str = "dist") -> str:
        """创建部署专用包"""
        logger.info("🚀 创建部署专用包...")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # 创建部署目录
        deploy_dir = output_dir / f"{self.package_name}_deploy_{self.timestamp}"
        deploy_dir.mkdir(exist_ok=True)
        
        # 收集文件
        files = self.collect_files()
        
        # 复制文件到部署目录
        for file_path in files:
            try:
                # 计算相对路径
                relative_path = file_path.relative_to(self.project_root)
                target_path = deploy_dir / relative_path
                
                # 创建目录
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 复制文件
                shutil.copy2(file_path, target_path)
                logger.debug(f"复制文件: {relative_path}")
                
            except Exception as e:
                logger.warning(f"复制文件失败 {file_path}: {e}")
        
        # 创建部署脚本
        self.create_deployment_scripts(deploy_dir)
        
        # 创建包信息
        package_info = self.create_package_info()
        with open(deploy_dir / "package_info.json", 'w', encoding='utf-8') as f:
            json.dump(package_info, f, indent=2, ensure_ascii=False)
        
        # 压缩部署目录
        zip_filename = f"{self.package_name}_deploy_v{self.version}_{self.timestamp}.zip"
        zip_path = output_dir / zip_filename
        
        shutil.make_archive(str(zip_path.with_suffix('')), 'zip', deploy_dir)
        
        # 清理临时目录
        shutil.rmtree(deploy_dir)
        
        logger.info(f"✅ 部署包创建完成: {zip_path}")
        return str(zip_path)
    
    def create_deployment_scripts(self, deploy_dir: Path):
        """创建部署脚本"""
        # Windows部署脚本
        deploy_bat = deploy_dir / "deploy.bat"
        with open(deploy_bat, 'w', encoding='utf-8') as f:
            f.write("@echo off\n")
            f.write("echo 股票分析系统部署脚本\n")
            f.write("echo ========================\n\n")
            f.write("echo 1. 检查Python环境...\n")
            f.write("python --version\n")
            f.write("if errorlevel 1 (\n")
            f.write("    echo 错误: 未找到Python，请先安装Python 3.8+\n")
            f.write("    pause\n")
            f.write("    exit /b 1\n")
            f.write(")\n\n")
            f.write("echo 2. 运行部署脚本...\n")
            f.write("python deploy.py\n")
            f.write("if errorlevel 1 (\n")
            f.write("    echo 部署失败，请检查错误信息\n")
            f.write("    pause\n")
            f.write("    exit /b 1\n")
            f.write(")\n\n")
            f.write("echo 3. 启动系统...\n")
            f.write("python start_system.py\n")
            f.write("pause\n")
        
        # Linux/macOS部署脚本
        deploy_sh = deploy_dir / "deploy.sh"
        with open(deploy_sh, 'w', encoding='utf-8') as f:
            f.write("#!/bin/bash\n")
            f.write("echo '股票分析系统部署脚本'\n")
            f.write("echo '========================'\n\n")
            f.write("echo '1. 检查Python环境...'\n")
            f.write("python3 --version || {\n")
            f.write("    echo '错误: 未找到Python，请先安装Python 3.8+'\n")
            f.write("    exit 1\n")
            f.write("}\n\n")
            f.write("echo '2. 运行部署脚本...'\n")
            f.write("python3 deploy.py || {\n")
            f.write("    echo '部署失败，请检查错误信息'\n")
            f.write("    exit 1\n")
            f.write("}\n\n")
            f.write("echo '3. 启动系统...'\n")
            f.write("python3 start_system.py\n")
        
        # 设置执行权限
        os.chmod(deploy_sh, 0o755)
    
    def create_minimal_package(self, output_dir: str = "dist") -> str:
        """创建最小化包（仅包含运行时必需文件）"""
        logger.info("📦 创建最小化包...")
        
        # 最小化包含的文件模式
        minimal_patterns = [
            "backend_api/**/*.py",
            "backend_core/**/*.py",
            "frontend/**/*",
            # admin 工程目录不打包
            "requirements.txt",
            "requirements-prod.txt",
            "start_system.py",
            "start_frontend.py",
            "start_backend_core.py",
            "start_admin.py",
            "run.py",
            "migrate_db.py",
            "database/**/*",
            "README.md",
            "START_GUIDE.md",
            "deploy.py",
            "deploy_config.json",
        ]
        
        # 最小化排除的文件模式
        minimal_excludes = [
            "**/__pycache__/**",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.pyd",
            "**/.pytest_cache/**",
            "**/.mypy_cache/**",
            "admin",
            "admin/**",
            "**/test/**",
            "**/tests/**",
            "**/*_test.py",
            "**/test_*.py",
            "**/.git/**",
            "**/.vscode/**",
            "**/.idea/**",
            "**/*.log",
            "**/logs/**",
            "**/docs/**",
            "**/package.py",
            "**/*.egg-info/**",
            "**/build/**",
            "**/dist/**",
        ]
        
        files = []
        for root, dirs, filenames in os.walk(self.project_root):
            root_path = Path(root)
            def _rel(d: str) -> str:
                try:
                    return str((root_path / d).relative_to(self.project_root))
                except ValueError:
                    return str(root_path / d)
            dirs[:] = [
                d for d in dirs
                if not any(p in ("test", "tests") for p in (root_path / d).relative_to(self.project_root).parts)
                and not any(self.match_pattern(_rel(d), pattern) for pattern in minimal_excludes)
            ]
            for filename in filenames:
                file_path = root_path / filename
                if self.should_include_file(file_path, minimal_patterns, minimal_excludes):
                    files.append(file_path)
        
        # 创建ZIP包
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        zip_filename = f"{self.package_name}_minimal_v{self.version}_{self.timestamp}.zip"
        zip_path = output_dir / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                try:
                    arcname = file_path.relative_to(self.project_root)
                    zipf.write(file_path, arcname)
                except Exception as e:
                    logger.warning(f"添加文件失败 {file_path}: {e}")
        
        logger.info(f"✅ 最小化包创建完成: {zip_path}")
        return str(zip_path)
    
    def package(self, format_type: str = "all", output_dir: str = "dist") -> List[str]:
        """执行打包"""
        logger.info(f"🚀 开始打包项目 (格式: {format_type})...")
        
        # 收集文件
        files = self.collect_files()
        
        results = []
        
        if format_type in ["all", "zip"]:
            zip_path = self.create_zip_package(files, output_dir)
            results.append(zip_path)
        
        if format_type in ["all", "tar"]:
            tar_path = self.create_tar_package(files, output_dir)
            results.append(tar_path)
        
        if format_type in ["all", "deploy"]:
            deploy_path = self.create_deployment_package(output_dir)
            results.append(deploy_path)
        
        if format_type in ["all", "minimal"]:
            minimal_path = self.create_minimal_package(output_dir)
            results.append(minimal_path)
        
        logger.info(f"🎉 打包完成! 共创建 {len(results)} 个包")
        for result in results:
            logger.info(f"📦 {result}")
        
        return results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="股票分析系统打包脚本")
    parser.add_argument("--format", choices=["zip", "tar", "deploy", "minimal", "all"], 
                       default="all", help="打包格式")
    parser.add_argument("--output", default="dist", help="输出目录")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    packager = ProjectPackager(args.project_root)
    results = packager.package(args.format, args.output)
    
    print(f"\n🎉 打包完成! 共创建 {len(results)} 个包:")
    for result in results:
        print(f"📦 {result}")

if __name__ == "__main__":
    main() 