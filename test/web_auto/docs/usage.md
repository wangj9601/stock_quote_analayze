# Web 自动化使用文档

## 1. 目录说明

- **根目录**：`test/web_auto`
- **业务脚本 (Specs)**：`specs/`
  - `pvfrs-workflow.spec.ts`：PVFRS 策略全生命周期测试
  - `gms-workflow.spec.ts`：GMS 回测管理测试
  - `users-management.spec.ts`：用户管理测试
  - `market-data.spec.ts`：行情浏览测试
  - `data-collection.spec.ts`：采集任务启动测试
  - `smoke.spec.ts`：全菜单页面可用性扫描
- **页面对象 (POM)**：`src/pages/`
  - 存放各页面的 Locator 封装及核心 Action。
- **配置与工具**：`src/config.ts`, `src/fixtures/`

## 2. 环境准备

### 2.1 首次安装（在 `test/web_auto` 目录执行）

```bash
npm install
npx playwright install --with-deps chromium
```

复制并配置环境变量：

```bash
copy .env.web-auto.example .env.web-auto
```

### 2.2 升级依赖后重装浏览器（推荐）

当 `@playwright/test` 版本升级、切换机器、清理缓存后，建议重新执行：

```bash
npx --prefix test/web_auto playwright install chromium
```

## 3. 环境变量说明

- `WEB_BASE_URL`：待测系统地址（默认 `http://127.0.0.1:3000`）
- `WEB_USERNAME`：登录用户名（必填）
- `WEB_PASSWORD`：登录密码（必填）
- `LOGIN_MODE`：建议保持 `account_password`
- `HEADLESS`：设置为 `false` 可在运行时弹出浏览器窗口观察

## 4. 常用执行命令

> 建议优先使用下面“仓库根目录可直接执行”的命令，避免在错误目录执行 `npx playwright test` 导致误扫描其他测试（如 `admin` 下的 `*.test.ts`）。

### 4.1 全量回归
```bash
npx --prefix test/web_auto playwright test --config test/web_auto/playwright.config.ts
```

### 4.2 执行特定模块
```bash
npx --prefix test/web_auto playwright test --config test/web_auto/playwright.config.ts test/web_auto/specs/pvfrs-workflow.spec.ts
```

### 4.3 调试模式 (UI)
```bash
npx --prefix test/web_auto playwright test --config test/web_auto/playwright.config.ts --ui
```

### 4.4 在 `test/web_auto` 目录执行（等价写法）
```bash
npx playwright test
```

## 5. 开发指南：如何新增一个测试

### 步骤 A：创建页面对象 (POM)
在 `src/pages/` 创建新文件，如 `report.page.ts`：
```typescript
export class ReportPage {
  constructor(readonly page: Page) {
    this.table = page.locator('.report-table');
  }
  async download(id: string) {
    await this.table.locator(`tr:has-text("${id}")`).getByText('下载').click();
  }
}
```

### 步骤 B：编写业务脚本 (Spec)
在 `specs/` 创建新文件。**注意：相对路径导入必须带 `.js` 后缀**：
```typescript
import { test, expect } from '../src/fixtures/auth.fixture.js';
import { ReportPage } from '../src/pages/report.page.js';

test('下载报告测试', async ({ authenticatedPage }) => {
  const reportPage = new ReportPage(authenticatedPage);
  await authenticatedPage.goto('/reports');
  await reportPage.download('REP-001');
  // ... 加上断言
});
```

### 步骤 C：选择器与断言稳定性规范（强烈建议）
1. **优先语义定位**：优先 `getByRole`、`getByLabel`、`getByPlaceholder`，少用纯 class 链。
2. **限定作用域**：页面有多 tab / 多表单时，先定位到容器（如 tabpanel、dialog、form card）再找子元素。
3. **Element Plus Select**：优先点击 `.el-select` 容器，不直接点内部 `input.el-select__input`，否则容易被 placeholder 层拦截。
4. **避免 strict mode 冲突**：文本可能重复时，使用 `getByRole(...).first()` 或在容器内查找，不直接全页 `getByText('xxx')`。
5. **环境敏感断言降级**：后端数据/任务调度不稳定时，`@case` 先校验“提交动作完成 + 页面状态正确”，再做“结果落库/列表出现”。
6. **保留可诊断信息**：失败后优先看 `test-results/**/error-context.md` 的 page snapshot，再改定位器。

