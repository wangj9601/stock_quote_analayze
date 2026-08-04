# AKShare 使用与连接问题指南

本文档整合 AKShare 连接问题解决方案、增强采集器使用、历史数据采集程序使用说明及配置与维护要点。

---

## 一、连接问题与原因

调用 AKShare 接口（如 `stock_zh_a_spot_em`）失败时，常见原因包括：

1. **SSL 连接错误**：`[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol`
2. **连接被重置**：`Remote end closed connection without response`
3. **IP 封禁或频率限制**：东方财富等数据源对频繁请求或部分网络环境有限制

---

## 二、解决方案概览

### 2.1 增强的 AKShare 采集器（推荐在可访问环境下使用）

通过增强采集器改善连接稳定性与容错：

- **SSL 优化**：自定义 SSL 上下文、可选关闭 SSL 验证、连接重试
- **代理支持**：代理池轮换，支持 HTTP/HTTPS 代理
- **User-Agent 轮换**：多组浏览器 UA，降低被识别为脚本的概率
- **随机延迟**：如 1～3 秒随机延迟，降低请求频率
- **多数据源回退**：主源失败时切换备用接口，如  
  `stock_zh_a_spot_em` → `stock_sh_a_spot_em` / `stock_sz_a_spot_em` / `stock_bj_a_spot_em`

**文件位置**：

- `backend_core/data_collectors/akshare/enhanced_base.py` — 增强基础采集器
- `backend_core/data_collectors/akshare/enhanced_realtime.py` — 增强实时行情采集器

**使用示例**：

```python
from backend_core.data_collectors.akshare.enhanced_realtime import EnhancedRealtimeQuoteCollector

collector = EnhancedRealtimeQuoteCollector()
success = collector.collect_quotes()
```

### 2.2 配置代理

若需通过代理访问数据源，可在配置中增加代理池，例如：

```python
# backend_core/config/config.py 或等价配置
'akshare': {
    'proxy_pool': [
        {'http': 'http://proxy1:port', 'https': 'https://proxy1:port'},
        {'http': 'http://proxy2:port', 'https': 'https://proxy2:port'},
    ],
    # 其他配置...
}
```

### 2.3 切换到 Tushare 或其他数据源

当 AKShare 在目标网络下持续不可用时，可考虑：

- **Tushare**：需 Token，免费额度通常够用，稳定性较好。
- **新浪/腾讯/东方财富等 API**：需自行对接与解析，部分免费。

---

## 三、配置说明

### 3.1 增强相关配置示例

```python
'akshare': {
    'max_retries': 3,
    'retry_delay': 5,
    'timeout': 30,
    'log_dir': str(ROOT_DIR / 'backend_core' / 'logs'),
    'db_file': str(DB_DIR / 'stock_analysis.db'),
    'max_connection_errors': 10,
    # 增强配置
    'proxy_pool': [],
    'random_delay_range': (1, 3),
    'ssl_verify': False,
    'use_fallback_sources': True,
}
```

### 3.2 历史采集器相关

- 数据库：使用 `backend_core.database.db.SessionLocal`，需保证数据库配置正确。
- 重试：最大重试 3 次，递增延迟（如 2s、4s、6s）；请求间隔可加 0.5～1.5 秒随机延迟。

---

## 四、历史数据采集程序使用说明

### 4.1 程序概述

`historical_collector.py`（或项目中等价的历史采集脚本）基于 akshare 采集 A 股历史行情，支持按日期范围批量采集。

- **数据接口**：akshare `stock_zh_a_hist`（前复权等，以实际为准）
- **股票列表**：可从 `stock_basic_info` 等表获取
- **功能**：指定日期范围、自动跳过已存在数据、重试与日志、结果统计

### 4.2 命令行使用

```bash
# 按日期范围采集所有股票
python backend_core/data_collectors/akshare/historical_collector.py 2025-08-01 2025-09-03

# 指定股票
python backend_core/data_collectors/akshare/historical_collector.py 2025-08-01 2025-09-03 --stocks 000001 000002 000858

# 测试模式（仅前若干只）
python backend_core/data_collectors/akshare/historical_collector.py 2025-08-01 2025-09-03 --test
```

