# PVFRS策略回测数据库表说明

## 概述

PVFRS (Price-Volume-Frequency Resonance Strategy) 策略回测系统包含4个核心数据表,用于存储回测任务、结果、交易记录和收益曲线数据。

## 表结构

### 1. pvfrs_backtest_tasks (回测任务表)

存储PVFRS策略的回测任务信息。

**字段说明:**

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | 主键ID |
| task_id | VARCHAR(50) | UNIQUE, NOT NULL, INDEX | 任务唯一标识 |
| mode | VARCHAR(20) | NOT NULL | 回测模式: single(单股), batch(批量), optimize(优化) |
| stock_codes | TEXT | | 股票代码列表(JSON格式) |
| market | VARCHAR(10) | NOT NULL | 市场类型: CN(A股), HK(港股) |
| start_date | DATE | NOT NULL | 回测开始日期 |
| end_date | DATE | NOT NULL | 回测结束日期 |
| initial_capital | FLOAT | NOT NULL | 初始资金 |
| status | VARCHAR(20) | DEFAULT 'running' | 任务状态: running, completed, failed, cancelled |
| progress | INTEGER | DEFAULT 0 | 进度百分比 (0-100) |
| current_step | VARCHAR(50) | | 当前执行步骤描述 |
| error_message | TEXT | | 错误信息 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |
| completed_at | DATETIME | NULLABLE | 完成时间 |

**索引:**
- `task_id` (UNIQUE)

---

### 2. pvfrs_backtest_results (回测结果表)

存储每个股票的回测结果统计数据。

**字段说明:**

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | 主键ID |
| task_id | VARCHAR(50) | FOREIGN KEY, NOT NULL, INDEX | 关联任务ID |
| stock_code | VARCHAR(20) | NOT NULL, INDEX | 股票代码 |
| market | VARCHAR(10) | NOT NULL | 市场类型 |
| backtest_date | DATE | NOT NULL | 回测日期 |
| start_date | DATE | NOT NULL | 回测开始日期 |
| end_date | DATE | NOT NULL | 回测结束日期 |
| initial_capital | FLOAT | NOT NULL | 初始资金 |
| final_capital | FLOAT | NOT NULL | 最终资金 |
| total_return | FLOAT | NOT NULL | 总收益率 (%) |
| annual_return | FLOAT | NOT NULL | 年化收益率 (%) |
| max_drawdown | FLOAT | NOT NULL | 最大回撤 (%) |
| sharpe_ratio | FLOAT | NOT NULL | 夏普比率 |
| win_rate | FLOAT | NOT NULL | 胜率 (%) |
| profit_factor | FLOAT | NOT NULL | 盈亏比 |
| total_trades | INTEGER | NOT NULL | 总交易次数 |
| avg_holding_period | FLOAT | NOT NULL | 平均持仓天数 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |

**索引:**
- `task_id` (INDEX)
- `stock_code` (INDEX)

**外键:**
- `task_id` -> `pvfrs_backtest_tasks.task_id`

**关系:**
- 一个任务可以有多个结果 (一对多)

---

### 3. pvfrs_trade_records (交易记录表)

存储回测过程中的每笔交易详情。

**字段说明:**

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | 主键ID |
| result_id | INTEGER | FOREIGN KEY, NOT NULL | 关联回测结果ID |
| stock_code | VARCHAR(20) | NOT NULL | 股票代码 |
| market | VARCHAR(10) | NOT NULL | 市场类型 |
| entry_date | DATE | NOT NULL | 入场日期 |
| exit_date | DATE | NOT NULL | 出场日期 |
| entry_price | FLOAT | NOT NULL | 入场价格 |
| exit_price | FLOAT | NOT NULL | 出场价格 |
| pnl | FLOAT | NOT NULL | 盈亏金额 |
| pnl_percent | FLOAT | NOT NULL | 盈亏百分比 (%) |
| exit_reason | TEXT | NOT NULL | 出场原因 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |

**外键:**
- `result_id` -> `pvfrs_backtest_results.id`

**关系:**
- 一个回测结果可以有多条交易记录 (一对多)

---

### 4. pvfrs_equity_curves (收益曲线表)

存储回测过程中每日的资金曲线数据。

