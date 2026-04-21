# Web 自动化设计文档

## 1. 设计目标

- 支持 Web 系统的自动登录、功能冒烟扫描、按用例回归执行。
- 兼容验证码场景，支持无人值守和半自动两种执行模式。
- 支持本地执行与 CI 定时执行，并沉淀失败证据（截图/视频/trace/报告）。

## 2. 架构分层

### 2.1 执行层

- 组件：Playwright Test Runner
- 职责：并发调度、重试、报告生成、失败留痕
- 关键文件：`playwright.config.ts`

### 2.2 认证层

- 组件：登录管理器 + 认证夹具
- 职责：根据环境变量选择登录模式，建立可复用登录态
- 关键文件：
  - `src/auth/login-manager.ts`
  - `src/fixtures/auth.fixture.ts`

### 2.3 页面层（POM）

- 组件：页面对象
- 职责：封装页面元素定位与核心交互，减少测试脚本重复代码
- 关键文件：
  - `src/pages/login.page.ts`
  - `src/pages/admin-layout.page.ts`

### 2.4 业务编排层

- 冒烟扫描：遍历侧边菜单并校验页面可见性
- 用例执行：读取结构化用例并逐步执行关键字动作
- 关键文件：
  - `src/runner/smoke-scanner.ts`
  - `src/runner/case-runner.ts`

### 2.5 数据层

- Excel/CSV 输入，解析后转换为标准用例模型
- 支持导出 JSON 供追踪与二次处理
- 关键文件：
  - `src/data/excel-case-parser.ts`
  - `scripts/excel-to-json.ts`

## 3. 核心数据模型

### 3.1 用例模型 `WebCase`

- `caseId`: 用例编号
- `title`: 用例标题
- `tags`: 标签集合
- `precondition`: 前置条件（说明性）
- `steps`: 步骤列表

### 3.2 步骤模型 `WebCaseStep`

- `action`: 执行动作（`click/fill/press/assertVisible/assertText/goto`）
- `target`: 目标选择器或 URL
- `value`: 输入值/按键（可选）
- `expect`: 断言值（可选）

## 4. 登录策略设计

### 4.1 `account_password`（默认）

- 账号密码自动登录
- 可附带测试环境验证码绕过 Header（若后端支持）
- 登录成功后保存 `storageState`

### 4.2 `storage_state`

- 直接复用历史登录态
- 减少重复登录与验证码触发

### 4.3 `manual_captcha`

- 首次登录页人工处理验证码（`page.pause()`）
- 成功后保存 `storageState`，后续自动化继续执行

## 5. 冒烟扫描设计

- 扫描入口：`specs/smoke.spec.ts`
- 扫描规则：
  - 登录后获取侧边栏菜单项
  - 逐项点击并等待页面稳定
  - 断言 `.admin-content` 可见
  - 记录每个菜单项通过/失败信息
- 结果输出：测试注解 + HTML 报告 + 失败证据

## 6. 用例执行设计

- 执行入口：`specs/excel-cases.spec.ts`
- 执行流程：
  - 读取 `data/excel/web_cases.xlsx`
  - 解析并按 `caseId` 聚合步骤
  - 为每条用例动态生成测试
  - 逐步执行动作与断言
- 容错策略：
  - Excel 缺失时跳过整组用例（避免 CI 误红）
  - 不支持动作时显式抛错

## 7. CI 设计

- 工作流文件：`.github/workflows/web-auto-e2e.yml`
- 触发方式：
  - 定时（每日）
  - 手动触发
- 执行顺序：
  - 安装依赖与浏览器
  - 执行 `test:smoke`
  - 执行 `test:cases`
  - 上传报告
  - 失败时可选 webhook 告警

## 8. 可扩展性建议

- 在 `case-runner` 增加动作：`select`, `check`, `upload`, `assertUrl`
- 增加前后置钩子：数据准备、清理、接口桩
- 引入分层标签执行：`@smoke/@regression/@critical`
- 接入 Allure 或统一测试看板做趋势分析
