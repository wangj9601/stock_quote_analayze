# ETF历史迁移脚本使用说明

脚本路径：`manual_scripts/etf_historical_migration.py`

## 1. 功能概述

- 从多数据源迁移 ETF 历史行情到 `fund_historical_quotes`。
- 数据源自动降级顺序：东方财富 -> 新浪 -> 同花顺（同花顺仅做今日单日快照兜底）。
- 使用 `(code, date)` 主键幂等写入（`ON CONFLICT DO UPDATE`）。

## 2. 参数说明

- `--start-date`：开始日期，格式 `YYYY-MM-DD`（必填）
- `--end-date`：结束日期，格式 `YYYY-MM-DD`（必填）
- `--codes`：ETF 代码列表（可选，不传则读取 `fund_basic_info` 启用列表）
- `--batch-size`：每批处理 ETF 数量，默认 `20`
- `--sleep-ms`：每批处理后的休眠毫秒数，默认 `500`
- `--skip-existing`：仅补缺，不更新已存在记录
- `--recalc-indicators`：迁移后重算 ETF 指标
- `--max-retries`：单数据源最大重试次数，默认 `3`

## 3. 常用命令

### 3.1 单只 ETF 小范围回填

```bash
python manual_scripts/etf_historical_migration.py --start-date 2026-04-01 --end-date 2026-04-05 --codes 510300 --batch-size 1 --sleep-ms 0
```

### 3.2 全量启用 ETF 历史回填

```bash
python manual_scripts/etf_historical_migration.py --start-date 2025-01-01 --end-date 2026-04-20
```

### 3.3 仅补缺模式（不覆盖已有数据）

```bash
python manual_scripts/etf_historical_migration.py --start-date 2025-01-01 --end-date 2026-04-20 --skip-existing
```

### 3.4 回填后重算指标

```bash
python manual_scripts/etf_historical_migration.py --start-date 2026-01-01 --end-date 2026-04-20 --codes 510300 159915 --recalc-indicators
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

- 默认模式：同一 `(code, date)` 再次执行会更新（幂等覆盖）。
- `--skip-existing` 模式：已存在记录会被跳过，只写入缺失日期。

## 6. 常见问题与处理建议

- 东方财富接口不可达：脚本会自动降级到新浪，再降级同花顺。
- 同花顺历史能力说明：当前仅可通过实时快照兜底“今日单日”数据，不适合区间历史主采。
- 日期格式错误：请使用 `YYYY-MM-DD`。
- 执行较慢：可适当调大 `--batch-size`，调小 `--sleep-ms`，并结合网络稳定性调整 `--max-retries`。
