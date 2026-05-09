import { test, expect } from '../src/fixtures/auth.fixture.js'
import { DashboardPage } from '../src/pages/dashboard.page.js'
import { StockBasicPage } from '../src/pages/stock-basic.page.js'
import { IndicatorsPage } from '../src/pages/indicators.page.js'
import { SelectionResultsPage } from '../src/pages/selection-results.page.js'
import { DataSourcePage } from '../src/pages/datasource.page.js'
import { MonitoringPage } from '../src/pages/monitoring.page.js'
import { ModelsPage } from '../src/pages/models.page.js'
import { LogsPage } from '../src/pages/logs.page.js'
import { ReportManagementPage } from '../src/pages/report-management.page.js'

test.describe('管理端全模块加载冒烟 @module', () => {
  test('仪表板模块可加载 @module @smoke', async ({ authenticatedPage }) => {
    const pageObject = new DashboardPage(authenticatedPage)
    await pageObject.goto()
    await pageObject.expectLoaded()
  })

  test('股票基本信息模块可加载 @module', async ({ authenticatedPage }) => {
    const pageObject = new StockBasicPage(authenticatedPage)
    await pageObject.goto()
    await pageObject.expectLoaded()
  })

  test('指标管理模块可加载 @module', async ({ authenticatedPage }) => {
    const pageObject = new IndicatorsPage(authenticatedPage)
    await pageObject.goto()
    await pageObject.expectLoaded()
  })

  test('选股管理（仅单股 000001）可加载 @module', async ({ authenticatedPage }) => {
    const pageObject = new SelectionResultsPage(authenticatedPage)
    // 默认 goto：昨日 + GMS_E2E_SINGLE_STOCK=000001，不触全市场
    await pageObject.goto()
    await pageObject.expectLoaded()
  })

  test('数据源配置模块可加载 @module', async ({ authenticatedPage }) => {
    const pageObject = new DataSourcePage(authenticatedPage)
    await pageObject.goto()
    await pageObject.expectLoaded()
  })

  test('系统监控模块可加载 @module', async ({ authenticatedPage }) => {
    const pageObject = new MonitoringPage(authenticatedPage)
    await pageObject.goto()
    await pageObject.expectLoaded()
  })

  test('预测模型模块可加载 @module', async ({ authenticatedPage }) => {
    const pageObject = new ModelsPage(authenticatedPage)
    await pageObject.goto()
    await pageObject.expectLoaded()
  })

  test('系统日志模块可加载并可切换操作日志 Tab @module', async ({ authenticatedPage }) => {
    const logsPage = new LogsPage(authenticatedPage)
    await logsPage.goto()
    await expect(authenticatedPage.getByText('系统日志')).toBeVisible()
    await logsPage.switchTab('operation')
    await expect(authenticatedPage.getByRole('tab', { name: '操作日志' })).toBeVisible()
  })

  test('报告管理模块默认 Tab 可加载 @module', async ({ authenticatedPage }) => {
    const pageObject = new ReportManagementPage(authenticatedPage)
    await pageObject.goto()
    await pageObject.expectLoaded()
    await expect(authenticatedPage.getByRole('tab', { name: '发送邮箱配置' })).toBeVisible()
  })

  test('报告管理支持 sender/push/logs 三个 Tab query @module', async ({ authenticatedPage }) => {
    const pageObject = new ReportManagementPage(authenticatedPage)

    await pageObject.goto('sender')
    await pageObject.expectLoaded()
    await expect(authenticatedPage).toHaveURL(/tab=sender/)

    await pageObject.goto('push')
    await pageObject.expectLoaded()
    await expect(authenticatedPage).toHaveURL(/tab=push/)

    await pageObject.goto('logs')
    await pageObject.expectLoaded()
    await expect(authenticatedPage).toHaveURL(/tab=logs/)
  })
})
