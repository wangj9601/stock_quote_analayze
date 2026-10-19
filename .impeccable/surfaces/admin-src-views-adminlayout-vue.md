---
version: 1
slug: "admin-src-views-adminlayout-vue"
primary_target: "admin/src/views/AdminLayout.vue"
related_targets: ["admin/src/archive/catalog.ts","admin/src/components/layout/NavMenuGroup.vue","admin/src/style.css","admin/src/views/LoginView.vue"]
---

# 管理端 · 档案分类号

- 模式：Operate
- 受众：内部同事，日间办公，今日 / 策略 / 采集都要一步到达
- 任务：在任意管理页认出档号、当前组，并进入另外两组
- 证明：真实菜单名、路径与权限不变、冰枫堂可见
- 约束：不改接口与策略短码；不把用户站深色作战板搬过来

## Direction contract

THESIS: 每一页都是一份可检索的档案，靠固定档号定位；拒绝常见后台的无编号侧栏和仪表盘英雄数字。
OWN-WORLD: 纸色底 #f3f1ec、墨色字 #1a2332、索引蓝侧栏 #234e70、马尼拉色当前项 #d7b56d。控件是细线纸页和密表，圆角不超过 2px。签名是档号：侧栏项右侧、内容标题、以及始终在场的今日 / 策略 / 采集三扇门。
STORY: 打开即见自己在哪一组；点一扇门进入该组首页；表格里当前行抬起、其余行变淡；同一策略的多个版本以同一尺度并排对照。
FIRST VIEWPORT: 左侧约 248px 索引蓝栏，顶上「冰枫堂」，分组下列出带档号的菜单，当前项铺马尼拉色。右侧先是「档号 · 页名」，其下三扇等宽的门，再是本页密表。主操作留在本页表格或筛选旁，不做成营销主按钮。
FORM: 档案分类号，有序列表第 3 位。seed:28ef1cdce046d3aa
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
