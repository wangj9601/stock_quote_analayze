# 板块代码映射（同花顺 ↔ 东财）

## 背景

行情页默认展示同花顺板码，实时/列表采集常写入东财码（`BKxxxx`）。双源并存时需持久化映射，避免仅靠同名桥接失败。

## 范围

| board_kind | 说明 |
|---|---|
| `industry` | 行业板（如 881178 ↔ BK0740） |
| `concept` | 概念板（如数字同花顺码 ↔ BK） |

表名历史原因仍为 `industry_board_code_map`，以 `board_kind` 区分。

## 功能

- 同名自动重建（`match_method=name_exact`），保留手工/导入映射
- 行业板列表/详情：按「本码 / 映射对端 / 同名」择优行情，并优先更新时间更新的一条
- 概念板列表/详情：附加 `mapped_em_board_code` / `mapped_ths_board_code`；角色解析优先走映射表
- 行业实时采集：优先按映射镜像东财指数到同花顺码
- 概念列表同步后：自动补全同名映射

## 启用

```bash
python migrations/add_industry_board_code_map.py
```

重启 `backend_api`。

## 管理端

路径：**板块成分股维护** → 行业/概念 →「同花顺 ↔ 东财 代码映射」

API 前缀：`/api/admin/industry-board-code-map`

- `GET /?board_kind=industry|concept` 列表
- `POST /` 手工 upsert（body 含 `board_kind`）
- `POST /rebuild` 按同名重建（body 含 `board_kind`）
- `DELETE /{id}` 停用
- `GET /resolve?board_code=&board_kind=` 查对端码