## 6. 常见排障

### 6.1 导入报错 (Module Not Found)
因为项目使用 `ESM (NodeNext)`，TS 在编译时要求显式指定 `.js`。
- ❌ `import { X } from '../pages/my.page'`
- ✅ `import { X } from '../pages/my.page.js'`

### 6.2 登录超时或失败
1. 检查 `.env.web-auto` 中的账号密码是否正确。
2. 检查 `WEB_BASE_URL` 是否可达。
3. 如果系统有验证码，请在测试环境开启“万能验证码”或“验证码绕过”。

### 6.3 选择器不生效
- 使用 `npx playwright test --debug` 启动步进式调试。
- 建议优先使用 `page.getByRole` 或 `page.getByPlaceholder` 等面向用户的 Locator。

### 6.7 Element Plus 组件点击超时（被 placeholder 遮挡）
报错特征示例：
- `... intercepts pointer events`
- 点击 `combobox` / `el-select__input` 超时

处理建议：
1. 不要点内部 `input.el-select__input`，改点外层 `.el-select` 容器（必要时 `click({ force: true })`）。
2. 用表单项标签限定作用域，例如：先定位包含“角色/回测模式”的 `el-form-item`，再找 `.el-select`。
3. 下拉项优先用 `getByRole('option', { name: 'xxx' })` 选择，减少对 DOM 结构的耦合。

### 6.8 strict mode violation（命中多个元素）
报错特征示例：
- `strict mode violation: ... resolved to 2 elements`

处理建议：
1. 给定位器加上下文：先定位 tabpanel / dialog / card，再在局部查找。
2. 将模糊文本改为语义定位（例如 tab 用 `getByRole('tab', { name: '策略配置' })`）。
3. 对可接受的重复目标，用 `.first()` 或更精确的 name（避免裸 `getByText` 全页搜索）。

### 6.4 浏览器可执行文件缺失（Executable doesn't exist）
报错特征示例：
- `browserType.launch: Executable doesn't exist ...`
- 日志提示 `Please run: npx playwright install`

处理步骤：
1. 在仓库根目录执行：`npx --prefix test/web_auto playwright install chromium`
2. 验证安装状态：`npx --prefix test/web_auto playwright install --dry-run`
3. 再执行测试：
   - 根目录：`npx --prefix test/web_auto playwright test --config test/web_auto/playwright.config.ts`
   - 或 `test/web_auto` 目录：`npx playwright test`

### 6.5 缺少登录账号密码（WEB_USERNAME / WEB_PASSWORD）
报错特征示例：
- `缺少 WEB_USERNAME 或 WEB_PASSWORD，无法执行账号密码登录。`

处理步骤：
1. 在 `test/web_auto` 目录确认存在 `.env.web-auto`（若无则复制：`copy .env.web-auto.example .env.web-auto`）
2. 在 `.env.web-auto` 中填写：
   - `WEB_USERNAME=你的测试账号`
   - `WEB_PASSWORD=你的测试密码`
3. 重新执行测试（建议先跑一个用例验证）：`npx playwright test specs/users-management.spec.ts`

### 6.6 连接被拒绝（ERR_CONNECTION_REFUSED）
报错特征示例：
- `page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:3000/login`

处理步骤：
1. 检查被测系统是否启动并可访问（默认地址 `http://127.0.0.1:3000`）
2. 若端口不是 `3000`，在 `.env.web-auto` 中设置正确地址：
   - `WEB_BASE_URL=http://127.0.0.1:实际端口`
3. 打开浏览器手动访问 `WEB_BASE_URL/login`，确认页面可达后再运行 E2E
