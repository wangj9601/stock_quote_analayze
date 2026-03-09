# AKShare HistoricalQuoteCollector 历史数据采集流程图

## 概述

AKShare HistoricalQuoteCollector 是一个专门用于采集股票历史行情数据的采集器，它继承自 AKShareCollector 基类，提供了完整的历史数据采集、处理和存储功能。

---

## 流程图

### 核心流程图（简化版）

```mermaid
flowchart TD
    A[开始采集] --> B[初始化采集器]
    B --> C[验证日期格式]
    C --> D[获取股票列表<br/>ak.stock_zh_a_spot_em]
    D --> E[遍历每只股票]
    E --> F[获取历史数据<br/>ak.stock_zh_a_hist]
    F --> G{数据获取成功?}
    G -->|否| H[记录错误<br/>继续下一只]
    G -->|是| I[数据清洗转换]
    I --> J[保存到数据库<br/>INSERT OR REPLACE]
    J --> K{保存成功?}
    K -->|否| L[记录错误<br/>继续下一只]
    K -->|是| M[成功计数+1]
    M --> N{处理完所有股票?}
    N -->|否| E
    N -->|是| O[输出统计结果]
    L --> N
    H --> N
    O --> P[结束]
```

### 完整流程图（详细版）

```mermaid
flowchart TD
    A[开始历史数据采集] --> B[初始化 HistoricalQuoteCollector]
    B --> C[设置信号处理器<br/>SIGINT/SIGTERM]
    C --> D[验证日期格式<br/>YYYYMMDD]
    D --> E{日期格式正确?}
    E -->|否| F[记录错误日志<br/>返回 0,0]
    E -->|是| G[初始化数据库表结构<br/>CREATE TABLE historical_quotes]
    G --> H[获取股票列表<br/>ak.stock_zh_a_spot_em]
    H --> I[统计总股票数量]
    I --> J[初始化计数器<br/>success_count=0<br/>error_count=0<br/>connection_error_count=0]
    J --> K[开始遍历股票列表]
    K --> L{检查中断信号<br/>should_stop?}
    L -->|是| M[记录中断日志<br/>安全退出]
    L -->|否| N[提取股票信息<br/>code, name, market]
    N --> O[调用 _fetch_stock_data<br/>获取单只股票历史数据]
    O --> P{网络请求成功?}
    P -->|否| Q[connection_error_count++]
    Q --> R{连接错误次数<br/>>= max_connection_errors?}
    R -->|是| S[记录错误日志<br/>退出程序]
    R -->|否| T[等待5秒<br/>继续下一只股票]
    P -->|是| U{数据为空?}
    U -->|是| V[记录警告日志<br/>继续下一只股票]
    U -->|否| W[提取日线数据]
    W --> X[数据清洗转换<br/>_safe_value处理]
    X --> Y[执行数据库插入<br/>INSERT OR REPLACE]
    Y --> Z{数据库操作成功?}
    Z -->|否| AA[error_count++<br/>记录错误日志]
    Z -->|是| BB[success_count++<br/>connection_error_count=0]
    BB --> CC{成功数量<br/>% 100 == 0?}
    CC -->|是| DD[记录进度日志<br/>已处理 X/Y 只股票]
    CC -->|否| EE[继续下一只股票]
    AA --> EE
    T --> EE
    V --> EE
    DD --> EE
    EE --> K
    M --> FF[关闭数据库连接]
    S --> FF
    FF --> GG[记录最终统计<br/>成功: X, 失败: Y]
    GG --> HH[结束]
    F --> HH
```

### 数据流向图

```mermaid
flowchart LR
    A[AKShare API] --> B[HistoricalQuoteCollector]
    B --> C[数据清洗<br/>_safe_value]
    C --> D[数据验证]
    D --> E[SQLite数据库<br/>historical_quotes表]
    
    F[配置参数] --> B
    G[股票列表] --> B
    H[日期参数] --> B
    
    B --> I[日志记录]
    B --> J[错误处理]
    B --> K[进度监控]
```

### 类继承关系

```mermaid
classDiagram
    class AKShareCollector {
        +config: Dict
        +logger: Logger
        +_retry_on_failure()
        +get_stock_list()
        +get_historical_quotes()
    }
    
    class HistoricalQuoteCollector {
        +db_file: Path
        +should_stop: bool
        +_init_db()
        +_safe_value()
        +_fetch_stock_data()
        +collect_quotes()
    }
    
    AKShareCollector <|-- HistoricalQuoteCollector
```

### 关键方法流程（时序图）

```mermaid
sequenceDiagram
    participant Main as 主程序
    participant Collector as HistoricalQuoteCollector
    participant AKShare as AKShare API
    participant DB as 数据库
    
    Main->>Collector: collect_quotes(date_str)
    Collector->>Collector: 验证日期格式
    Collector->>AKShare: stock_zh_a_spot_em()
    AKShare-->>Collector: 股票列表
    loop 每只股票
        Collector->>AKShare: stock_zh_a_hist(code, date)
        AKShare-->>Collector: 历史数据
        Collector->>Collector: _safe_value() 数据清洗
        Collector->>DB: INSERT OR REPLACE
        DB-->>Collector: 操作结果
    end
    Collector-->>Main: (success_count, error_count)
```

