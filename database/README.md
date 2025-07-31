# PostgreSQL数据库迁移工具

本目录包含了股票分析系统的PostgreSQL数据库迁移脚本和工具。

## 文件说明

### 1. migration_script.sql
完整的数据库迁移脚本，包含：
- 表结构创建
- 索引创建
- 视图创建
- 触发器创建
- 数据导出/导入命令示例

### 2. export_data.py
Python数据导出脚本，提供交互式菜单：
- 导出数据库结构
- 导出所有数据
- 导出完整数据库备份
- 导出特定表数据
- 导出所有主要表数据

### 3. import_data.py
Python数据导入脚本，提供交互式菜单：
- 导入完整数据库备份
- 仅导入表结构
- 仅导入数据
- 备份当前数据库

### 4. quick_export.bat
Windows批处理脚本，快速导出数据库：
- 完整数据库备份
- 表结构
- 数据
- 主要表数据

## 使用方法

### 方法1: 使用Python脚本（推荐）

#### 导出数据
```bash
cd database
python export_data.py
```

#### 导入数据
```bash
cd database
python import_data.py
```

### 方法2: 使用批处理脚本（Windows）

```bash
cd database
quick_export.bat
```

### 方法3: 手动执行SQL命令

#### 导出命令
```bash
# 导出完整数据库
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis > full_backup.sql

# 导出表结构
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis --schema-only > schema_backup.sql

# 导出数据
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis --data-only > data_backup.sql

# 导出特定表
pg_dump -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis -t stock_realtime_quote --data-only > stock_realtime_quote_data.sql
```

#### 导入命令
```bash
# 导入完整数据库
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < full_backup.sql

# 导入表结构
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < schema_backup.sql

# 导入数据
psql -h 192.168.31.237 -p 5446 -U postgres -d stock_analysis < data_backup.sql
```

## 数据库表结构

### 核心表
1. **users** - 用户表
2. **admins** - 管理员表
3. **stock_basic_info** - 股票基本信息表
4. **stock_realtime_quote** - 实时行情表
5. **historical_quotes** - 历史行情表
6. **watchlist** - 自选股表
7. **watchlist_groups** - 自选股分组表
8. **stock_news** - 股票新闻表
9. **stock_notice_report** - 股票公告表
10. **stock_research_report** - 股票研报表
11. **quote_data** - 行情数据表
12. **quote_sync_tasks** - 行情同步任务表

### 日志表
1. **watchlist_history_collection_logs** - 自选股历史采集日志表

## 注意事项

### 1. 环境要求
- 确保已安装PostgreSQL客户端工具（pg_dump, psql）
- 确保Python环境已安装
- 确保有数据库连接权限

### 2. 安全注意事项
- 数据库密码会显示在脚本中，生产环境请使用环境变量
- 导入操作会覆盖现有数据，请先备份
- 建议在测试环境验证后再在生产环境使用

### 3. 性能考虑
- 大数据量导出可能需要较长时间
- 建议在数据库负载较低时进行导出操作
- 可以考虑使用并行导出提高效率

### 4. 错误处理
- 如果导出失败，检查网络连接和数据库权限
- 如果导入失败，检查SQL文件格式和数据库版本兼容性
- 查看错误日志获取详细信息

## 常见问题

### Q: 导出时提示权限错误
A: 检查数据库用户权限，确保有SELECT权限

### Q: 导入时提示表已存在
A: 使用`--clean`参数或手动删除现有表

### Q: 数据量很大，导出很慢
A: 考虑分批导出或使用并行导出

### Q: 导入后数据不完整
A: 检查SQL文件是否完整，确认没有截断

## 联系支持

如果遇到问题，请检查：
1. 数据库连接配置是否正确
2. 网络连接是否正常
3. 数据库服务是否运行
4. 用户权限是否足够 