# 数据采集API服务与管理端页面使用说明

## 🎯 概述

本文档介绍数据采集程序的API服务封装和管理端页面功能，实现了从命令行工具到Web服务的完整迁移。

## 📋 系统架构

### 1. 后端API服务
- **位置**: `backend_api/stock/data_collection_api.py`
- **功能**: 提供RESTful API接口
- **技术栈**: FastAPI + SQLAlchemy + Background Tasks

### 2. 管理端页面
- **位置**: `admin/datacollect.html`
- **功能**: 提供Web界面操作
- **技术栈**: Vue.js + Element Plus + Tailwind CSS

### 3. 数据采集核心
- **位置**: `backend_core/data_collectors/akshare/historical_collector.py`
- **功能**: 实际的数据采集逻辑
- **技术栈**: akshare + pandas + SQLAlchemy

### 4. A股历史采集数据源回退策略（新增）
- 入口：`backend_api/stock/data_collection_api.py` 的 A股历史采集逻辑
- 策略：
  1. 优先调用东方财富接口 `ak.stock_zh_a_hist`
  2. 若东财接口异常或无数据，自动回退新浪接口 `ak.stock_zh_a_daily`
- 结果标记：
  - `collected_source = akshare_eastmoney`（东财）
  - `collected_source = akshare_sina`（新浪回退）
- 作用：降低外部源瞬时失败导致的任务失败率，提升管理端“历史数据采集-AkShare”稳定性

## 🚀 API接口说明

### 1. 启动历史数据采集

**接口**: `POST /data-collection/historical`

**请求参数**:
```json
{
    "start_date": "2025-08-01",
    "end_date": "2025-09-03",
    "stock_codes": ["000001", "000002"],  // 可选
    "test_mode": false  // 可选
}
```

**响应**:
```json
{
    "task_id": "historical_collection_20250904_143022_12345",
    "status": "started",
    "message": "历史数据采集任务已启动",
    "start_date": "2025-08-01",
    "end_date": "2025-09-03",
    "stock_codes": null,
    "test_mode": false
}
```

### 2. 获取任务状态

**接口**: `GET /data-collection/status/{task_id}`

**响应**:
```json
{
    "task_id": "historical_collection_20250904_143022_12345",
    "status": "running",
    "progress": 45,
    "total_stocks": 100,
    "processed_stocks": 45,
    "success_count": 43,
    "failed_count": 2,
    "collected_count": 1250,
    "skipped_count": 0,
    "start_time": "2025-09-04T14:30:22",
    "end_time": null,
    "error_message": null,
    "failed_details": []
}
```

### 3. 获取任务列表

**接口**: `GET /data-collection/tasks`

**响应**:
```json
[
    {
        "task_id": "historical_collection_20250904_143022_12345",
        "status": "completed",
        "progress": 100,
        "total_stocks": 100,
        "processed_stocks": 100,
        "success_count": 98,
        "failed_count": 2,
        "collected_count": 2500,
        "skipped_count": 0,
        "start_time": "2025-09-04T14:30:22",
        "end_time": "2025-09-04T14:35:15",
        "error_message": null,
        "failed_details": []
    }
]
```

### 4. 取消任务

**接口**: `DELETE /data-collection/tasks/{task_id}`

**响应**:
```json
{
    "message": "任务已取消",
    "task_id": "historical_collection_20250904_143022_12345"
}
```

### 5. 获取股票列表

**接口**: `GET /data-collection/stock-list`

**响应**:
```json
{
    "total": 5417,
    "stocks": [
        {
            "code": "000001",
            "name": "平安银行"
        },
        {
            "code": "000002",
            "name": "万科A"
        }
    ]
}
```

## 🖥️ 管理端页面功能

### 1. 页面特性
- ✅ 响应式设计，支持移动端
- ✅ 实时任务状态更新
- ✅ 进度条显示
- ✅ 任务取消功能
- ✅ 错误信息展示
- ✅ 表单验证

### 2. 主要功能模块

#### 2.1 采集配置
- **日期范围选择**: 开始日期和结束日期
- **股票选择**: 支持采集所有股票或指定股票代码
- **测试模式**: 只采集前5只股票进行测试
- **表单验证**: 确保输入数据有效性

