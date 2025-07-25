# 核心数据采集编排组件图

## 简化架构图

```mermaid
graph TB
    %% 主入口
    A[main.py 入口点] --> B[BlockingScheduler]
    
    %% 调度器触发包装函数
    B --> C1[collect_akshare_realtime]
    B --> C2[collect_tushare_historical]
    B --> C3[collect_akshare_index_realtime]
    B --> C4[collect_akshare_industry_board_realtime]
    B --> C5[collect_akshare_stock_notices]
    B --> C6[run_watchlist_history_collection]
    
    %% 包装函数调用采集器
    C1 --> D1[ak_collector<br/>AkshareRealtimeQuoteCollector]
    C2 --> D2[tushare_hist_collector<br/>HistoricalQuoteCollector]
    C3 --> D3[index_collector<br/>RealtimeIndexSpotAkCollector]
    C4 --> D4[industry_board_collector<br/>RealtimeStockIndustryBoardCollector]
    C5 --> D5[notice_collector<br/>AkshareStockNoticeReportCollector]
    C6 --> D6[watchlist_collector<br/>WatchlistHistoryCollector]
    
    %% 配置影响所有采集器
    E[DATA_COLLECTORS<br/>from config.py] --> D1
    E --> D2
    E --> D3
    E --> D4
    E --> D5
    E --> D6
    
    %% 数据源
    D1 --> F1[AKShare API]
    D2 --> F2[Tushare API]
    D3 --> F1
    D4 --> F1
    D5 --> F1
    D6 --> F3[多数据源]
    
    %% 数据存储
    D1 --> G[SQLite Database]
    D2 --> G
    D3 --> G
    D4 --> G
    D5 --> G
    D6 --> G
    
    %% 样式定义
    classDef entry fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef scheduler fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef wrapper fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef collector fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef config fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef api fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    classDef storage fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    
    class A entry
    class B scheduler
    class C1,C2,C3,C4,C5,C6 wrapper
    class D1,D2,D3,D4,D5,D6 collector
    class E config
    class F1,F2,F3 api
    class G storage
```

## 核心编排逻辑

### 1. 系统启动流程

```mermaid
flowchart TD
    A[main.py 启动] --> B[初始化 BlockingScheduler]
    B --> C[配置定时任务]
    C --> D[启动调度器服务]
    D --> E[等待定时触发]
    
    classDef start fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    classDef process fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef wait fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    
    class A start
    class B,C,D process
    class E wait
```

### 2. 定时任务调度逻辑

```mermaid
flowchart TD
    A[BlockingScheduler] --> B{定时触发检查}
    
    B --> C1[交易时间检查]
    B --> C2[每日时间检查]
    B --> C3[间隔时间检查]
    
    C1 --> D1[AKShare 实时行情<br/>交易时间每15分钟]
    C1 --> D2[指数实时行情<br/>交易时间每20分钟]
    C1 --> D3[行业板块行情<br/>交易时间每30分钟]
    
    C2 --> D4[Tushare 历史数据<br/>每日10:25]
    C2 --> D5[自选股历史数据<br/>每日13:56]
    
    C3 --> D6[公告数据<br/>每60分钟]
    
    D1 --> E1[collect_akshare_realtime]
    D2 --> E2[collect_akshare_index_realtime]
    D3 --> E3[collect_akshare_industry_board_realtime]
    D4 --> E4[collect_tushare_historical]
    D5 --> E5[run_watchlist_history_collection]
    D6 --> E6[collect_akshare_stock_notices]
    
    classDef scheduler fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef decision fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef task fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef wrapper fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    
    class A scheduler
    class B,C1,C2,C3 decision
    class D1,D2,D3,D4,D5,D6 task
    class E1,E2,E3,E4,E5,E6 wrapper
```

### 3. 采集器实例初始化流程

```mermaid
flowchart LR
    A[读取配置] --> B[DATA_COLLECTORS]
    B --> C1[akshare配置]
    B --> C2[tushare配置]
    
    C1 --> D1[ak_collector<br/>AkshareRealtimeQuoteCollector]
    C1 --> D2[index_collector<br/>RealtimeIndexSpotAkCollector]
    C1 --> D3[industry_board_collector<br/>RealtimeStockIndustryBoardCollector]
    C1 --> D4[notice_collector<br/>AkshareStockNoticeReportCollector]
    
    C2 --> D5[tushare_hist_collector<br/>HistoricalQuoteCollector]
    C2 --> D6[tushare_realtime_collector<br/>RealtimeQuoteCollector]
    
    D1 --> E[采集器实例池]
    D2 --> E
    D3 --> E
    D4 --> E
    D5 --> E
    D6 --> E
    
    classDef config fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef source fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef collector fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef pool fill:#fff3e0,stroke:#f57c00,stroke-width:3px
    
    class A,B config
    class C1,C2 source
    class D1,D2,D3,D4,D5,D6 collector
    class E pool
```

