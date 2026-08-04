# ETF历史迁移脚本使用说明

脚本路径：`manual_scripts/etf_historical_migration.py`

## 0. 当前实现的整体处理流程（总览）

1. 参数解析与日期校验（`parse_args` + `validate_dates`）
2. 初始化迁移器（`EtfHistoricalMigration`），建立数据库会话并初始化统计器
3. 加载 ETF 列表（`_load_etf_list`）
   - 传了 `--codes`：按指定代码处理
   - 未传 `--codes`：从 `fund_basic_info` 读取 `collect_enabled=true` 的全部 ETF
4. 主循环按 ETF 代码逐只执行（`run` -> `_migrate_one`）
5. 单只 ETF 内执行三数据源“重试 + 降级”拉取
   - `eastmoney` -> `sina` -> `ths`
6. 对拉取结果按日期过滤后 UPSERT 到 `fund_historical_quotes`（`_upsert_rows`）
7. 可选重算指标（`--recalc-indicators`）
8. 输出进度、汇总统计和失败明细，返回退出码

## 1. 功能概述

- 从多数据源迁移 ETF 历史行情到 `fund_historical_quotes`。
- 数据源自动降级顺序：东方财富 -> 新浪 -> 同花顺（同花顺仅做今日单日快照兜底）。
- 使用 `(code, date)` 主键幂等写入（`ON CONFLICT DO UPDATE`）。
- 默认按“本次时间段内”做补缺采集：整段扫描，只写入缺失日期（支持中断后重跑续传，不重复写入已存在日期）。

## 2. 参数说明

- `--start-date`：开始日期，格式 `YYYY-MM-DD`（必填）
- `--end-date`：结束日期，格式 `YYYY-MM-DD`（必填）
- `--codes`：ETF 代码列表（可选，不传则读取 `fund_basic_info` 启用列表）
- `--batch-size`：每批处理 ETF 数量，默认 `20`
- `--sleep-ms`：每批处理后的休眠毫秒数，默认 `500`
- `--skip-existing`：仅补缺，不更新已存在记录（默认模式下已是该行为；该参数主要用于显式表达）
- `--recalc-indicators`：迁移后重算 ETF 指标
- `--max-retries`：单数据源最大重试次数，默认 `3`
- `--full-refresh`：强制全量回刷（忽略默认增量起点，按 `--start-date ~ --end-date` 全量处理）
- `--log-effective-start`：打印每只 ETF 在本次区间内的实际增量起点（用于排查断点续跑）

## 3. 常用命令

### 3.1 单只 ETF 小范围回填

```bash
python manual_scripts/etf_historical_migration.py --start-date 2026-04-01 --end-date 2026-04-05 --codes 510300 --batch-size 1 --sleep-ms 0
```

### 3.2 全量启用 ETF 历史回填（默认增量）

```bash
python manual_scripts/etf_historical_migration.py --start-date 2025-01-01 --end-date 2026-04-24
```

### 3.3 仅补缺模式（不覆盖已有数据）

```bash
python manual_scripts/etf_historical_migration.py --start-date 2025-01-01 --end-date 2026-04-20 --skip-existing
```

### 3.4 回填后重算指标

```bash
python manual_scripts/etf_historical_migration.py --start-date 2026-01-01 --end-date 2026-04-20 --codes 510300 159915 --recalc-indicators
```

### 3.5 全量回刷（覆盖历史区间）

```bash
python manual_scripts/etf_historical_migration.py --start-date 2025-01-01 --end-date 2026-04-20 --full-refresh
```

### 3.6 打印每只 ETF 的区间增量起点（调试）

```bash
python manual_scripts/etf_historical_migration.py --start-date 2025-01-01 --end-date 2026-04-20 --codes 159001 510300 --log-effective-start
```

## 4. 输出与退出码

- 输出统计包括：
  - ETF 总数 / 成功数 / 失败数
  - 行级插入 / 更新 / 跳过
  - 数据源命中统计（`eastmoney|sina|ths`）
  - 失败明细（`code + error`）
