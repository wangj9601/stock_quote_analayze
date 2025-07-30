# PostgreSQL迁移指南

## 概述

本指南说明如何将股票分析系统从SQLite数据库迁移到PostgreSQL数据库。

## 迁移前准备

### 1. 安装PostgreSQL

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

#### CentOS/RHEL
```bash
sudo yum install postgresql postgresql-server
sudo postgresql-setup initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

#### Windows
1. 下载PostgreSQL安装包：https://www.postgresql.org/download/windows/
2. 运行安装程序，按提示完成安装
3. 记住设置的密码

#### macOS
```bash
brew install postgresql
brew services start postgresql
```

### 2. 安装Python PostgreSQL驱动

```bash
pip install psycopg2-binary
```

### 3. 配置PostgreSQL

#### 创建数据库用户
```bash
# 切换到postgres用户
sudo -u postgres psql

# 创建数据库用户（可选）
CREATE USER stock_user WITH PASSWORD 'your_password';

# 创建数据库
CREATE DATABASE stock_analysis OWNER stock_user;

# 授权
GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO stock_user;

# 退出
\q
```

## 迁移步骤

### 1. 备份现有数据

如果要从SQLite迁移现有数据：

```bash
# 备份SQLite数据库
cp database/stock_analysis.db database/stock_analysis.db.backup

# 导出数据（可选）
python export_sqlite_data.py
```

### 2. 更新配置文件

编辑 `deploy_config.json`：

```json
{
  "database": {
    "type": "postgresql",
    "host": "localhost",
    "port": 5432,
    "name": "stock_analysis",
    "user": "postgres",
    "password": "your_password",
    "pool_size": 5,
    "max_overflow": 10
  }
}
```

### 3. 初始化PostgreSQL数据库

```bash
# 运行PostgreSQL环境检查
python check_postgresql_env.py

# 初始化PostgreSQL数据库
python init_postgresql_db.py

# 运行数据库迁移
python migrate_db.py

# 测试数据库连接
python test_deploy_db.py
```

### 4. 数据迁移（可选）

如果有现有SQLite数据需要迁移：

```bash
# 运行数据迁移脚本
python migrate_sqlite_to_postgresql.py
```

## 验证迁移

### 1. 检查数据库连接

```bash
python test_deploy_db.py
```

### 2. 启动系统测试

```bash
python start_system.py
```

### 3. 访问系统验证

- 前端：http://localhost:8000
- 后端API：http://localhost:5000
- 管理后台：http://localhost:8001

## Docker部署

### 1. 使用Docker Compose（推荐）

```bash
# 启动所有服务（包括PostgreSQL）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 2. 手动Docker部署

```bash
# 启动PostgreSQL容器
docker run -d \
  --name postgres \
  -e POSTGRES_DB=stock_analysis \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=qidianspacetime \
  -p 5446:5432 \
  postgres:13

# 启动应用容器
docker run -d \
  --name stock-analyzer \
  --link postgres:postgres \
  -p 5000:5000 \
  -p 8000:8000 \
  -p 8001:8001 \
  stock-analyzer
```

## 性能优化

### 1. PostgreSQL配置优化

编辑 `postgresql.conf`：

```ini
# 内存配置
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

# 连接配置
max_connections = 100

# 日志配置
log_statement = 'all'
log_duration = on
```

### 2. 索引优化

```sql
-- 为常用查询创建索引
CREATE INDEX idx_quote_data_stock_date ON quote_data(stock_code, trade_date);
CREATE INDEX idx_quote_data_date ON quote_data(trade_date);
CREATE INDEX idx_watchlist_user ON watchlist(user_id);
CREATE INDEX idx_stock_basic_code ON stock_basic_info(stock_code);
```

## 故障排除

### 1. 连接失败

```bash
# 检查PostgreSQL服务状态
sudo systemctl status postgresql

# 检查端口监听
netstat -tlnp | grep 5432

# 检查防火墙
sudo ufw status
```

### 2. 权限问题

```bash
# 检查用户权限
sudo -u postgres psql -c "\du"

# 重新授权
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO postgres;"
```

### 3. 数据迁移失败

```bash
# 检查数据完整性
python check_data_integrity.py

# 重新运行迁移
python init_postgresql_db.py
python migrate_db.py
```

## 回滚方案

如果需要回滚到SQLite：

### 1. 更新配置

```json
{
  "database": {
    "type": "sqlite",
    "path": "database/stock_analysis.db"
  }
}
```

### 2. 恢复数据

```bash
# 恢复SQLite数据库
cp database/stock_analysis.db.backup database/stock_analysis.db

# 重新启动系统
python start_system.py
```

## 监控和维护

### 1. 数据库监控

```bash
# 查看数据库大小
psql -c "SELECT pg_size_pretty(pg_database_size('stock_analysis'));"

# 查看表大小
psql -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public';"
```

### 2. 备份策略

```bash
# 创建备份脚本
#!/bin/bash
pg_dump -h localhost -U postgres stock_analysis > backup_$(date +%Y%m%d_%H%M%S).sql

# 设置定时备份
crontab -e
# 添加：0 2 * * * /path/to/backup_script.sh
```

## 技术支持

如遇问题请检查：

1. PostgreSQL版本是否兼容（推荐12+）
2. 连接参数是否正确
3. 用户权限是否足够
4. 网络连接是否正常
5. 防火墙设置是否正确

更多详细信息请查看项目文档或联系技术支持。 