#### 2.2 任务管理
- **任务列表**: 显示所有采集任务
- **状态显示**: 运行中、已完成、失败、已取消
- **进度监控**: 实时显示任务进度
- **统计信息**: 成功数、失败数、新增数据量
- **任务取消**: 支持取消正在运行的任务

#### 2.3 实时更新
- **自动刷新**: 每5秒自动刷新任务状态
- **实时进度**: 动态更新进度条
- **状态变化**: 及时反映任务状态变化

## 🔧 部署和使用

### 1. 启动API服务

```bash
# 进入项目目录
cd stock_quote_analayze

# 启动API服务
python backend_api/main.py
```

### 2. 访问管理端页面

```
http://localhost:8000/admin/datacollect.html
```

### 3. 测试API服务

```bash
# 运行测试脚本
python test/test_data_collection_api.py
```

## 📊 使用流程

### 1. 基本使用流程

1. **打开管理端页面**
   - 访问 `http://localhost:8000/admin/datacollect.html`

2. **配置采集参数**
   - 选择日期范围
   - 选择股票范围（全部或指定）
   - 可选择测试模式

3. **启动采集任务**
   - 点击"开始采集"按钮
   - 系统会返回任务ID

4. **监控任务进度**
   - 页面会自动刷新显示任务状态
   - 查看进度条和统计信息

5. **查看结果**
   - 任务完成后查看采集结果
   - 如有失败可查看错误详情

### 2. 高级功能

#### 2.1 批量采集
```javascript
// 通过API批量启动多个任务
const tasks = [
    { start_date: "2025-08-01", end_date: "2025-08-31" },
    { start_date: "2025-09-01", end_date: "2025-09-30" }
];

for (const task of tasks) {
    await axios.post('/data-collection/historical', task);
}
```

#### 2.2 任务监控
```javascript
// 监控特定任务
const taskId = "historical_collection_20250904_143022_12345";
const status = await axios.get(`/data-collection/status/${taskId}`);
console.log(`任务进度: ${status.data.progress}%`);
```

## ⚙️ 配置说明

### 1. API配置

**文件**: `backend_api/main.py`

```python
# 注册数据采集路由
from stock.data_collection_api import router as data_collection_router
app.include_router(data_collection_router)
```

### 2. 数据库配置

**文件**: `backend_api/database.py`

确保数据库连接配置正确，支持PostgreSQL。

### 3. 日志配置

**文件**: `backend_api/stock/data_collection_api.py`

```python
logger = logging.getLogger(__name__)
```

## 🔍 故障排除

### 1. 常见问题

#### 1.1 API服务无法启动
- 检查端口是否被占用
- 确认依赖包已安装
- 查看错误日志

#### 1.2 数据库连接失败
- 检查数据库服务状态
- 确认连接配置正确
- 验证数据库权限

#### 1.3 采集任务失败
- 检查网络连接
- 确认akshare可用性
- 查看详细错误信息
- 若日志出现东财接口连接中断（如 `Remote end closed connection without response`），系统会自动回退新浪接口；可重点关注最终 `collected_source` 与失败明细

### 2. 调试方法

#### 2.1 查看API日志
```bash
tail -f app.log
```

#### 2.2 测试API端点
```bash
curl http://localhost:8000/data-collection/stock-list
```

#### 2.3 检查任务状态
```bash
curl http://localhost:8000/data-collection/tasks
```

## 📈 性能优化

### 1. 并发控制
- 使用后台任务避免阻塞
- 合理设置请求间隔
- 支持任务取消

### 2. 内存管理
- 及时释放数据库连接
- 避免大量数据加载到内存
- 使用流式处理

### 3. 错误处理
- 完善的异常捕获
- 详细的错误日志
- 优雅的失败处理

## 🔮 扩展功能

### 1. 计划任务
- 支持定时采集
- 周期性数据更新
- 自动重试机制

### 2. 数据源扩展
- 支持更多数据源
- 数据源切换功能
- 数据质量检查

### 3. 监控告警
- 任务失败告警
- 性能监控
- 资源使用统计

---

**版本**: 1.0.0  
**创建时间**: 2025-09-04  
**适用环境**: Python 3.7+, FastAPI, Vue.js
