# 分析频道：龙头/中军加入 GMS 策略观察股

## 能力

在分析频道「板块分析」「龙头中军」短线角色区，可将当前板的龙头、中军写入 **GMS 策略观察股**（管理端「GMS策略版本」观察股池 / 选股页 `GMS观察股` 范围）。

- 单只：角色 pill 旁「+观察股」
- 批量：本板「龙头+中军全部加入」
- 去重：已在启用版本观察股中则跳过；Toast 汇总新增/跳过/失败

## API / 表

| 项 | 说明 |
|----|------|
| `POST /api/analysis/gms-strategy-watchlist/add` | Body: `{ stocks:[{code,name,market?,role?}], board_code?, board_name?, remark? }` |
| 表 | `gms_strategy_version_stocks`（写入主启用 `gms_strategy_versions`） |
| 服务 | `backend_api/services/gms_strategy_watchlist.py`（与交易观察同步同一套） |

权限（任一即可）：`channel.analyze.tab.board.btn.gms_watchlist`、`channel.analyze.tab.leader_mid.btn.gms_watchlist`、或已有 `channel.analyze.tab.board.btn.observe`。

## 验证

1. 分析频道 → 板块分析 → 选择板块，短线角色出现后点「+观察股」或「全部加入」
2. 选股页 GMS → 范围选「GMS观察股」刷新，应能看到新加入代码
3. 管理端 GMS 策略版本 → 观察股列表亦可核对；重复加入应 Toast「跳过」
