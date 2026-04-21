# Web 自动化使用文档

## 1. 目录说明

- 根目录：`test/web_auto`
- 冒烟测试：`specs/smoke.spec.ts`
- 用例回归：`specs/excel-cases.spec.ts`
- Excel 模板：`data/excel/web_cases.template.csv`
- 登录策略：`docs/login_strategy.md`

## 2. 环境准备

在 `test/web_auto` 目录执行：

```bash
npm install
npx playwright install --with-deps chromium
```

复制并配置环境变量：

```bash
copy .env.web-auto.example .env.web-auto
```

## 3. 环境变量说明

- `WEB_BASE_URL`：待测系统地址（如 `http://127.0.0.1:3000`）
- `WEB_USERNAME`：登录用户名
- `WEB_PASSWORD`：登录密码
- `LOGIN_MODE`：登录模式（`account_password/storage_state/manual_captcha`）
- `STORAGE_STATE_PATH`：登录态文件路径（默认 `.auth/storage-state.json`）
- `HEADLESS`：是否无头执行（`true/false`）
- `CAPTCHA_BYPASS_HEADER_KEY`：可选，验证码绕过 Header 键
- `CAPTCHA_BYPASS_HEADER_VALUE`：可选，验证码绕过 Header 值

## 4. 常用命令

### 4.1 冒烟扫描

```bash
npm run test:smoke
```

### 4.2 Excel 用例回归

```bash
npm run test:cases
```

### 4.3 全量执行

```bash
npm run test:all
```

### 4.4 查看报告

```bash
npm run report
```

### 4.5 Excel 转 JSON

```bash
npm run excel:convert
```

## 5. Excel 用例编写规范

建议将业务用例整理成 `web_cases.xlsx`，字段如下：

- `caseId`
- `title`
- `tags`（逗号分隔）
- `precondition`
- `stepAction`
- `stepTarget`
- `stepValue`
- `stepExpect`

动作说明：

- `click`：点击元素（`stepTarget` 为选择器）
- `fill`：输入文本（`stepValue` 为输入值）
- `press`：按键（`stepValue` 如 `Enter`）
- `assertVisible`：断言元素可见
- `assertText`：断言元素包含文本（`stepExpect`）
- `goto`：访问 URL（`stepTarget` 为地址）

## 6. 登录模式实践建议

- **推荐**：测试环境支持免验证码，使用 `account_password`
- **次选**：先人工登录一次，再用 `storage_state`
- **过渡**：`manual_captcha` 模式联调

若你们系统必须滑块/图形验证码，建议先让后端给测试账号开白名单或测试开关。

## 7. 失败排查

- 登录失败：检查 `WEB_BASE_URL/用户名/密码` 与登录接口可用性
- 选择器失效：页面改版后更新 `stepTarget` 或 POM
- 用例未执行：确认 `data/excel/web_cases.xlsx` 已放置且字段正确
- CI 失败：查看 `playwright-report` artifact 与截图/trace

## 8. CI 接入

已提供工作流：`.github/workflows/web-auto-e2e.yml`

建议在仓库 Secrets 中配置：

- `WEB_BASE_URL`
- `WEB_USERNAME`
- `WEB_PASSWORD`
- `LOGIN_MODE`
- `WEB_AUTO_ALERT_WEBHOOK`（可选）
