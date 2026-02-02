# GMS策略数据库字段缺失问题修复总结

## 问题描述

在使用GMS选股策略时,出现以下错误:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) 错误: 字段 mean_frequency_resonance_indicators.d1 不存在
```

## 根本原因

在 `backend_core/data_collectors/akshare/historical_collector.py` 文件的 `_init_mean_frequency_table()` 方法中,创建 `mean_frequency_resonance_indicators` 表时缺少了以下四个字段:

- `d1` (REAL) - 周期起点收盘价 d₁
- `d1_date` (VARCHAR(20)) - d₁ 对应的交易日期
- `d20` (REAL) - 周期末/当日收盘价 d₂₀  
- `d20_date` (VARCHAR(20)) - d₂₀ 对应的交易日期

虽然 SQLAlchemy 模型定义(`backend_api/models.py` 中的 `MeanFrequencyResonanceIndicators` 类)包含了这些字段,并且数据插入代码也尝试写入这些字段,但数据库表结构定义中缺少这些列,导致查询时报错。

## 修复内容

### 1. 修改表初始化代码

修改了 `backend_core/data_collectors/akshare/historical_collector.py` 文件中的 `_init_mean_frequency_table()` 方法:

**修改前:**
```python
CREATE TABLE IF NOT EXISTS mean_frequency_resonance_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,
    market_type VARCHAR(10) NOT NULL,
    macro_displacement_delta REAL,
    amplitude REAL,
    ratio_d20 REAL,
    ratio_d1 REAL,
    instant_deviation REAL,
    rising_days_z INTEGER,
    falling_days_f INTEGER,
    efficiency_m20_minus_m REAL,
    ma20_d REAL,
    mavol20_m REAL,
    bias REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type)
)
```

**修改后:**
```python
CREATE TABLE IF NOT EXISTS mean_frequency_resonance_indicators (
    code VARCHAR(20) NOT NULL,
    date VARCHAR(20) NOT NULL,
    market_type VARCHAR(10) NOT NULL,
    macro_displacement_delta REAL,
    amplitude REAL,
    ratio_d20 REAL,
    ratio_d1 REAL,
    instant_deviation REAL,
    rising_days_z INTEGER,
    falling_days_f INTEGER,
    efficiency_m20_minus_m REAL,
    ma20_d REAL,
    mavol20_m REAL,
    bias REAL,
    d1 REAL,                    -- 新增
    d1_date VARCHAR(20),        -- 新增
    d20 REAL,                   -- 新增
    d20_date VARCHAR(20),       -- 新增
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, date, market_type)
)
```

同时添加了相应的 ALTER TABLE 语句以支持已存在表的迁移:

```python
self.session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d1 REAL"))
self.session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d1_date VARCHAR(20)"))
self.session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d20 REAL"))
self.session.execute(text("ALTER TABLE mean_frequency_resonance_indicators ADD COLUMN IF NOT EXISTS d20_date VARCHAR(20)"))
```

### 2. 创建数据库迁移脚本

创建了 `backend_core/data_collectors/migrate_mean_frequency_table.py` 脚本,用于为已存在的数据库表添加缺失的字段。

### 3. 执行数据库迁移

运行迁移脚本成功添加了所有缺失的字段:

```
2026-02-02 08:40:26,152 - INFO - 添加字段 d1 成功
2026-02-02 08:40:26,220 - INFO - 添加字段 d1_date 成功
2026-02-02 08:40:26,274 - INFO - 添加字段 d20 成功
2026-02-02 08:40:26,293 - INFO - 添加字段 d20_date 成功
2026-02-02 08:40:26,443 - INFO - 所有必需字段都已存在!
```

## 验证

迁移完成后,表中包含以下所有字段:

```
code, date, market_type, macro_displacement_delta, instant_deviation, 
rising_days_z, falling_days_f, efficiency_m20_minus_m, ma20_d, 
mavol20_m, created_at, bias, amplitude, ratio_d20, ratio_d1, 
d1, d1_date, d20, d20_date
```

## 影响范围

- **修改的文件:**
  - `backend_core/data_collectors/akshare/historical_collector.py`
  
- **新增的文件:**
  - `backend_core/data_collectors/migrate_mean_frequency_table.py`

- **影响的功能:**
  - GMS选股策略查询
  - 均值频率共振指标数据采集
  - PVFRS相关功能

## 后续建议

1. 在未来添加新字段时,确保同时更新:
   - SQLAlchemy 模型定义 (`models.py`)
   - 表创建 SQL 语句 (`_init_*_table` 方法)
   - 数据插入/更新语句
   - ALTER TABLE 迁移语句

2. 考虑使用 Alembic 等数据库迁移工具来管理数据库架构变更,避免手动维护 SQL 语句。

3. 建议在开发环境和生产环境都运行一次迁移脚本,确保所有环境的数据库结构一致。

## 修复日期

2026-02-02
