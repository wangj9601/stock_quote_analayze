# 每日报告推送系统 - 部署文档

## 目录

1. [环境要求](#环境要求)
2. [依赖安装](#依赖安装)
3. [配置说明](#配置说明)
4. [数据库初始化](#数据库初始化)
5. [启动步骤](#启动步骤)
6. [监控指标](#监控指标)
7. [故障排查](#故障排查)
8. [维护操作](#维护操作)

---

## 环境要求

### 系统要求

- **操作系统**: Linux (推荐 Ubuntu 20.04+) 或 Windows Server 2016+
- **Python版本**: Python 3.8 或更高版本
- **数据库**: PostgreSQL 12.0 或更高版本
- **内存**: 最低 2GB，推荐 4GB+
- **磁盘空间**: 最低 10GB (用于存储报告文件和日志)

### 网络要求

- 能够访问SMTP服务器 (用于邮件推送)
- 能够访问微信API服务器 (用于微信推送)
- 数据库服务器连接 (PostgreSQL)

### 第三方服务

- **SMTP服务**: Gmail、QQ邮箱、企业邮箱等
- **微信服务**: 
  - 个人微信: 需要微信公众号或服务号
  - 企业微信: 需要企业微信应用

---

## 依赖安装

### 1. 安装Python依赖

```bash
# 使用pip安装依赖
pip install -r requirements.txt

# 或使用生产环境依赖
pip install -r requirements-prod.txt
```

### 2. 核心依赖包

```
# Web框架
fastapi>=0.95.0
uvicorn>=0.21.0

# 数据库
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
alembic>=1.10.0

# 定时任务
apscheduler>=3.10.0

# 邮件
aiosmtplib>=2.0.0

# 测试
pytest>=7.3.0
hypothesis>=6.70.0

# 其他
python-dotenv>=1.0.0
pydantic>=1.10.0
```

### 3. 验证安装

```bash
python -c "import fastapi, sqlalchemy, apscheduler; print('依赖安装成功')"
```

---

## 配置说明

### 1. 环境变量配置

创建 `.env` 文件或设置系统环境变量：

```bash
# 数据库配置
DATABASE_URL=postgresql+psycopg2://username:password@localhost:5432/stock_analysis

# SMTP邮件配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_FROM_NAME=股票分析系统

# 微信配置 (企业微信)
WECHAT_CORP_ID=your_corp_id
WECHAT_AGENT_ID=your_agent_id
WECHAT_SECRET=your_secret

# 微信配置 (个人微信公众号)
WECHAT_TOKEN=your_token
WECHAT_ENCODING_AES_KEY=your_aes_key

# 推送配置
MAX_RETRY_COUNT=3
PUSH_BATCH_SIZE=100
REPORT_DIR=./reports

# JWT配置
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### 2. 配置文件说明

#### backend_api/config.py

主配置文件，包含所有系统配置。支持通过环境变量覆盖默认值。

**SMTP配置项**:
- `host`: SMTP服务器地址
- `port`: SMTP端口 (通常为587或465)
- `username`: 发件人账号
- `password`: 发件人密码或应用专用密码
- `use_tls`: 是否使用TLS加密
- `from_email`: 发件人邮箱地址
- `from_name`: 发件人显示名称

**推送配置项**:
- `max_retry_count`: 推送失败最大重试次数
- `push_batch_size`: 批量推送的批次大小
- `report_dir`: 报告文件存储目录
- `default_push_times`: 默认推送时间点 (如 ["09:30", "15:30"])

**微信配置项**:
- `corp_id`: 企业微信Corp ID
- `agent_id`: 企业微信Agent ID
- `secret`: 企业微信Secret
- `token`: 微信公众号Token
- `encoding_aes_key`: 微信公众号EncodingAESKey

### 3. Gmail SMTP配置示例

如果使用Gmail发送邮件，需要：

1. 启用两步验证
2. 生成应用专用密码
3. 使用应用专用密码作为 `SMTP_PASSWORD`

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_USE_TLS=true
```

### 4. 企业微信配置示例

1. 登录企业微信管理后台
2. 创建应用，获取 `AgentId` 和 `Secret`
3. 在"我的企业"中获取 `Corp ID`

```bash
WECHAT_CORP_ID=ww1234567890abcdef
WECHAT_AGENT_ID=1000002
WECHAT_SECRET=your_secret_key_here
```

---

## 数据库初始化

### 1. 创建数据库

```bash
# 连接到PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE stock_analysis;

# 创建用户 (可选)
CREATE USER stock_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE stock_analysis TO stock_user;
```

### 2. 运行数据库迁移

```bash
# 查看将要执行的操作 (模拟模式)
python init_db.py --dry-run

# 执行数据库迁移
python init_db.py

# 验证表结构
python init_db.py --verify

# 查看数据库状态
python init_db.py --status
```

### 3. 验证数据库表

确保以下表已创建：

- `users` - 用户表 (包含 wechat_openid, wechat_type 字段)
- `user_push_configs` - 用户推送配置表
- `push_records` - 推送记录表
- `watchlist` - 自选股表
- `historical_quotes` - A股历史行情表
- `historical_quotes_hk` - 港股历史行情表

### 4. 生成测试数据 (可选)

```bash
# 生成5个测试用户，每个用户10只自选股
python generate_test_data.py --users 5 --stocks 10

# 清除测试数据
python generate_test_data.py --clean

# 生成数据但不生成推送记录
python generate_test_data.py --users 3 --no-records
```

---

## 启动步骤

### 1. 启动API服务

```bash
# 开发环境
python start_backend_api.py

# 生产环境 (使用uvicorn)
uvicorn backend_api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 2. 启动推送调度器

```bash
# 前台运行 (用于测试)
python start_scheduler.py

# 指定推送时间点
python start_scheduler.py --push-times "09:30,15:30,21:00"

# 指定日志级别
python start_scheduler.py --log-level DEBUG

# 后台运行 (守护进程模式)
python start_scheduler.py --daemon --pid-file /var/run/scheduler.pid

# 查看日志
tail -f scheduler.log
```

### 3. 使用systemd管理服务 (Linux)

创建服务文件 `/etc/systemd/system/push-scheduler.service`:

```ini
[Unit]
Description=Stock Report Push Scheduler
After=network.target postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python start_scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start push-scheduler

# 设置开机自启
sudo systemctl enable push-scheduler

# 查看状态
sudo systemctl status push-scheduler

# 查看日志
sudo journalctl -u push-scheduler -f
```

### 4. 使用Windows服务 (Windows)

使用 `nssm` (Non-Sucking Service Manager):

```cmd
# 下载并安装nssm
# https://nssm.cc/download

# 安装服务
nssm install PushScheduler "C:\path\to\python.exe" "C:\path\to\start_scheduler.py"

# 启动服务
nssm start PushScheduler

# 查看状态
nssm status PushScheduler
```

### 5. 验证服务运行

```bash
# 检查调度器是否运行
ps aux | grep start_scheduler

# 检查PID文件
cat scheduler.pid

# 查看日志
tail -f scheduler.log

# 测试API
curl http://localhost:8000/api/push/status
```

---

## 监控指标

### 1. 关键性能指标 (KPI)

#### 推送成功率

```
推送成功率 = (成功推送数 / 总推送数) × 100%
```

**目标**: ≥ 95%

**监控方法**:
```sql
SELECT 
    COUNT(*) FILTER (WHERE status = 'success') * 100.0 / COUNT(*) as success_rate
FROM push_records
WHERE push_date >= CURRENT_DATE - INTERVAL '7 days';
```

#### 推送延迟

```
推送延迟 = 完成时间 - 计划时间
```

**目标**: ≤ 5分钟

**监控方法**:
```sql
SELECT 
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_delay_seconds
FROM push_records
WHERE status = 'success'
AND push_date >= CURRENT_DATE - INTERVAL '7 days';
```

#### 错误率

```
错误率 = (失败推送数 / 总推送数) × 100%
```

**目标**: ≤ 5%

**监控方法**:
```sql
SELECT 
    COUNT(*) FILTER (WHERE status = 'failed') * 100.0 / COUNT(*) as error_rate
FROM push_records
WHERE push_date >= CURRENT_DATE - INTERVAL '7 days';
```

### 2. 系统监控

#### 调度器健康检查

```bash
# 检查调度器进程
ps aux | grep start_scheduler

# 检查最近的推送记录
psql -d stock_analysis -c "SELECT * FROM push_records ORDER BY created_at DESC LIMIT 10;"

# 检查待推送用户数
curl http://localhost:8000/api/push/status
```

#### 日志监控

关键日志关键词：
- `ERROR` - 错误日志
- `推送失败` - 推送失败
- `重试` - 重试操作
- `SMTP connection failed` - 邮件服务故障
- `微信API错误` - 微信服务故障

```bash
# 查看错误日志
grep ERROR scheduler.log | tail -20

# 查看推送失败日志
grep "推送失败" scheduler.log | tail -20

# 统计错误数量
grep ERROR scheduler.log | wc -l
```

### 3. 数据库监控

```sql
-- 查看今日推送统计
SELECT 
    status,
    COUNT(*) as count
FROM push_records
WHERE push_date = CURRENT_DATE
GROUP BY status;

-- 查看各渠道推送情况
SELECT 
    jsonb_object_keys(channel_status) as channel,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE channel_status->jsonb_object_keys(channel_status) = '"success"') as success
FROM push_records
WHERE push_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY channel;

-- 查看重试次数分布
SELECT 
    retry_count,
    COUNT(*) as count
FROM push_records
WHERE push_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY retry_count
ORDER BY retry_count;
```

### 4. 告警规则

建议配置以下告警：

1. **推送成功率低于90%** (过去1小时)
2. **连续3次推送失败** (同一用户)
3. **调度器进程停止**
4. **数据库连接失败**
5. **SMTP服务不可用**
6. **微信API调用失败率 > 10%**

---

## 故障排查

### 1. 调度器无法启动

**症状**: 运行 `start_scheduler.py` 后立即退出

**可能原因**:
- 数据库连接失败
- 配置文件错误
- 端口被占用
- 权限不足

**排查步骤**:

```bash
# 1. 检查数据库连接
python -c "from backend_core.database.db import get_db_session; print(get_db_session())"

# 2. 检查配置文件
python -c "from backend_api.config import SMTP_CONFIG, PUSH_CONFIG; print('配置正常')"

# 3. 查看详细日志
python start_scheduler.py --log-level DEBUG

# 4. 检查PID文件
rm -f scheduler.pid
```

### 2. 推送失败

**症状**: 推送记录状态为 `failed`

**可能原因**:
- 用户未绑定推送渠道
- SMTP服务不可用
- 微信API调用失败
- 报告生成失败
- 网络问题

**排查步骤**:

```bash
# 1. 查看错误信息
psql -d stock_analysis -c "SELECT user_id, error_messages FROM push_records WHERE status = 'failed' ORDER BY created_at DESC LIMIT 5;"

# 2. 检查用户配置
psql -d stock_analysis -c "SELECT u.id, u.email, u.wechat_openid, c.channels FROM users u JOIN user_push_configs c ON u.id = c.user_id WHERE u.id = <user_id>;"

# 3. 测试SMTP连接
python -c "from backend_api.services.email_service import EmailService; from backend_api.config import SMTP_CONFIG; service = EmailService(SMTP_CONFIG); print('SMTP连接正常')"

# 4. 测试微信API
python -c "from backend_core.wechat.wechat_service import WeChatService; from backend_api.config import WECHAT_CONFIG; service = WeChatService(**WECHAT_CONFIG); print('微信API正常')"

# 5. 手动重试失败的推送
curl -X POST http://localhost:8000/api/push/records/<record_id>/retry
```

### 3. 邮件发送失败

**症状**: 邮件渠道推送失败，错误信息包含 "SMTP"

**可能原因**:
- SMTP配置错误
- 邮箱密码错误
- 未启用应用专用密码 (Gmail)
- SMTP服务器不可达
- 防火墙阻止

**排查步骤**:

```bash
# 1. 验证SMTP配置
echo $SMTP_HOST
echo $SMTP_PORT
echo $SMTP_USERNAME

# 2. 测试SMTP连接
telnet smtp.gmail.com 587

# 3. 检查防火墙
sudo iptables -L | grep 587

# 4. 查看详细错误
grep "SMTP" scheduler.log | tail -20

# 5. 使用测试脚本
python -c "
from backend_api.services.email_service import EmailService
from backend_api.config import SMTP_CONFIG
service = EmailService(SMTP_CONFIG)
result = service.send_report_email(
    to_email='test@example.com',
    subject='测试邮件',
    content='<p>这是一封测试邮件</p>',
    attachment_path=None
)
print(result)
"
```

### 4. 微信推送失败

**症状**: 微信渠道推送失败，错误信息包含 "微信API"

**可能原因**:
- 微信配置错误
- Access Token过期
- 用户未关注公众号
- 企业微信应用未授权
- API调用频率限制

**排查步骤**:

```bash
# 1. 验证微信配置
echo $WECHAT_CORP_ID
echo $WECHAT_AGENT_ID

# 2. 测试微信API
python -c "
from backend_core.wechat.wechat_service import WeChatService
from backend_api.config import WECHAT_CONFIG
service = WeChatService(**WECHAT_CONFIG)
# 测试获取access_token
print('微信API测试成功')
"

# 3. 查看详细错误
grep "微信" scheduler.log | tail -20

# 4. 检查用户OpenID
psql -d stock_analysis -c "SELECT id, username, wechat_openid, wechat_type FROM users WHERE wechat_openid IS NOT NULL;"
```

### 5. 报告生成失败

**症状**: 推送记录显示报告生成失败

**可能原因**:
- 用户没有自选股
- 历史数据缺失
- 磁盘空间不足
- 文件权限问题

**排查步骤**:

```bash
# 1. 检查用户自选股
psql -d stock_analysis -c "SELECT COUNT(*) FROM watchlist WHERE user_id = <user_id>;"

# 2. 检查历史数据
psql -d stock_analysis -c "SELECT COUNT(*) FROM historical_quotes WHERE stock_code IN (SELECT stock_code FROM watchlist WHERE user_id = <user_id>);"

# 3. 检查磁盘空间
df -h

# 4. 检查报告目录权限
ls -la ./reports

# 5. 手动生成报告测试
python -c "
from backend_api.services.report_service import ReportService
from backend_core.database.db import get_db_session
service = ReportService(get_db_session(), './reports')
result = service.generate_user_report(<user_id>, 'summary')
print(result)
"
```

### 6. 数据库连接问题

**症状**: 日志显示数据库连接错误

**可能原因**:
- 数据库服务未启动
- 连接字符串错误
- 网络问题
- 连接池耗尽

**排查步骤**:

```bash
# 1. 检查PostgreSQL服务
sudo systemctl status postgresql

# 2. 测试数据库连接
psql -h localhost -U postgres -d stock_analysis

# 3. 检查连接字符串
echo $DATABASE_URL

# 4. 查看数据库连接数
psql -d stock_analysis -c "SELECT count(*) FROM pg_stat_activity;"

# 5. 重启数据库 (谨慎操作)
sudo systemctl restart postgresql
```

### 7. 性能问题

**症状**: 推送延迟高，系统响应慢

**可能原因**:
- 并发用户数过多
- 数据库查询慢
- 报告生成耗时
- 网络延迟

**排查步骤**:

```bash
# 1. 查看系统资源
top
htop

# 2. 查看数据库慢查询
psql -d stock_analysis -c "SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# 3. 分析推送耗时
psql -d stock_analysis -c "SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds FROM push_records WHERE status = 'success' AND push_date >= CURRENT_DATE - INTERVAL '1 day';"

# 4. 调整批次大小
export PUSH_BATCH_SIZE=50

# 5. 增加数据库连接池
# 修改 backend_api/config.py 中的 pool_size 和 max_overflow
```

---

## 维护操作

### 1. 日常维护

#### 清理旧报告文件

```bash
# 删除30天前的报告文件
find ./reports -name "*.csv" -mtime +30 -delete

# 查看报告目录大小
du -sh ./reports
```

#### 清理旧推送记录

```sql
-- 删除90天前的推送记录
DELETE FROM push_records WHERE push_date < CURRENT_DATE - INTERVAL '90 days';

-- 归档旧记录 (可选)
CREATE TABLE push_records_archive AS 
SELECT * FROM push_records WHERE push_date < CURRENT_DATE - INTERVAL '90 days';
```

#### 日志轮转

```bash
# 使用logrotate配置日志轮转
# 创建 /etc/logrotate.d/push-scheduler

/path/to/project/scheduler.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 your_user your_group
}
```

### 2. 备份和恢复

#### 数据库备份

```bash
# 备份数据库
pg_dump -U postgres stock_analysis > backup_$(date +%Y%m%d).sql

# 备份特定表
pg_dump -U postgres -t users -t user_push_configs -t push_records stock_analysis > push_backup_$(date +%Y%m%d).sql

# 恢复数据库
psql -U postgres stock_analysis < backup_20240101.sql
```

#### 配置文件备份

```bash
# 备份配置文件
cp backend_api/config.py backend_api/config.py.backup
cp .env .env.backup
```

### 3. 更新和升级

#### 更新代码

```bash
# 拉取最新代码
git pull origin main

# 安装新依赖
pip install -r requirements.txt

# 运行数据库迁移
python init_db.py

# 重启服务
sudo systemctl restart push-scheduler
```

#### 回滚版本

```bash
# 回滚到指定版本
git checkout <commit_hash>

# 恢复数据库
psql -U postgres stock_analysis < backup_before_upgrade.sql

# 重启服务
sudo systemctl restart push-scheduler
```

### 4. 性能优化

#### 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_push_records_user_date ON push_records(user_id, push_date);
CREATE INDEX idx_push_records_status ON push_records(status);
CREATE INDEX idx_user_push_configs_enabled ON user_push_configs(enabled);

-- 分析表
ANALYZE users;
ANALYZE user_push_configs;
ANALYZE push_records;

-- 清理表
VACUUM FULL push_records;
```

#### 调整配置

```bash
# 增加批次大小 (如果系统资源充足)
export PUSH_BATCH_SIZE=200

# 减少重试次数 (如果失败率低)
export MAX_RETRY_COUNT=2

# 调整数据库连接池
# 修改 backend_api/config.py
DATABASE_CONFIG = {
    "pool_size": 10,  # 增加连接池大小
    "max_overflow": 20,
}
```

### 5. 安全维护

#### 更新密码

```bash
# 更新SMTP密码
export SMTP_PASSWORD=new_password

# 更新数据库密码
psql -U postgres -c "ALTER USER stock_user WITH PASSWORD 'new_password';"

# 更新JWT密钥
export JWT_SECRET_KEY=new_secret_key

# 重启服务
sudo systemctl restart push-scheduler
```

#### 审计日志

```bash
# 查看登录记录
psql -d stock_analysis -c "SELECT username, last_login FROM users ORDER BY last_login DESC LIMIT 20;"

# 查看推送记录
psql -d stock_analysis -c "SELECT user_id, push_date, status FROM push_records ORDER BY created_at DESC LIMIT 50;"

# 查看错误日志
grep ERROR scheduler.log | tail -50
```

---

## 附录

### A. 常用命令速查

```bash
# 启动调度器
python start_scheduler.py

# 停止调度器
kill $(cat scheduler.pid)

# 查看调度器状态
ps aux | grep start_scheduler

# 查看日志
tail -f scheduler.log

# 数据库迁移
python init_db.py

# 生成测试数据
python generate_test_data.py --users 5

# 查看推送状态
curl http://localhost:8000/api/push/status

# 手动触发推送
curl -X POST http://localhost:8000/api/push/trigger
```

### B. 配置文件模板

参见项目根目录下的 `env_wechat_report.example` 文件。

### C. 联系支持

如遇到无法解决的问题，请联系技术支持：

- 邮箱: support@example.com
- 文档: https://docs.example.com
- Issue: https://github.com/your-repo/issues

---

**文档版本**: 1.0.0  
**最后更新**: 2024-01-01  
**维护者**: 开发团队
