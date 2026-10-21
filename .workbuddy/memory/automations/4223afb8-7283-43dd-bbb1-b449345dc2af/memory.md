# 自动化「URT策略推送任务」执行记忆

- 自动化 ID：`4223afb8-7283-43dd-bbb1-b449345dc2af`
- 名称：URT策略推送任务 ｜ 提示词：推送每日 URT 策略信号列表
- 调度：每天 12:58（recurring）｜cwd：项目根

## 执行方式（已验证，可复用）
复用项目既有推送链路，零改动代码：
- 脚本：`.workbuddy/tmp/push_urt_daily.py`（用系统 Python 3.12 跑）
- 解释器：`C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe`
  （该解释器已装 fastapi/psycopg2/sqlalchemy/pandas/openpyxl；WorkBuddy 托管 3.13 无依赖）
- 逻辑：`get_push_service(db)` → 对所有 `enabled 且 report_type='urt_daily'` 的 `user_push_configs`
  调 `push_service.push_to_user(user_id, push_time=f"M%H:%M:%S", config_id, force=True)`
- 结果落盘：`.workbuddy/tmp/push_urt_daily_result.json`

## 关键环境事实
- 本机服务在跑：API:5000、前端:8000、管理端:8001、PostgreSQL:5446（DB_URL 见 .env 的 DB_*）
- psql：`/d/Program Files/PostgreSQL/17/bin/psql`，口令取 `.env` 的 `DB_PASSWORD`
- `.env` 已配默认企微（WECHAT_CORP_*，profile 空）
- `watchlist` 表无 market 列（仅 stock_code/stock_name/group_name）；`historical_quotes.date` 为 text
- 报告输出目录：`reports/csv/`；信号表 `urt_signal_trace`（唯一键 code+date+config_id）
- URT 信号日取「最近一个已完成交易日」（收盘后才有当日 bar；盘中跑=上一交易日）

## 历史执行
### 2026-10-21 12:59（第 10 次）
- 复用同一脚本，链路照常跑通（未探测服务，推送只依赖 DB+推送服务）
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success
  - `reports/csv/urt_7_20261020_125934.xlsx`（17 行，0 买点，得分 24.7–67.4，均值 42.3；Top 002557洽洽食品 67.4）
  - `reports/csv/urt_6_20261020_130044.xlsx`（76 行，0 买点，得分 24.0–67.8，均值 39.4；Top 002832比音勒芬 67.8）
- 信号日推进到 **2026-10-20**（周二收盘）；`historical_quotes` 最新=10-20（5567 只），采集已与信号日同步
- 风险主因：user7「空头趋势」13 +「上行空间不足」11；user6「空头趋势」58 +「上行空间不足」48（空头占比明显升高，与上周结构不同）
- **数据质量告警（延续）**：`historical_quotes` 仍缺 2026-10-12（周一），已连续 7 天未修复；10-13~10-20 各日均 ~5567 只正常
- 观察：`urt_signal_trace` 10-20=7571，较 10-19 的 5348 明显回升（类似 10-13 的 8332 高位波动）

### 2026-10-20 12:59（第 9 次）
- 复用同一脚本，链路照常跑通；服务未探测（推送只依赖 DB+推送服务）
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success，push_records 179 / 180
  - `reports/csv/urt_7_20261019_125953.xlsx`（9 行，0 买点，得分 31.7–64.9，均值48.5；Top 002557洽洽食品64.9 RR12.85）
  - `reports/csv/urt_6_20261019_130102.xlsx`（27 行，0 买点，得分 33.5–70.5，均值47.4；Top 002832比音勒芬70.5）
- 信号日推进到 **2026-10-19**（周一收盘）；`historical_quotes` 最新=10-19（5567 只）
- 名单换手：user7 新增洽洽食品/退出光线传媒；user6 40→27 行，新增4退出17（收敛明显）
- 风险主因：user7「上行空间不足」7 +「空头趋势」4；user6「上行空间不足」15 +「空头趋势」12
- **数据质量告警（延续）**：`historical_quotes` 仍缺 2026-10-12（周一）、09-25，已连续 6 天未修复
- 观察结论：`urt_signal_trace` 10-19=5348，与 10-16/10-15 持平 → 此前 8332→5349 的跳水已稳定，非持续衰减

### 2026-10-19 12:59（第 8 次，当日第 2 次）
- 复用同一脚本，链路照常跑通；服务状态未探测（推送只依赖 DB+推送服务）
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success，push_records 177 / 178
  - `reports/csv/urt_7_20261016_125932.xlsx`（9 行，0 买点，得分 35.1–62.6；Top 600285羚锐制药62.6）
  - `reports/csv/urt_6_20261016_130027.xlsx`（40 行，0 买点，得分 23.9–65.7；Top 000993闽东电力65.7）
- 信号日仍为 **2026-10-16**（周一盘中运行=上一交易日收盘），`historical_quotes` 最新=10-16（5569 只）
- user7 池行数与上午一致（9 行）；风险主因：user6「上行空间不足」25 次 +「空头趋势」23 次
- **数据质量告警（延续）**：`historical_quotes` 仍缺 2026-10-12（周一）、09-25；建议排查日更采集
- 观察：`urt_signal_trace` 每日行数从 10-13 的 8332 降到 10-16 的 5349，需留意后续扫描覆盖是否为正常收敛

### 2026-10-19 08:41（第 7 次）
- 复用同一脚本，链路照常跑通；**本次 API5000/前端8000/管理端8001 均未启动，仅 PG5446 在线**——推送链路只依赖 DB+推送服务，不受影响（可作为常备结论）
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success，push_records 175 / 176
  - `reports/csv/urt_7_20261016_084206.xlsx`（9 行，0 买点，得分 35.1–62.6；Top 600285羚锐制药62.6）
  - `reports/csv/urt_6_20261016_084330.xlsx`（40 行，0 买点，得分 23.9–65.7；Top 000993闽东电力65.7）