### 4. 数据采集执行流程

```mermaid
flowchart TD
    A[包装函数被触发] --> B[获取采集器实例]
    B --> C[应用配置参数]
    C --> D[连接数据源API]
    D --> E{API调用成功?}
    
    E -->|是| F[数据获取]
    E -->|否| G{重试次数 < 3?}
    
    G -->|是| H[等待5秒]
    H --> I[重试API调用]
    I --> E
    
    G -->|否| J[记录错误日志]
    J --> K[跳过本次采集]
    
    F --> L[数据处理和清洗]
    L --> M[数据存储到PostgreSQL]
    M --> N[记录成功日志]
    N --> O[采集完成]
    
    K --> O
    
    classDef trigger fill:#e8f5e8,stroke:#2e7d32,stroke-width:3px
    classDef process fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef decision fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef success fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    
    class A trigger
    class B,C,D,F,L,M,N process
    class E,G decision
    class H,I,J,K error
    class O success
```

### 5. 配置管理架构

```mermaid
graph TB
    A[config.py] --> B[DATA_COLLECTORS]
    
    B --> C1[tushare配置组]
    B --> C2[akshare配置组]
    
    C1 --> D1[max_retries: 3]
    C1 --> D2[retry_delay: 5]
    C1 --> D3[timeout: 30]
    C1 --> D4[token: tushare_token]
    C1 --> D5[log_dir: logs]
    C1 --> D6[db_file: stock_analysis.db]
    
    C2 --> E1[max_retries: 3]
    C2 --> E2[retry_delay: 5]
    C2 --> E3[timeout: 30]
    C2 --> E4[log_dir: logs]
    C2 --> E5[db_file: stock_analysis.db]
    
    D1 --> F[采集器实例配置]
    D2 --> F
    D3 --> F
    D4 --> F
    D5 --> F
    D6 --> F
    E1 --> F
    E2 --> F
    E3 --> F
    E4 --> F
    E5 --> F
    
    classDef config fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef group fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef param fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef target fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    
    class A,B config
    class C1,C2 group
    class D1,D2,D3,D4,D5,D6,E1,E2,E3,E4,E5 param
    class F target
```

## 定时任务配置

| 任务名称 | 调度策略 | 包装函数 | 采集器实例 |
|---------|---------|---------|-----------|
| AKShare 实时行情 | 交易时间每15分钟 | `collect_akshare_realtime()` | `ak_collector` |
| Tushare 历史数据 | 每日10:25 | `collect_tushare_historical()` | `tushare_hist_collector` |
| 指数实时行情 | 交易时间每20分钟 | `collect_akshare_index_realtime()` | `index_collector` |
| 行业板块行情 | 交易时间每30分钟 | `collect_akshare_industry_board_realtime()` | `industry_board_collector` |
| 公告数据 | 每60分钟 | `collect_akshare_stock_notices()` | `notice_collector` |
| 自选股历史数据 | 每日13:56 | `run_watchlist_history_collection()` | `watchlist_collector` |

## 数据流图

```mermaid
flowchart LR
    A[定时触发] --> B[包装函数]
    B --> C[采集器实例]
    C --> D[数据源API]
    D --> E[数据处理]
    E --> F[数据库存储]
    E --> G[日志记录]
    
    H[配置管理] --> C
    
    classDef trigger fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef wrapper fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef collector fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef api fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef process fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef storage fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef config fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    
    class A trigger
    class B wrapper
    class C collector
    class D api
    class E process
    class F,G storage
    class H config
```

## 关键组件说明

### 编排层组件
- **main.py**: 系统入口点，负责初始化和启动
- **BlockingScheduler**: 核心调度器，管理所有定时任务

### 包装函数层
- **collect_akshare_realtime()**: AKShare实时行情采集
- **collect_tushare_historical()**: Tushare历史数据采集
- **collect_akshare_index_realtime()**: 指数实时行情采集
- **collect_akshare_industry_board_realtime()**: 行业板块行情采集
- **collect_akshare_stock_notices()**: 公告数据采集
- **run_watchlist_history_collection()**: 自选股历史数据采集

### 采集器实例层
- **ak_collector**: AKShare实时行情采集器
- **tushare_hist_collector**: Tushare历史数据采集器
- **index_collector**: 指数实时行情采集器
- **industry_board_collector**: 行业板块行情采集器
- **notice_collector**: 公告数据采集器
- **watchlist_collector**: 自选股历史数据采集器

### 配置层
- **DATA_COLLECTORS**: 统一配置管理，影响所有采集器实例

## 扩展性设计

### 新增采集任务流程
1. 创建新的采集器类
2. 在main.py中初始化采集器实例
3. 创建对应的包装函数
4. 在调度器中添加定时任务配置

### 配置管理优势
- 统一的配置接口
- 支持不同数据源的独立配置
- 灵活的调度策略配置
- 易于维护和扩展 