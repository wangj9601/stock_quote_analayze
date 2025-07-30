# 股票分析系统部署总结

## 📋 项目概述

股票分析系统是一个基于 FastAPI + SQLAlchemy + HTML/CSS/JavaScript 开发的完整股票分析平台，提供实时行情、历史数据、个股分析、自选股管理等功能。

## 🚀 部署方案

### 方案一：一键部署（推荐）

#### 1. 使用部署脚本
```bash
# 运行部署脚本
python deploy.py

# 启动系统
python start_system.py
```

#### 2. 使用打包的部署包
```bash
# 解压部署包
unzip stock_quote_analyze_deploy_v*.zip

# Windows用户双击运行
deploy.bat

# Linux/macOS用户运行
chmod +x deploy.sh
./deploy.sh
```

### 方案二：Docker部署

#### 1. 构建镜像
```bash
docker build -t stock-analyzer .
```

#### 2. 运行容器
```bash
# 单容器运行
docker run -d -p 5000:5000 -p 8000:8000 -p 8001:8001 stock-analyzer

# 使用Docker Compose
docker-compose up -d
```

### 方案三：手动部署

#### 1. 环境准备
```bash
# 检查Python版本（需要3.8+）
python --version

# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

#### 2. 安装依赖
```bash
# 安装主项目依赖
pip install -r requirements.txt

# 安装backend_core依赖
pip install -r backend_core/requirements.txt

# 安装backend_api依赖
pip install -r backend_api/requirements.txt
```

#### 3. 数据库初始化
```bash
# 运行数据库迁移
python migrate_db.py

# 测试数据库连接
python test_deploy_db.py
```

#### 4. 启动服务
```bash
# 一键启动所有服务
python start_system.py

# 或分别启动
python run.py              # 后端API
python start_frontend.py   # 前端服务
```

## 📦 打包部署

### 1. 创建部署包
```bash
# 创建所有格式的包
python package.py --format all

# 创建特定格式的包
python package.py --format deploy    # 部署专用包
python package.py --format minimal   # 最小化包
python package.py --format zip       # ZIP包
python package.py --format tar       # TAR包
```

### 2. 包文件说明
- `stock_quote_analyze_deploy_v*.zip` - 部署专用包，包含完整部署脚本
- `stock_quote_analyze_minimal_v*.zip` - 最小化包，仅包含运行时必需文件
- `stock_quote_analyze_v*.zip` - 完整项目包
- `stock_quote_analyze_v*.tar.gz` - Linux/macOS格式包

## 🌐 访问地址

部署成功后，可通过以下地址访问：

- **登录页面**: http://localhost:8000/login.html
- **首页**: http://localhost:8000/index.html
- **后端API**: http://localhost:5000
- **管理后台**: http://localhost:8001/
- **API文档**: http://localhost:5000/docs

## ⚙️ 配置说明

### 1. 端口配置
编辑 `deploy_config.json` 文件：
```json
{
  "ports": {
    "backend": 5000,    // 后端API端口
    "frontend": 8000,   // 前端端口
    "admin": 8001       // 管理后台端口
  }
}
```

### 2. 数据库配置
```json
{
  "database": {
    "type": "sqlite",
    "path": "database/stock_analysis.db",
    "backup_enabled": true,
    "backup_interval": "daily"
  }
}
```

### 3. 数据源配置
```json
{
  "data_sources": {
    "akshare": {
      "enabled": true,
      "timeout": 30,
      "retry_count": 3
    },
    "tushare": {
      "enabled": false,
      "token": "",
      "timeout": 30
    }
  }
}
```

## 🔧 生产环境部署

### 1. 使用Gunicorn
```bash
# 安装Gunicorn
pip install gunicorn

# 启动后端服务
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend_api.main:app --bind 0.0.0.0:5000
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

## 📊 系统功能

### 核心功能
- ✅ 实时股票行情数据
- ✅ 历史行情查询和导出
- ✅ 个股详细分析
- ✅ 自选股管理
- ✅ K线图表展示
- ✅ 用户登录注册
- ✅ 价格提醒功能
- ✅ 财经新闻资讯
- ✅ 管理后台界面

### 技术特性
- 🔄 自动数据采集（akshare/tushare）
- 📈 技术指标计算
- 🔐 JWT身份认证
- 🌐 CORS跨域支持
- 📝 详细日志记录
- 🧪 完整测试覆盖

## 🔍 故障排除

### 常见问题

#### 1. 端口冲突
```bash
# 检查端口占用
netstat -tulpn | grep :5000
netstat -tulpn | grep :8000

# 修改配置文件中的端口
```

#### 2. 依赖安装失败
```bash
# 升级pip
python -m pip install --upgrade pip

# 清理缓存
pip cache purge

# 重新安装
pip install -r requirements.txt
```

#### 3. 数据库问题
```bash
# 检查数据库文件
ls -la database/

# 重新初始化数据库
python migrate_db.py

# 测试数据库连接
python test_deploy_db.py
```

#### 4. 权限问题
```bash
# Linux/macOS设置执行权限
chmod +x *.sh
chmod +x deploy.sh
```

### 日志查看
```bash
# 查看部署日志
tail -f deploy.log

# 查看应用日志
tail -f logs/app.log

# 查看系统日志
journalctl -u stock-analyzer -f
```

## 📈 性能优化

### 1. 数据库优化
- 定期清理历史数据
- 创建必要的索引
- 配置数据库连接池

### 2. 缓存策略
- 使用Redis缓存热点数据
- 实现数据预加载
- 配置CDN加速静态资源

### 3. 监控告警
- 配置系统监控
- 设置性能告警
- 定期备份数据

## 🔒 安全建议

### 1. 生产环境配置
- 修改默认JWT密钥
- 配置HTTPS
- 限制CORS来源
- 启用防火墙

### 2. 数据安全
- 定期备份数据库
- 加密敏感数据
- 实施访问控制
- 监控异常访问

## 📞 技术支持

### 文档资源
- `README.md` - 项目介绍
- `QUICK_DEPLOY.md` - 快速部署指南
- `DEPLOYMENT_GUIDE.md` - 详细部署指南
- `docs/` - 技术文档

### 联系方式
如遇问题请检查：
1. Python版本是否符合要求（3.8+）
2. 依赖包是否正确安装
3. 端口是否被占用
4. 数据库文件权限
5. 网络连接是否正常

---

💡 **提示**: 建议首次部署使用一键部署方案，系统会自动完成所有配置和启动步骤。 