### 错误处理流程

```mermaid
flowchart TD
    A[开始处理] --> B{网络请求}
    B -->|成功| C[处理数据]
    B -->|失败| D[重试机制]
    D --> E{重试次数<br/>>= max_retries?}
    E -->|否| F[等待retry_delay秒]
    F --> B
    E -->|是| G[记录错误<br/>继续下一只]
    
    C --> H{数据验证}
    H -->|通过| I[保存数据]
    H -->|失败| J[记录警告<br/>继续下一只]
    
    I --> K{数据库操作}
    K -->|成功| L[成功计数+1]
    K -->|失败| M[记录错误<br/>继续下一只]
    
    L --> N[继续下一只股票]
    G --> N
    J --> N
    M --> N
```

---

## 详细流程说明

### 1. 初始化阶段

- **HistoricalQuoteCollector 初始化**: 继承 AKShareCollector 基类，加载配置参数
- **信号处理器设置**: 监听 SIGINT 和 SIGTERM 信号，支持安全中断
- **数据库初始化**: 创建 historical_quotes 表结构

### 2. 数据获取阶段

- **日期验证**: 验证输入日期格式为 YYYYMMDD
- **股票列表获取**: 通过 `ak.stock_zh_a_spot_em()` 获取所有 A 股列表
- **数据采集**: 对每只股票调用 `ak.stock_zh_a_hist()` 获取历史数据

### 3. 数据处理阶段

- **数据清洗**: 通过 `_safe_value()` 方法安全转换数值
- **数据验证**: 检查数据完整性，过滤空数据
- **数据转换**: 将 akshare 返回的中文字段名转换为数据库字段

### 4. 数据存储阶段

- **数据库操作**: 使用 INSERT OR REPLACE 语句避免重复数据
- **事务管理**: 每只股票单独提交，确保数据一致性
- **错误处理**: 记录详细的错误信息和统计

### 5. 监控和日志

- **进度监控**: 每处理 100 只股票记录一次进度
- **错误统计**: 分别统计成功和失败的数量
- **连接错误处理**: 连续连接错误超过阈值时安全退出

---

## 关键特性

### 1. 容错机制

- **重试机制**: 继承基类的 `_retry_on_failure` 方法
- **连接错误处理**: 连续错误超过阈值时退出
- **信号处理**: 支持 Ctrl+C 安全中断

### 2. 数据完整性

- **数据验证**: 验证日期格式和数据有效性
- **重复处理**: 使用 INSERT OR REPLACE 避免重复
- **事务安全**: 单只股票事务提交

### 3. 性能优化

- **批量处理**: 逐只股票处理，避免内存溢出
- **进度监控**: 定期记录处理进度
- **资源管理**: 及时关闭数据库连接

---

## 配置参数

```python
DATA_COLLECTORS = {
    'akshare': {
        'max_retries': 3,              # 最大重试次数
        'retry_delay': 5,              # 重试延迟（秒）
        'timeout': 30,                 # 请求超时时间（秒）
        'log_dir': 'logs',             # 日志目录
        'db_file': 'stock_analysis.db', # 数据库文件路径
        'max_connection_errors': 10    # 最大连接错误次数
    }
}
```

配置与调度关系：

```mermaid
flowchart TD
    A[配置文件<br/>config.py] --> B[DATA_COLLECTORS]
    B --> C[akshare配置]
    C --> D[max_retries: 3]
    C --> E[retry_delay: 5]
    C --> F[timeout: 30]
    C --> G[max_connection_errors: 10]
    
    H[调度器<br/>main.py] --> I[定时任务]
    I --> J[每日15:30执行]
    J --> K[collect_tushare_historical]
    K --> L[HistoricalQuoteCollector.collect_quotes]
```

---

## 数据库表结构

```sql
CREATE TABLE historical_quotes (
    code TEXT,                    -- 股票代码
    name TEXT,                    -- 股票名称
    market TEXT,                  -- 市场类型
    date TEXT,                    -- 交易日期
    open REAL,                    -- 开盘价
    high REAL,                    -- 最高价
    low REAL,                     -- 最低价
    close REAL,                   -- 收盘价
    volume REAL,                  -- 成交量
    amount REAL,                  -- 成交额
    change_percent REAL,          -- 涨跌幅
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 更新时间
    PRIMARY KEY (code, date)      -- 复合主键
);
```

---

## 使用示例

```python
# 创建采集器实例
collector = HistoricalQuoteCollector()

# 采集指定日期的历史数据
success_count, error_count = collector.collect_quotes('20241201')

# 输出结果
print(f"采集完成: 成功 {success_count} 只, 失败 {error_count} 只")
```

---

## 调度集成

该采集器已集成到主调度系统中，支持定时执行：

```python
# 在 main.py 中的调度配置
scheduler.add_job(
    collect_tushare_historical,
    'cron',
    hour=15,
    minute=30,
    id='historical_quotes_collection'
)
```
