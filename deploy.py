#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析系统部署脚本
支持新环境一键部署
"""

import os
import sys
import subprocess
import shutil
import json
import platform
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deploy.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Deployer:
    """项目部署器"""
    
    def __init__(self, config_path: str = "deploy_config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.project_root = Path(__file__).parent
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        
    def load_config(self) -> Dict:
        """加载部署配置"""
        default_config = {
            "python_version": "3.8",
            "ports": {
                "backend": 5000,
                "frontend": 8000,
                "admin": 8001
            },
            "database": {
                "type": "postgresql",
                "host": "192.168.31.237",
                "port": 5446,
                "name": "stock_analysis",
                "user": "postgres",
                "password": "qidianspacetime",
                "pool_size": 5,
                "max_overflow": 10
            },
            "services": {
                "backend": True,
                "frontend": True,
                "admin": True,
                "data_collector": True
            },
            "environment": {
                "production": False,
                "debug": False
            }
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}, 使用默认配置")
                return default_config
        else:
            logger.info("配置文件不存在，创建默认配置")
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Dict):
        """保存配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def check_environment(self) -> bool:
        """检查部署环境"""
        logger.info("🔍 检查部署环境...")
        
        # 检查Python版本
        if sys.version_info < (3, 8):
            logger.error(f"❌ Python版本过低: {self.python_version}, 需要3.8+")
            return False
        logger.info(f"✅ Python版本: {self.python_version}")
        
        # 检查必要目录
        required_dirs = [
            "backend_api",
            "backend_core", 
            "frontend",
            "admin"
        ]
        
        for dir_name in required_dirs:
            if not os.path.exists(dir_name):
                logger.error(f"❌ 缺少必要目录: {dir_name}")
                return False
        logger.info("✅ 项目目录结构检查通过")
        
        # 检查必要文件
        required_files = [
            "requirements-prod.txt",
            "start_backend_api.py",
            "start_backend_core.py",    
            "start_frontend.py"
        ]
        
        for file_name in required_files:
            if not os.path.exists(file_name):
                logger.error(f"❌ 缺少必要文件: {file_name}")
                return False
        logger.info("✅ 项目文件检查通过")
        
        # 检查数据库配置
        db_config = self.config.get("database", {})
        db_type = db_config.get("type", "postgresql")
        
        if db_type == "postgresql":
            logger.info("📊 检查PostgreSQL环境...")
            
            # 检查PostgreSQL环境
            if os.path.exists("check_postgresql_env.py"):
                try:
                    subprocess.run([sys.executable, "check_postgresql_env.py"], check=True, capture_output=True)
                    logger.info("✅ PostgreSQL环境检查通过")
                except subprocess.CalledProcessError:
                    logger.error("❌ PostgreSQL环境检查失败，请运行 python check_postgresql_env.py 查看详细信息")
                    return False
            else:
                logger.warning("⚠️ PostgreSQL环境检查脚本不存在，跳过检查")
        
        return True
    
    def install_dependencies(self) -> bool:
        """安装项目依赖"""
        logger.info("📦 安装项目依赖...")
        
        try:
            # 升级pip
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                         check=True, capture_output=True)
            logger.info("✅ pip升级完成")
            
            # 确定环境类型
            environment = self.config.get("environment", "production")
            logger.info(f"🔧 部署环境: {environment}")
            
            # 安装生产环境依赖
            if os.path.exists("requirements-prod.txt"):
                logger.info("📦 安装生产环境依赖...")
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-prod.txt"], 
                             check=True, capture_output=True)
                logger.info("✅ 生产环境依赖安装完成")
            elif os.path.exists("requirements.txt"):
                logger.info("📦 安装标准依赖...")
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                             check=True, capture_output=True)
                logger.info("✅ 标准依赖安装完成")
            else:
                logger.error("❌ 未找到requirements.txt或requirements-prod.txt文件")
                return False
            
            # 开发环境额外依赖
            if environment == "development" and os.path.exists("requirements-dev.txt"):
                logger.info("📦 安装开发环境依赖...")
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"], 
                             check=True, capture_output=True)
                logger.info("✅ 开发环境依赖安装完成")
            
            # 安装子模块依赖（如果存在且需要）
            if self.config.get("install_submodules", True):
                # 安装backend_core依赖 - 优先使用简化版本
                if os.path.exists("backend_core/requirements-minimal.txt"):
                    logger.info("📦 安装backend_core简化依赖...")
                    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "backend_core/requirements-minimal.txt"], 
                                 check=True, capture_output=True)
                    logger.info("✅ backend_core简化依赖安装完成")
                elif os.path.exists("backend_core/requirements.txt"):
                    logger.info("📦 安装backend_core完整依赖...")
                    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "backend_core/requirements.txt"], 
                                 check=True, capture_output=True)
                    logger.info("✅ backend_core完整依赖安装完成")
                
                # 安装backend_api依赖
                if os.path.exists("backend_api/requirements.txt"):
                    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "backend_api/requirements.txt"], 
                                 check=True, capture_output=True)
                    logger.info("✅ backend_api依赖安装完成")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 依赖安装失败: {e}")
            return False
    
    def setup_database(self) -> bool:
        """初始化数据库"""
        logger.info("🗄️ 初始化数据库...")
        
        try:
            db_config = self.config.get("database", {})
            db_type = db_config.get("type", "postgresql")
            
            if db_type == "postgresql":
                logger.info("📊 配置PostgreSQL数据库...")
                
                # 初始化PostgreSQL数据库
                if os.path.exists("init_postgresql_db.py"):
                    logger.info("🗄️ 初始化PostgreSQL数据库...")
                    subprocess.run([sys.executable, "init_postgresql_db.py"], check=True, capture_output=True)
                    logger.info("✅ PostgreSQL数据库初始化完成")
                
                # 检查PostgreSQL连接
                if os.path.exists("test_deploy_db.py"):
                    logger.info("🔍 测试PostgreSQL连接...")
                    subprocess.run([sys.executable, "test_deploy_db.py"], check=True, capture_output=True)
                    logger.info("✅ PostgreSQL连接测试通过")
                
                # 运行数据库迁移
                if os.path.exists("migrate_db.py"):
                    logger.info("🔄 运行数据库迁移...")
                    subprocess.run([sys.executable, "migrate_db.py"], check=True, capture_output=True)
                    logger.info("✅ 数据库迁移完成")
                
            elif db_type == "sqlite":
                logger.info("📊 配置SQLite数据库...")
                
                # 创建数据库目录
                db_path = db_config.get("path", "database/stock_analysis.db")
                db_dir = Path(db_path).parent
                db_dir.mkdir(parents=True, exist_ok=True)
                
                # 运行数据库迁移
                if os.path.exists("migrate_db.py"):
                    subprocess.run([sys.executable, "migrate_db.py"], check=True, capture_output=True)
                    logger.info("✅ 数据库迁移完成")
                
                # 检查数据库连接
                if os.path.exists("test_deploy_db.py"):
                    subprocess.run([sys.executable, "test_deploy_db.py"], check=True, capture_output=True)
                    logger.info("✅ 数据库连接测试通过")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 数据库设置失败: {e}")
            return False
    
    def create_startup_scripts(self) -> bool:
        """创建启动脚本"""
        logger.info("📝 创建启动脚本...")
        
        try:
            # Windows批处理文件
            if platform.system() == "Windows":
                self.create_windows_scripts()
            else:
                self.create_unix_scripts()
            
            logger.info("✅ 启动脚本创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 启动脚本创建失败: {e}")
            return False
    
    def create_windows_scripts(self):
        """创建Windows启动脚本"""
        # 主启动脚本
        with open("start.bat", "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("echo 启动股票分析系统...\n")
            f.write("python start_system.py\n")
            f.write("pause\n")
        
        # 后端启动脚本
        with open("start_backend.bat", "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("echo 启动后端服务...\n")
            f.write("python run.py\n")
            f.write("pause\n")
        
        # 前端启动脚本
        with open("start_frontend.bat", "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("echo 启动前端服务...\n")
            f.write("python start_frontend.py\n")
            f.write("pause\n")
    
    def create_unix_scripts(self):
        """创建Unix/Linux启动脚本"""
        # 主启动脚本
        with open("start.sh", "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write("echo '启动股票分析系统...'\n")
            f.write("python3 start_system.py\n")
        
        # 后端启动脚本
        with open("start_backend.sh", "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write("echo '启动后端服务...'\n")
            f.write("python3 run.py\n")
        
        # 前端启动脚本
        with open("start_frontend.sh", "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write("echo '启动前端服务...'\n")
            f.write("python3 start_frontend.py\n")
        
        # 设置执行权限
        os.chmod("start.sh", 0o755)
        os.chmod("start_backend.sh", 0o755)
        os.chmod("start_frontend.sh", 0o755)
    
    def create_docker_files(self) -> bool:
        """创建Docker部署文件"""
        logger.info("🐳 创建Docker部署文件...")
        
        try:
            # Dockerfile
            dockerfile_content = """# 使用Python 3.9官方镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
COPY backend_core/requirements.txt ./backend_core/
COPY backend_api/requirements.txt ./backend_api/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r backend_core/requirements.txt
RUN pip install --no-cache-dir -r backend_api/requirements.txt

# 复制项目文件
COPY . .

# 创建日志目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 5000 8000 8001

# 等待数据库启动并初始化
COPY wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

# 启动命令
CMD ["/wait-for-it.sh", "postgres:5432", "--", "python", "start_system.py"]
"""
            
            with open("Dockerfile", "w", encoding="utf-8") as f:
                f.write(dockerfile_content)
            
            # docker-compose.yml
            compose_content = """version: '3.8'

services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: stock_analysis
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: qidianspacetime
    ports:
      - "5446:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  stock-analyzer:
    build: .
    ports:
      - "5000:5000"  # 后端API
      - "8000:8000"  # 前端
      - "8001:8001"  # 管理后台
    volumes:
      - ./logs:/app/logs
    environment:
      - PYTHONPATH=/app
      - ENVIRONMENT=production
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=stock_analysis
      - DB_USER=postgres
      - DB_PASSWORD=qidianspacetime
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
"""
            
            with open("docker-compose.yml", "w", encoding="utf-8") as f:
                f.write(compose_content)
            
            # .dockerignore
            dockerignore_content = """__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis
.DS_Store
*.egg-info
.installed.cfg
*.egg
MANIFEST
.env
.venv
venv/
ENV/
env.bak/
venv.bak/
"""
            
            with open(".dockerignore", "w", encoding="utf-8") as f:
                f.write(dockerignore_content)
            
            logger.info("✅ Docker文件创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ Docker文件创建失败: {e}")
            return False
    
    def create_deployment_guide(self) -> bool:
        """创建部署指南"""
        logger.info("📖 创建部署指南...")
        
        try:
            guide_content = """# 股票分析系统部署指南

## 快速部署

### 1. 环境要求
- Python 3.8+
- PostgreSQL 12+
- 操作系统: Windows/Linux/macOS
- 内存: 4GB+
- 磁盘空间: 2GB+

### 2. 数据库配置
系统使用PostgreSQL数据库，请确保：
- PostgreSQL服务已启动
- 数据库连接参数正确（见deploy_config.json）
- 用户具有创建数据库和表的权限

### 3. 一键部署
```bash
# 运行部署脚本
python deploy.py

# 启动系统
python start_system.py
```

### 4. 手动部署
```bash
# 安装依赖
pip install -r requirements.txt
pip install -r backend_core/requirements.txt
pip install -r backend_api/requirements.txt

# 初始化PostgreSQL数据库
python init_postgresql_db.py

# 运行数据库迁移
python migrate_db.py

# 启动服务
python start_system.py
```

## Docker部署

### 1. 构建镜像
```bash
docker build -t stock-analyzer .
```

### 2. 运行容器
```bash
docker run -d -p 5000:5000 -p 8000:8000 -p 8001:8001 stock-analyzer
```

### 3. 使用Docker Compose
```bash
docker-compose up -d
```

## 访问地址

- 登录页面: http://localhost:8000/login.html
- 首页: http://localhost:8000/index.html
- 后端API: http://localhost:5000
- 管理后台: http://localhost:8001/

## 配置说明

编辑 `deploy_config.json` 文件来修改配置:

```json
{
  "python_version": "3.8",
  "ports": {
    "backend": 5000,
    "frontend": 8000,
    "admin": 8001
  },
  "database": {
    "type": "sqlite",
    "path": "database/stock_analysis.db"
  },
  "services": {
    "backend": true,
    "frontend": true,
    "admin": true,
    "data_collector": true
  }
}
```

## 故障排除

### 1. 端口冲突
修改 `deploy_config.json` 中的端口配置

### 2. 依赖安装失败
```bash
# 升级pip
python -m pip install --upgrade pip

# 清理缓存
pip cache purge

# 重新安装
pip install -r requirements.txt
```

### 3. 数据库问题
```bash
# 检查数据库连接
python test_db_connection.py

# 重新初始化数据库
python migrate_db.py
```

### 4. 权限问题
```bash
# Linux/macOS设置执行权限
chmod +x start.sh start_backend.sh start_frontend.sh
```

## 生产环境部署

### 1. 使用Gunicorn
```bash
pip install gunicorn
# --timeout：静默超过该秒数会重启 worker；GMS 全 A 股选股可能超过数分钟，须 >= 600，并与 Nginx proxy_read_timeout、GMS_SCREENING_TIMEOUT 一致
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend_api.main:app -b 0.0.0.0:5000 --timeout 600
```

### 2. 使用Nginx反向代理
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://localhost:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. 使用Supervisor管理进程
```ini
[program:stock-analyzer]
command=python /path/to/stock_analyzer/start_system.py
directory=/path/to/stock_analyzer
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/stock-analyzer.log
```

## 监控和维护

### 1. 日志查看
```bash
tail -f deploy.log
tail -f logs/app.log
```

### 2. 性能监控
- 使用 `htop` 监控系统资源
- 使用 `netstat -tulpn` 检查端口占用
- 使用 `df -h` 检查磁盘空间

### 3. 备份
```bash
# 备份数据库
cp database/stock_analysis.db backup/stock_analysis_$(date +%Y%m%d).db

# 备份配置文件
cp deploy_config.json backup/
```

## 技术支持

如遇问题请检查:
1. Python版本是否符合要求
2. 依赖包是否正确安装
3. 端口是否被占用
4. 数据库文件权限
5. 网络连接是否正常

更多信息请查看项目README.md文件。
"""
            
            with open("DEPLOYMENT_GUIDE.md", "w", encoding="utf-8") as f:
                f.write(guide_content)
            
            logger.info("✅ 部署指南创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 部署指南创建失败: {e}")
            return False
    
    def test_deployment(self) -> bool:
        """测试部署"""
        logger.info("🧪 测试部署...")
        
        try:
            # 测试数据库连接
            if os.path.exists("test_deploy_db.py"):
                result = subprocess.run([sys.executable, "test_deploy_db.py"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info("✅ 数据库连接测试通过")
                else:
                    logger.error(f"❌ 数据库连接测试失败: {result.stderr}")
                    return False
            
            # 测试API连接
            if os.path.exists("test_api.py"):
                result = subprocess.run([sys.executable, "test_api.py"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info("✅ API连接测试通过")
                else:
                    logger.warning(f"⚠️ API连接测试失败: {result.stderr}")
            
            logger.info("✅ 部署测试完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 部署测试失败: {e}")
            return False
    
    def deploy(self, args) -> bool:
        """执行完整部署流程"""
        logger.info("🚀 开始部署股票分析系统...")
        
        # 1. 环境检查
        if not self.check_environment():
            return False
        
        # 2. 安装依赖
        if not self.install_dependencies():
            return False
        
        # 3. 数据库初始化
        if not self.setup_database():
            return False
        
        # 4. 创建启动脚本
        if not self.create_startup_scripts():
            return False
        
        # 5. 创建Docker文件（可选）
        if args.docker:
            if not self.create_docker_files():
                return False
        
        # 6. 创建部署指南
        if not self.create_deployment_guide():
            return False
        
        # 7. 测试部署
        if not self.test_deployment():
            return False
        
        logger.info("🎉 部署完成!")
        logger.info("📖 请查看 DEPLOYMENT_GUIDE.md 了解详细使用说明")
        logger.info("🚀 运行 'python start_system.py' 启动系统")
        
        return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="股票分析系统部署脚本")
    parser.add_argument("--config", default="deploy_config.json", help="配置文件路径")
    parser.add_argument("--docker", action="store_true", help="创建Docker部署文件")
    parser.add_argument("--test-only", action="store_true", help="仅运行测试")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    deployer = Deployer(args.config)
    
    if args.test_only:
        success = deployer.test_deployment()
    else:
        success = deployer.deploy(args)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 