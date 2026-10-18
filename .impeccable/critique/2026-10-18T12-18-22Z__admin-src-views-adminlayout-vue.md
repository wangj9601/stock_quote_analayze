---
target: admin管理端界面
total_score: 19
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:E:\\wangxw\\work\\stock_quote_analayze\\admin\\src\\views\\AdminLayout.vue"
target_fingerprint: "sha256:2a736013b6fad12cb645ee201e621a7c407f36d216f06e08747620ac02157f96"
target_path: "E:\\wangxw\\work\\stock_quote_analayze\\admin\\src\\views\\AdminLayout.vue"
timestamp: 2026-10-18T12-18-22Z
slug: admin-src-views-adminlayout-vue
closed: true
---
Method: dual-agent (A: f459396c-25b6-407d-ab7e-60dca51ae98d · B: bdf2e8dd-81a3-4e1c-8a96-84ef8c645605)

# 管理端界面：优化与重构空间

目标：`admin/src/views/AdminLayout.vue`（壳层代表整个 Vue 管理端）。模式：Operate。检测器 3 条警告；浏览器叠层未注入（没有正在运行的管理端服务）。

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | 桌面顶栏隐藏；预计算成功只 toast，状态卡不更新 |
| 2 | Match System / Real World | 2 | 策略短码在，壳的心智模型不在；同步结果甩英文计数 |
| 3 | User Control and Freedom | 2 | 预计算、强制采集、Push 没有撤销；路由 key 一变整页重挂 |
| 4 | Consistency and Standards | 2 | 登录手写表单，站内 Element；策略页标题层级不统一 |
| 5 | Error Prevention | 2 | 退出登录的确认重于全市场预计算和「先删除后插入」 |
| 6 | Recognition Rather Than Recall | 2 | 21 项平铺；图标复用；PVFRS 在路由里不在菜单里 |
| 7 | Flexibility and Efficiency | 1 | 无快捷键、无最近访问；加速器只有侧栏收起 |
| 8 | Aesthetic and Minimalist Design | 2 | 四张同权状态卡先于任务；监控用危险色标进程数 |
| 9 | Error Recovery | 2 | 预计算失败只有 toast，不指出下一步 |
| 10 | Help and Documentation | 2 | 个别对话框有说明，壳层没有策略短码对照 |
| **Total** | | **19/40** | **Poor** |

## Design Specificity Verdict

**LLM assessment：** 通用 Element Plus 后台。侧栏标题是「管理后台」，登录是灰底加 indigo 主按钮，选中态是 `blue-50`。策略短码只出现在菜单文字里。`DESIGN.md` 写明用户站作战标图不约束管理端，管理端也没有另做一套冰枫堂运营语言。稳定的领域信号几乎只有仪表盘资金流的涨红跌绿。品牌「冰枫堂」没有进入壳和登录。

**Deterministic scan：** `impeccable detect admin/src` 退出码 2，3 条 warning，全是 slop。`DataCollectView.vue` 两处装饰色（`text-purple-600` 统计数字、`text-indigo-400` 图标）；`ReportDetail.vue` 指标卡 `border-left: 3px solid #3b82f6`。检测器没扫到信息架构和确认等级，这两项是人工评审的主结论。紫色/靛蓝不是误报，只是「on heading」的归因偏了。

**Visual overlays：** 没有可靠的页内叠层。终端里没有管理端开发服务，按约定没有自行拉起应用。

## Overall Impression

能完成日常运维，但壳层可以换成任何内部系统。最大机会不是把管理端涂成用户站深色作战板，而是把 21 个平铺入口收成少数任务组，并让破坏性作业的确认和结束后状态配得上它的后果。

## What's Working

- 仪表盘资金流向把周期、图形/列表、行业与概念放在同一张卡片，涨红跌绿和点柱看成分股符合 A 股习惯。
- 窄屏抽屉、遮罩和触控高度是认真做过的，不是只写了桌面侧栏。
- 用户管理已收成四个 Tab；环境同步把密钥留在服务端，轮换后要求立即复制明文。

## Priority Issues

### [P1] 侧栏 21 项平铺
- **Why it matters：** 操作员每天在采集、预计算、回测之间跳，现在策略、行情作业、访问审计混在一条列表里，点错策略的成本先于任务本身。
- **Fix：** 在 `AdminLayout.vue` 的 `menuItems` 收成四组：今日看板、策略、行情与采集、访问与审计。组内再用短码。复用已有的 `NavMenuGroup.vue`。
- **Suggested command：** /impeccable layout

### [P1] 危险作业的确认弱于退出
- **Why it matters：** 全市场预计算（空版本等于全部启用版本）、勾选「强制更新（先删除后插入）」后的开始采集、Push 到生产，都没有和退出登录同级的停顿。成功后状态卡不刷新，操作员要自己记得残留买点。
- **Fix：** 退出用普通确认；删除、强制覆盖、Push、全市场预计算用危险确认，并带上策略、市场、日期。提交后在页面留下任务条，而不是只 toast。落点：`CsbManagementView.vue`、`UrtManagementView.vue`、`DataCollectView.vue`、`EnvSyncView.vue`。
- **Suggested command：** /impeccable harden

### [P1] 壳层没有冰枫堂
- **Why it matters：** 内部操作员看不出这是冰枫堂的研究运维。登录副文案是「请输入您的登录凭据」。
- **Fix：** 侧栏和登录写上「冰枫堂」。保持浅色密度，只借用涨跌色和短码字号，不要套 `body.ops-map` 暗底。
- **Suggested command：** /impeccable colorize

### [P2] 策略页壳复制
- **Why it matters：** CSB 与 URT 几乎同构；SBBR、DBLB、CUPB、KGT、RPE 各自再写一套页头加预计算。改一次确认要改多文件，版式也不能帮操作员区分策略。
- **Fix：** 抽一个策略运营壳（状态、Tab、预计算对话框），各策略只填短码和参数。表格和表单继续用 Element Plus。
- **Suggested command：** /impeccable distill

### [P2] 桌面没有当前位置
- **Why it matters：** 顶栏在宽屏被藏起。侧栏一收，主区没有页名。
- **Fix：** 桌面主区保留一条细页眉：当前组、当前页、主操作。`currentPageName` 不要只供给窄屏。
- **Suggested command：** /impeccable layout

## Persona Red Flags

**Alex（每日跑采集和预计算的操作员）：** 没有最近策略，GMS 版本和 GMS 回测不相邻。强制采集没有确认，熟练用户会把「开始采集」当成可重复的安全动作。

**Sam（键盘和读屏）：** 登录框主要靠占位符。收起侧栏后没有页名。预计算没有可聚焦的进度区，状态变化靠 toast。

**Riley（压边界）：** 候选上限可到很大，空版本表示全量，失败只 toast。路由里有 PVFRS，菜单没有，深链和菜单承诺不一致。`router-view` 用完整路径做 key，中途改查询会丢掉未提交内容。

## Minor Observations

- 检测器抓到的紫色、靛蓝和 3px 蓝左边框，是浅色壳上的装饰色，应收回涨跌色和一种导航强调色。
- `TrendCharts` 等图标在行情、回测、形态、URT、CSB 上复用，不能当识别线索。
- ICP 备案在登录和壳底各一份，权重应低于任务区。

## Questions to Consider

- 管理端要不要继续保持浅色操作密度，只借用户站的品牌和涨跌色？
- 策略运营壳抽成一个之后，GMS 和 PVFRS 的「四卡」变体是否一并收进去？
- 侧栏先分组，还是先给预计算和 Push 补上对象级确认？
