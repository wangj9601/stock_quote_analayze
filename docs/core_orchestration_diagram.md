# 核心数据采集编排组件图

## 简化架构图

```mermaid

flowchart LR
    A["main.py 入口点"] --> B["BlockingScheduler"]
    B --> C1["collect_akshare_realtime"] & C2["collect_tushare_historical"] & C3["collect_akshare_index_realtime"] & C4["collect_akshare_industry_board_realtime"] & C5["collect_akshare_stock_notices"] & C6["run_watchlist_history_collection"]
    C1 --> D1["ak_collector<br>AkshareRealtimeQuoteCollector"]
    C2 --> D2["tushare_hist_collector<br>HistoricalQuoteCollector"]
    C3 --> D3["index_collector<br>RealtimeIndexSpotAkCollector"]
    C4 --> D4["industry_board_collector<br>RealtimeStockIndustryBoardCollector"]
    C5 --> D5["notice_collector<br>AkshareStockNoticeReportCollector"]
    C6 --> D6["watchlist_collector<br>WatchlistHistoryCollector"]
    E["DATA_COLLECTORS<br>from config.py"] --> D1 & D2 & D3 & D4 & D5 & D6
    D1 --> F1["AKShare API"] & G["PostgreSQL Database"]
    D2 --> F2["Tushare API"] & G
    D3 --> F1 & G
    D4 --> F1 & G
    D5 --> F1 & G
    D6 --> F3["多数据源"] & G
     A:::entry
     B:::scheduler
     C1:::wrapper
     C2:::wrapper
     C3:::wrapper
     C4:::wrapper
     C5:::wrapper
     C6:::wrapper
     D1:::collector
     D2:::collector
     D3:::collector
     D4:::collector
     D5:::collector
     D6:::collector
     E:::config
     F1:::api
     G:::storage
     F2:::api
     F3:::api
    classDef entry fill:#e3f2fd,stroke:#1565c0,stroke-width:3px
    classDef scheduler fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef wrapper fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px
    classDef collector fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef config fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef api fill:#e1f5fe,stroke:#0277bd,stroke-width:2px
    classDef storage fill:#f1f8e9,stroke:#33691e,stroke-width:2px

```

## 核心编排逻辑

### 1. 系统启动流程
```
main.py 启动
    ↓
初始化 BlockingScheduler
    ↓
配置定时任务
    ↓
启动调度器服务
    ↓
等待定时触发
```

### 2. 定时任务配置

| 任务名称 | 调度策略 | 包装函数 | 采集器实例 |
|---------|---------|---------|-----------|
| AKShare 实时行情 | 交易时间每15分钟 | `collect_akshare_realtime()` | `ak_collector` |
| Tushare 历史数据 | 每日10:25 | `collect_tushare_historical()` | `tushare_hist_collector` |
| 指数实时行情 | 交易时间每20分钟 | `collect_akshare_index_realtime()` | `index_collector` |
| 行业板块行情 | 交易时间每30分钟 | `collect_akshare_industry_board_realtime()` | `industry_board_collector` |
| 公告数据 | 每60分钟 | `collect_akshare_stock_notices()` | `notice_collector` |
| 自选股历史数据 | 每日13:56 | `run_watchlist_history_collection()` | `watchlist_collector` |

### 3. 采集器实例初始化

```python
# 初始化采集器实例
ak_collector = AkshareRealtimeQuoteCollector(DATA_COLLECTORS.get('akshare', {}))
tushare_hist_collector = HistoricalQuoteCollector(DATA_COLLECTORS.get('tushare', {}))
tushare_realtime_collector = RealtimeQuoteCollector(DATA_COLLECTORS.get('tushare', {}))
index_collector = RealtimeIndexSpotAkCollector()
industry_board_collector = RealtimeStockIndustryBoardCollector()
notice_collector = AkshareStockNoticeReportCollector(DATA_COLLECTORS.get('akshare', {}))
```

### 4. 配置管理

```python
DATA_COLLECTORS = {
    'tushare': {
        'max_retries': 3,
        'retry_delay': 5,
        'timeout': 30,
        'token': 'tushare_token'
    },
    'akshare': {
        'max_retries': 3,
        'retry_delay': 5,
        'timeout': 30
    }
}
```

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