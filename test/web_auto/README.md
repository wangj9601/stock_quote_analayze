# Web 自动化测试（Playwright）

本目录提供两类能力：

- 冒烟扫描：自动登录后遍历主菜单，快速发现页面可用性问题。
- 用例执行：读取 Excel（或 CSV）结构化用例，按步骤执行并断言。

## 文档导航

- 设计文档：`docs/design.md`
- 使用文档：`docs/usage.md`
- 登录策略：`docs/login_strategy.md`

## 1. 安装与准备

```bash
cd test/web_auto
npm install
npx playwright install --with-deps chromium
```

复制配置文件：

```bash
copy .env.web-auto.example .env.web-auto
```

## 2. 登录模式

- `account_password`：账号密码直登（优先配合测试环境免验证码开关）。
- `storage_state`：复用已保存会话态（`STORAGE_STATE_PATH`）。
- `manual_captcha`：首次人工通过验证码，脚本保存会话后自动执行。

## 3. 执行命令

```bash
npm run test:smoke
npm run test:cases
npm run test:all
npm run report
```

## 4. Excel/CSV 用例格式

优先将业务用例整理为以下字段：

- `caseId`
- `title`
- `tags`
- `precondition`
- `stepAction`（`click` / `fill` / `press` / `assertVisible` / `assertText` / `goto`）
- `stepTarget`（Playwright selector 或 URL）
- `stepValue`
- `stepExpect`

模板见：`data/excel/web_cases.template.csv`  
正式用例建议命名为：`data/excel/web_cases.xlsx`