参数含义：`start_date`、`end_date`（YYYY-MM-DD）；`--stocks` 可选股票列表；`--test` 测试模式。

### 4.3 程序化使用

```python
from backend_core.data_collectors.akshare.historical_collector import AkshareHistoricalCollector

collector = AkshareHistoricalCollector()

# 全部股票
result = collector.collect_historical_data("2025-08-01", "2025-09-03")

# 指定股票
result = collector.collect_historical_data("2025-08-01", "2025-09-03", ["000001", "000002"])

# result 含 total, success, failed, collected, skipped 等
```

### 4.4 数据字段与输出

- 常见字段：股票代码、名称、市场、开高低收、成交量、成交额、涨跌幅等；采集来源、采集时间（以实际表结构为准）。
- 日志：控制台与日志文件（如 `akshare_historical_collect.log`）；结果可写入 `historical_collect_operation_logs` 等表。

### 4.5 注意事项

- **去重**：已存在的交易日数据应跳过，避免重复插入。
- **频率**：适当随机延迟，建议大批量在非交易时间执行。
- **单只失败**：单只股票失败不影响其他股票，便于重试与排查。

---

## 五、测试与验证

### 5.1 增强采集器与连接方案

```bash
python test/test_enhanced_akshare_simple.py
python test/test_enhanced_akshare_collector.py
# 若有综合测试
python test/test_akshare_solutions.py
```

### 5.2 历史采集器

```bash
python test/test_akshare_historical_collector.py
```

可覆盖：数据库连接、akshare 可用性、股票列表、单只/批量采集等。

---

## 六、推荐使用策略

### 6.1 按环境选择

- **AKShare 可用**：优先使用增强采集器（含代理/多数据源回退），并配合随机延迟与重试。
- **AKShare 不可用**：短期可切换 Tushare 或新浪等 API；中期可配置代理后再用增强采集器；长期可做多数据源集成与自动故障转移。

### 6.2 性能与稳定性

- 历史大批量采集：分批执行、控制并发与请求间隔；必要时使用测试模式验证。
- 监控日志（如 `backend_core/logs/`）、连接错误与重试次数，定期跑测试脚本检查数据源可用性。

---

## 七、监控与维护

1. **日志**：查看 `backend_core/logs/` 下相关日志，关注连接错误与重试。
2. **定期测试**：用上述测试脚本定期验证数据源与采集路径。
3. **代理与配置**：使用代理时及时更新代理池；按需调整 `timeout`、`max_retries`、`random_delay_range` 等。
4. **数据源健康**：若有多个数据源，可做健康检查与自动切换。

---

## 八、常见问题

| 现象 | 建议 |
|------|------|
| akshare 连接失败 | 检查网络、代理、SSL 设置；尝试 `pip install --upgrade akshare`；使用增强采集器与多数据源回退 |
| 数据库连接失败 | 检查数据库配置、服务与权限 |
| 历史采集失败 | 检查股票代码与日期范围；查看详细日志；单只失败可重试 |
| 请求被限或封禁 | 增加延迟、配置代理、轮换 UA；或切换 Tushare/其他数据源 |
| 内存不足 | 减小每批数量、分批采集、控制并发 |

---

## 九、相关文件索引

| 说明 | 路径（示例） |
|------|----------------|
| 增强基础采集器 | backend_core/data_collectors/akshare/enhanced_base.py |
| 增强实时采集器 | backend_core/data_collectors/akshare/enhanced_realtime.py |
| 历史采集程序 | backend_core/data_collectors/akshare/historical_collector.py |
| 采集配置 | backend_core/config/config.py |
| 测试脚本 | test/test_enhanced_akshare_*.py, test/test_akshare_historical_collector.py |

---

本文档由以下原文档整合而成：AKShare 连接问题解决方案、Akshare 历史数据采集程序使用说明、AKShare 连接问题解决方案使用指南。