- 信号日推进到 **2026-10-16**（最新交易日，周一盘前运行=上周五收盘数据）；`historical_quotes` 最新=10-16（5569 只）
- user7 池行数明显收窄（19→9 行），为连阳/多头条件过滤所致，非异常
- **数据质量告警（延续）**：`historical_quotes` 仍缺 2026-10-12（周一）

### 2026-10-16 13:00（第 6 次）
- 复用同一脚本，链路照常跑通；服务（API5000/前端8000/管理端8001/PG5446）均在
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success，push_records 173 / 174
  - `reports/csv/urt_7_20261015_125925.xlsx`（19 行，0 买点，得分 28.5–64.1；Top 600285羚锐制药64.1）
  - `reports/csv/urt_6_20261015_130015.xlsx`（72 行，0 买点，得分 19.9–63.8；Top 002990盛视科技63.8）
- 信号日推进到 **2026-10-15**（最新交易日）；`historical_quotes` 最新=10-15（5568 只），采集已追上信号日
- **数据质量告警（延续）**：仍缺 2026-10-12（周一）；近 14 个有数据日：10-15,10-14,10-13,10-09,10-08,09-30,09-29,09-28,09-24,09-23,09-22,09-21,09-18,09-17

### 2026-10-15 13:00（第 5 次）
- 复用同一脚本，链路照常跑通；服务（API5000/前端8000/管理端8001/PG5446）均在
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success，push_records 171 / 172
  - `reports/csv/urt_7_20261014_130029.xlsx`（13 行，**1 买点**：600285 羚锐制药 得分70.1 RR2.77；得分 31.6–70.1）
  - `reports/csv/urt_6_20261014_130141.xlsx`（57 行，0 买点，得分 17.3–64.7；Top 000993闽东电力/002832比音勒芬 均 64.7）
- 信号日推进到 **2026-10-14**（上一交易日）；`historical_quotes` 最新=10-14（5566 只）
- **数据质量告警（延续）**：`historical_quotes` 仍缺 2026-10-12（周一）数据；缺口会扰动 MA20 / 连阳计数

### 2026-10-14 12:59（第 4 次）
- 复用同一脚本，链路照常跑通；服务（API5000/前端8000/管理端8001/PG5446）均在
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success，push_records 169 / 170
  - `reports/csv/urt_7_20261013_125943.xlsx`（20 行，0 买点，得分 27.1–69.1）
  - `reports/csv/urt_6_20261013_130048.xlsx`（86 行，0 买点，得分 17.2–73.5）
- 信号日推进到 **2026-10-13**（上一交易日）；`historical_quotes` 最新=10-13
- **数据质量告警（延续）**：`historical_quotes` 存在零星缺失交易日 —— 10-12(周一)、09-25 等无数据；
  近 12 个有数据日：10-13,10-09,10-08,09-30,09-29,09-28,09-24,09-23,09-22,09-21,09-18,09-17。
  缺口会扰动 MA20 / 连阳计数，建议排查日更采集完整性（`trading_calendar` 仍为空表）

### 2026-10-13 12:59（第 3 次）
- 复用同一脚本，链路照常跑通；服务（API5000/前端8000/管理端8001/PG5446）均在
- 同 2 条 enabled urt_daily 配置（id=13→user7、id=14→user6），均 success，push_records 167 / 168
  - `reports/csv/urt_7_20261009_125931.xlsx`（20 行，0 买点，得分 33.5–63.2）
  - `reports/csv/urt_6_20261009_130031.xlsx`（72 行，0 买点，得分 28.7–68.7）
- 信号日仍为 2026-10-09；**告警：`historical_quotes` 缺 2026-10-12（周一）数据，最新仅到 10-09**，疑似日更采集滞后（`trading_calendar` 为空表，无法用日历佐证）
- 注意：读取最新报告不要用文件名排序（HHMMSS 会跨日串位），应从 result json 的 report_file_path 取

### 2026-10-12 13:05（第 2 次）
- 复用同一脚本，链路照常跑通，前后端/DB/依赖均在线
- 目标 2 条 enabled urt_daily 配置：id=13→user7(wangxw1, email+wechat)、id=14→user6(wangxw, wechat)
- 结果：均 success；push_records 165 / 166
  - `reports/csv/urt_7_20261009_130544.xlsx`（20 行，0 买点，得分 33.5–63.2）
  - `reports/csv/urt_6_20261009_130654.xlsx`（72 行，0 买点，得分 28.7–68.7）
- 信号日 2026-10-09（上一交易日）；两池当日均 0 正式买点，主因「上行空间不足」+「空头趋势」硬闸否决
- 两账号 wechat_userid 同为 WangXueWu → 微信端仍收 2 条（去重问题未处理）

### 2026-10-12 13:01（首次）
- 目标：`user_push_configs` 中 enabled 的 urt_daily 共 2 条
  - id=13 → user 7 (wangxw1)，渠道 email+wechat
  - id=14 → user 6 (wangxw)，渠道 wechat
- 两账号 `wechat_userid` 同为 `WangXueWu`（同一微信，故会收到 2 条）
- 结果：均 success。生成报告
  - `reports/csv/urt_7_20261009_130206.xlsx`（20 行，0 买点）
  - `reports/csv/urt_6_20261009_130308.xlsx`（72 行，0 买点）
  - push_records 163 / 164
- 信号日 2026-10-09；两只自选池当日均无正式买点（均为连阳硬筛观察标的）
- 注意：若用户只要「仅推自己」，需停用其中一个 urt_daily 配置（当前两条都会推 → 微信重复）