- 退出码：
  - `0`：全部成功
  - `2`：存在失败
  - `1`：参数校验失败或无可迁移 ETF

## 5. 幂等与补缺行为

- 默认模式：按“本次区间补缺”采集；中断后重跑会跳过已存在日期，只补缺失日期。
- 同一 `(code, date)` 再次写入会更新（幂等覆盖）。
- `--skip-existing` 模式：已存在记录会被跳过，只写入缺失日期。
- `--full-refresh` 模式：按指定日期区间全量处理，适用于口径变更或数据纠偏。

## 6. 详细处理逻辑（按代码维度）

### 6.1 主循环是否按 ETF 代码执行

- 是。`run()` 中固定使用 `for idx, (code, name) in enumerate(etf_list, start=1)` 逐只处理。
- 即使开启 `--full-refresh`，外层循环仍不变，依然是“每次处理一只 ETF”。

### 6.2 单只 ETF 的处理步骤（`_migrate_one`）

1. 计算 `effective_start`（当前实现中，无论是否 `full_refresh`，都返回 `start_date`）
2. 如 `effective_start > end_date`，判定该 ETF 无需处理
3. 依次尝试数据源：
   - `eastmoney`：`ak.fund_etf_hist_em`（支持区间参数）
   - `sina`：`ak.fund_etf_hist_sina`（取全量后再在本地按日期过滤）
   - `ths`：`ak.fund_etf_spot_ths`（仅当区间包含今天时，补“今日单日快照”）
4. 每个数据源走 `_fetch_with_retry`，最多 `--max-retries` 次
5. 三源都无可用数据则记录失败
6. 有数据则执行 `_upsert_rows`
7. 若启用 `--recalc-indicators` 且本次有插入/更新，则触发指标重算

### 6.3 全量与增量在入库层的差异

- 核心开关：`should_skip_existing = skip_existing or (not full_refresh)`
- 默认模式（未开 `--full-refresh`）：
  - `should_skip_existing=True`
  - 先查区间内已有日期集合（`_existing_dates`）
  - 已存在日期直接 `skipped`，只补缺
- 全量模式（开启 `--full-refresh`）：
  - 若未额外传 `--skip-existing`，则 `should_skip_existing=False`
  - 区间内所有有效数据都参与 UPSERT
  - 已有记录会走 `ON CONFLICT DO UPDATE`，形成“全量回刷覆盖”

### 6.4 行级写入与字段处理

- 逐行读取 DataFrame，先做日期合法性和区间过滤
- 关键字段标准化：
  - 数值字段统一 `_to_float`
  - `pre_close` 缺失且 `close/change` 可用时，按 `pre_close = close - change` 回推
- 通过主键 `(code, date)` UPSERT 写入
- 统计分为 `inserted / updated / skipped`
- 单只 ETF 完成后 `commit`；异常则 `rollback` 并记录失败

### 6.5 节流、进度和异常

- 每处理 `batch_size` 只 ETF 后睡眠 `sleep_ms + 随机抖动`
- 每 `100` 只 ETF 打印一次进度（可通过 `PROGRESS_LOG_INTERVAL` 调整）
- 失败不会中断全局流程，统一累计到 `failures`，最终汇总输出

## 7. 数据源能力边界说明（当前实现）

- `eastmoney`：主采源，区间历史能力完整
- `sina`：降级源，可提供历史数据，但接口形态与字段较简化
- `ths`：兜底源，仅用于“区间包含今天”时补今日快照，不承担历史区间主采

## 8. 常见问题与处理建议

- 东方财富接口不可达：脚本会自动降级到新浪，再降级同花顺。
- 同花顺历史能力说明：当前仅可通过实时快照兜底“今日单日”数据，不适合区间历史主采。
- 日期格式错误：请使用 `YYYY-MM-DD`。
- 执行较慢：可适当调大 `--batch-size`，调小 `--sleep-ms`，并结合网络稳定性调整 `--max-retries`。