**字段说明:**

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTO_INCREMENT | 主键ID |
| result_id | INTEGER | FOREIGN KEY, NOT NULL | 关联回测结果ID |
| stock_code | VARCHAR(20) | NOT NULL | 股票代码 |
| market | VARCHAR(10) | NOT NULL | 市场类型 |
| curve_date | DATE | NOT NULL | 日期 |
| equity | FLOAT | NOT NULL | 当日权益 |
| created_at | DATETIME | DEFAULT NOW() | 创建时间 |

**索引:**
- `idx_result_curve_date` (result_id, curve_date) - 复合索引

**外键:**
- `result_id` -> `pvfrs_backtest_results.id`

**关系:**
- 一个回测结果可以有多条收益曲线记录 (一对多)

---

## 表关系图

```
pvfrs_backtest_tasks (1)
    ↓
pvfrs_backtest_results (N)
    ↓
    ├── pvfrs_trade_records (N)
    └── pvfrs_equity_curves (N)
```

## 使用示例

### 1. 创建回测任务

```python
from backend_api.models import PVFRSBacktestTask
from backend_api.database import SessionLocal
from datetime import datetime, date
import json

db = SessionLocal()

task = PVFRSBacktestTask(
    task_id="pvfrs_20260115_001",
    mode="batch",
    stock_codes=json.dumps(["000001", "600000", "000002"]),
    market="CN",
    start_date=date(2023, 1, 1),
    end_date=date(2025, 12, 31),
    initial_capital=100000.0,
    status="running",
    progress=0
)

db.add(task)
db.commit()
```

### 2. 保存回测结果

```python
from backend_api.models import PVFRSBacktestResult

result = PVFRSBacktestResult(
    task_id="pvfrs_20260115_001",
    stock_code="000001",
    market="CN",
    backtest_date=date.today(),
    start_date=date(2023, 1, 1),
    end_date=date(2025, 12, 31),
    initial_capital=100000.0,
    final_capital=150000.0,
    total_return=50.0,
    annual_return=15.5,
    max_drawdown=-12.5,
    sharpe_ratio=1.8,
    win_rate=65.0,
    profit_factor=2.1,
    total_trades=45,
    avg_holding_period=8.5
)

db.add(result)
db.commit()
```

### 3. 记录交易

```python
from backend_api.models import PVFRSTradeRecord

trade = PVFRSTradeRecord(
    result_id=result.id,
    stock_code="000001",
    market="CN",
    entry_date=date(2023, 3, 15),
    exit_date=date(2023, 3, 25),
    entry_price=10.50,
    exit_price=11.20,
    pnl=700.0,
    pnl_percent=6.67,
    exit_reason="止盈信号触发"
)

db.add(trade)
db.commit()
```

### 4. 保存收益曲线

```python
from backend_api.models import PVFRSEquityCurve

curve = PVFRSEquityCurve(
    result_id=result.id,
    stock_code="000001",
    market="CN",
    curve_date=date(2023, 3, 15),
    equity=102500.0
)

db.add(curve)
db.commit()
```

### 5. 查询回测结果

```python
from sqlalchemy import desc

# 查询某个任务的所有结果
results = db.query(PVFRSBacktestResult)\
    .filter(PVFRSBacktestResult.task_id == "pvfrs_20260115_001")\
    .order_by(desc(PVFRSBacktestResult.total_return))\
    .all()

# 查询某个结果的所有交易记录
trades = db.query(PVFRSTradeRecord)\
    .filter(PVFRSTradeRecord.result_id == result.id)\
    .all()

# 查询收益曲线
equity_curve = db.query(PVFRSEquityCurve)\
    .filter(PVFRSEquityCurve.result_id == result.id)\
    .order_by(PVFRSEquityCurve.curve_date)\
    .all()
```

## 注意事项

1. **任务ID唯一性**: `task_id` 必须全局唯一,建议使用时间戳+序号的格式
2. **外键约束**: 删除任务或结果时需要注意级联删除相关记录
3. **JSON存储**: `stock_codes` 字段使用JSON格式存储,需要序列化/反序列化
4. **日期格式**: 所有日期字段使用 `DATE` 类型,时间字段使用 `DATETIME` 类型
5. **百分比存储**: 收益率、回撤等百分比数据以实际百分比值存储(如 50.0 表示 50%)

## 维护脚本

- **创建表**: `python backend_api/create_pvfrs_tables.py`
- **验证表**: `python backend_api/verify_pvfrs_tables.py`

---

**创建时间**: 2026-01-15  
**版本**: 1.0  
**状态**: ✅ 已创建并验证
