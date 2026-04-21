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

- `WEB_BASE_URL`：待测系统地址（默认 `http://127.0.0.1:3000`）
- `WEB_USERNAME`：登录用户名（必填）
- `WEB_PASSWORD`：登录密码（必填）
- `LOGIN_MODE`：建议保持 `account_password`
- `HEADLESS`：设置为 `false` 可在运行时弹出浏览器窗口观察

## 4. 常用执行命令

### 4.1 全量回归
```bash
npx playwright test
```

### 4.2 执行特定模块
```bash
npx playwright test specs/pvfrs-workflow.spec.ts
```

### 4.3 调试模式 (UI)
```bash
npx playwright test --ui
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
