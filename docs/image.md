# 系统组件图

```mermaid
graph TD
  A[前端 Frontend]
  B[后端API Backend API]
  C[核心引擎 Backend Core]
  D[数据库 Database]
  E[管理后台 Admin]
  F[第三方数据源 Akshare/Tushare]

  A -- 调用RESTful API --> B
  E -- 管理API/配置/监控 --> B
  B -- 业务逻辑/数据服务 --> C
  C -- 采集/分析/预测/建议 --> D
  C -- 定时采集/数据处理 --> F
  C -- 读写 --> D
  B -- 读写 --> D
  E -- 读写/管理 --> D
  A -- 访问静态资源 --> E

  subgraph 用户界面
    A
    E
  end
  subgraph 服务层
    B
    C
  end
  D
  F

  
```


# 数据流管道图

```mermaid
flowchart TD
  A[第三方数据源<br/>Akshare/Tushare] -->|定时/手动采集| B[数据采集模块<br/>Backend Core]
  B -->|数据清洗/标准化| C[数据处理模块<br/>Backend Core]
  C -->|批量入库| D[数据库]
  D -->|查询/分析| E[分析与预测模块<br/>Backend Core]
  E -->|分析结果/建议| D
  D -->|API查询| F[后端API服务]
  F -->|RESTful API| G[前端/管理后台]

  subgraph 数据采集与处理
    B
    C
  end
  subgraph 数据消费
    F
    G
  end
  D
  E
  A
  
```

# 顶层架构图

```mermaid

graph LR
  subgraph 用户层
    A1[普通用户]
    A2[管理员]
  end

  subgraph 表现层
    B1[前端 Web]
    B2[管理后台 Web]
  end

  subgraph 服务层
    C1[后端API服务<br/>FastAPI]
  end

  subgraph 核心层
    D1[核心引擎 Backend Core]
    D2[分析与模型]
    D3[数据采集调度]
  end

  subgraph 数据层
    E1[数据库 PostgreSQL]
    E2[日志/配置/文件]
  end

  subgraph 外部资源
    F1[第三方数据源<br/>Akshare/Tushare]
  end

  A1 -- 浏览器访问 --> B1
  A2 -- 浏览器访问 --> B2
  B1 -- RESTful API --> C1
  B2 -- RESTful API --> C1
  C1 -- 业务调用/数据请求 --> D1
  D1 -- 调用分析/模型 --> D2
  D1 -- 调用采集调度 --> D3
  D3 -- 定时采集 --> F1
  D1 -- 读写 --> E1
  D2 -- 读写 --> E1
  C1 -- 读写 --> E1
  D1 -- 日志/配置 --> E2
  C1 -- 日志/配置 --> E2
  
```


```mermaid

flowchart TB
 subgraph s1["用户层"]
        A1["普通用户"]
        A2["管理员"]
  end
 subgraph s2["表现层"]
        B1["前端 Web"]
        B2["管理后台 Web"]
  end
 subgraph s3["服务层"]
        C1["后端API服务<br>FastAPI"]
  end
 subgraph s4["核心层"]
        D1["核心引擎 Backend Core"]
        D2["分析与模型"]
        D3["数据采集调度"]
  end
 subgraph s5["数据层"]
        E1["数据库 PostgreSQL"]
        E2["日志/配置/文件"]
  end
 subgraph s6["外部资源"]
        F1["第三方数据源<br>Akshare/Tushare"]
  end
    A1 -- 浏览器访问 --> B1
    A2 -- 浏览器访问 --> B2
    B1 -- RESTful API --> C1
    B2 -- RESTful API --> C1
    C1 -- 业务调用/数据请求 --> D1
    D1 -- 调用分析/模型 --> D2
    D1 -- 调用采集调度 --> D3
    D3 -- 定时采集 --> F1
    D1 -- 读写 --> E1
    D2 -- 读写 --> E1
    C1 -- 读写 --> E1
    D1 -- 日志/配置 --> E2
    C1 -- 日志/配置 --> E2

    ```


# AKShare采集器 类层次结构图

```mermaid

---
config:
  look: neo
  layout: elk
---
classDiagram
    class AKShareCollector
    AKShareCollector <|-- AkshareRealtimeQuoteCollector
    AKShareCollector <|-- HistoricalQuoteCollector
    AKShareCollector <|-- IndexQuoteCollector
    AKShareCollector <|-- AkshareStockNoticeReportCollector

    class RealtimeStockIndustryBoardCollector
    class RealtimeIndexSpotAkCollector

```


# AKShare采集器 数据流架构图

```mermaid

flowchart TD
 subgraph subGraph0["AKShare API"]
        A1["stock_zh_a_spot_em"]
        A2["stock_board_industry_name_em"]
        A3["stock_notice_report"]
        A4["stock_zh_index_spot_em"]
        A5["stock_zh_a_hist"]
  end
 subgraph subGraph1["Collector Classes"]
        B1["AkshareRealtimeQuoteCollector"]
        B2["RealtimeStockIndustryBoardCollector"]
        B3["AkshareStockNoticeReportCollector"]
        B4["RealtimeIndexSpotAkCollector"]
        B5["HistoricalQuoteCollector"]
  end
 subgraph subGraph2["Database Tables"]
        C1["stock_realtime_quote"]
        C2["stock_basic_info"]
        C3["industry_board_realtime_quotes"]
        C4["stock_notice_report"]
        C5["realtime_collect_operation_logs"]
        C6["index_realtime_quotes"]
        C7["historical_quotes"]
  end
    A1 --> B1
    B1 --> C1 & C2
    A2 --> B2
    B2 --> C3
    A3 --> B3
    B3 --> C4 & C5
    A4 --> B4
    B4 --> C6 & C5
    A5 --> B5
    B5 --> C7

```