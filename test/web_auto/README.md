# Web 自动化测试（Playwright）

本仓库提供一套基于 Playwright 1.54+ 的企业级 Web 自动化测试框架，支持管理后台的全流程业务校验。

## 核心设计

- **POM (Page Object Model)**：所有页面交互封装在 `src/pages` 中，选择器与测试逻辑解耦。
*   **Fixtures (自动登录)**：通过 `src/fixtures/auth.fixture.ts` 实现测试前自动登录，无需在 Spec 中重复编写登录逻辑。
- **业务 Spec**：在 `specs/` 目录下使用 TypeScript 编写强类型的测试脚本。
- **Excel 驱动 (旧版兼容)**：支持通过 Excel 描述简单步骤（适用于无代码背景的 QA）。

## 1. 快速开始

### 安装环境
```bash
cd test/web_auto
npm install
npx playwright install --with-deps chromium
```

### 配置环境变量
复制 `.env.web-auto.example` 并命名为 `.env.web-auto`：
```bash
WEB_BASE_URL=http://localhost:3000
WEB_USERNAME=admin
WEB_PASSWORD=admin123
```
> [!IMPORTANT]
> 必须提供 `WEB_USERNAME` 和 `WEB_PASSWORD` 才能执行需要登录的测试任务。

## 2. 常用执行命令

| 描述 | 命令 |
| :--- | :--- |
| 运行所有测试 (Headless) | `npx playwright test` |
| 运行单个测试文件 | `npx playwright test specs/pvfrs-workflow.spec.ts` |
| 进入 GUI 模式 (有头) | `npx playwright test --headed` |
| 只运行冒烟测试 | `npm run test:smoke` |
| 查看测试报告 | `npm run report` |

## 3. 开发指南 (POM)

### 编写页面对象 (POM)
在 `src/pages/` 下创建 `.page.ts` 文件：
```typescript
export class MyPage {
  constructor(readonly page: Page) {
    this.button = page.getByRole('button', { name: '提交' });
  }
  async submit() { await this.button.click(); }
}
```

### 编写测试用例 (Spec)
在 `specs/` 下创建 `.spec.ts` 文件。
> [!CAUTION]
> **ESM 导入规则**：在 `specs` 中导入内部模块时，路径必须包含 `.js` 后缀。
```typescript
import { test, expect } from '../src/fixtures/auth.fixture.js';
import { PVFRSPage } from '../src/pages/pvfrs.page.js';

test('业务流程测试', async ({ authenticatedPage }) => {
  const page = new PVFRSPage(authenticatedPage);
  await page.goto();
  // 执行操作...
});
```

## 4. 常见问题排查

- **Cannot find module '.../auth.fixture'**：请检查导入路径末尾是否漏掉了 `.js` 后缀。
- **缺少 WEB_USERNAME 错误**：确保 `test/web_auto/.env.web-auto` 文件存在且包含正确的用户名密码。
- **浏览器未安装**：执行 `npx playwright install chromium`。

---
更多详情请参考 [使用手册](file:///e:/wangxw/work/stock_quote_analayze/test/web_auto/docs/usage.md)。
