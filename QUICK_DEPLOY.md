# 股票分析系统快速部署指南

## 🚀 一键部署（推荐）

### Windows 用户
```bash
# 1. 解压项目文件
# 2. 双击运行 deploy.bat
# 3. 等待部署完成，系统自动启动
```

### Linux/macOS 用户
```bash
# 1. 解压项目文件
# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

## 📋 环境要求

- **Python**: 3.8 或更高版本
- **PostgreSQL**: 12 或更高版本
- **操作系统**: Windows 10+, Linux, macOS
- **内存**: 4GB 以上
- **磁盘空间**: 2GB 以上
- **网络**: 需要连接互联网获取股票数据

## 🔧 手动部署步骤

### 1. 检查Python环境
```bash
python --version
# 或
python3 --version
```

### 2. 安装依赖
```bash
# 安装主项目依赖
pip install -r requirements.txt

# 安装backend_core依赖
pip install -r backend_core/requirements.txt

# 安装backend_api依赖
pip install -r backend_api/requirements.txt
```

### 3. 初始化数据库
```bash
# 初始化PostgreSQL数据库
python init_postgresql_db.py

# 运行数据库迁移
python migrate_db.py
```

### 4. 启动系统
```bash
python start_system.py
```

## 🌐 访问系统

部署成功后，可以通过以下地址访问：

- **登录页面**: http://localhost:8000/login.html
- **首页**: http://localhost:8000/index.html
- **后端API**: http://localhost:5000
- **管理后台**: http://localhost:8001/

## 🐳 Docker部署

### 1. 构建镜像
```bash
docker build -t stock-analyzer .
```

### 2. 运行容器
```bash
docker run -d -p 5000:5000 -p 8000:8000 -p 8001:8001 stock-analyzer
```

### 3. 使用Docker Compose（推荐）
```bash
# 启动所有服务（包括PostgreSQL数据库）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## ⚙️ 配置说明

编辑 `deploy_config.json` 文件来修改配置：

```json
{
  "ports": {
    "backend": 5000,    // 后端API端口
    "frontend": 8000,   // 前端端口
    "admin": 8001       // 管理后台端口
  },
  "database": {
    "type": "postgresql",
    "host": "192.168.31.237",
    "port": 5446,
    "name": "stock_analysis",
    "user": "postgres",
    "password": "qidianspacetime"
  }
}
```

## 🔍 常见问题

### 1. 端口被占用
修改 `deploy_config.json` 中的端口配置，或停止占用端口的程序。

### 2. 依赖安装失败
```bash
# 升级pip
python -m pip install --upgrade pip

# 清理缓存
pip cache purge

# 重新安装
pip install -r requirements.txt
```

### 3. 数据库连接失败
```bash
# 检查PostgreSQL服务状态
sudo systemctl status postgresql

# 检查数据库连接
python test_deploy_db.py

# 重新初始化数据库
python init_postgresql_db.py
python migrate_db.py
```

### 4. 权限问题（Linux/macOS）
```bash
# 设置执行权限
chmod +x *.sh
chmod +x deploy.sh
```

## 📊 系统功能

- ✅ 实时股票行情数据
- ✅ 历史行情查询和导出
- ✅ 个股详细分析
- ✅ 自选股管理
- ✅ K线图表展示
- ✅ 用户登录注册
- ✅ 价格提醒功能
- ✅ 财经新闻资讯
- ✅ 管理后台界面

## 🛠 技术支持

如遇问题请检查：

1. Python版本是否符合要求（3.8+）
2. 依赖包是否正确安装
3. 端口是否被占用
4. 数据库文件权限
5. 网络连接是否正常

更多详细信息请查看 `DEPLOYMENT_GUIDE.md` 文件。

---

💡 **提示**: 首次使用建议运行一键部署脚本，系统会自动完成所有配置和启动步骤。 