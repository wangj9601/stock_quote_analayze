import { expect, type Locator, type Page } from '@playwright/test'
import { GMS_E2E_SINGLE_STOCK } from './selection-results.page.js'

export class GMSPage {
  readonly page: Page
  readonly backtestTab: Locator
  readonly reportsTab: Locator
  readonly configTab: Locator
  readonly createTaskButton: Locator

  constructor(page: Page) {
    this.page = page
    this.backtestTab = page.getByRole('tab', { name: '回测任务管理' })
    this.reportsTab = page.getByRole('tab', { name: '报告与分析' })
    this.configTab = page.getByRole('tab', { name: '策略配置' })
    this.createTaskButton = page.getByRole('button', { name: '创建任务' })
  }

  async goto() {
    await this.page.goto('/gms-management')
  }

  async switchTab(tabName: 'backtest' | 'reports' | 'config') {
    const tab = {
      backtest: this.backtestTab,
      reports: this.reportsTab,
      config: this.configTab
    }[tabName]
    await tab.click()
  }

  /**
   * 创建回测任务：固定「单股回测」+ {@link GMS_E2E_SINGLE_STOCK}，禁止默认全市场池。
   */
  async createTask(details: { name: string; singleStockCode?: string }) {
    const code = details.singleStockCode ?? GMS_E2E_SINGLE_STOCK
    const formCard = this.page.locator('.create-task-card').first()
    await formCard.getByRole('textbox', { name: '任务名称' }).fill(details.name)

    const poolSelect = formCard.locator('.el-form-item').filter({ hasText: '股票池' }).locator('.el-select')
    await poolSelect.click()
    await this.page.getByRole('option', { name: '单股回测' }).click()
    const codeInput = formCard.getByRole('textbox', { name: '股票代码' })
    await expect(codeInput).toBeVisible()
    await codeInput.fill(code)

    const createBtn = formCard.getByRole('button', { name: '创建任务' })
    await Promise.all([
      this.page.waitForResponse(
        (res) =>
          res.request().method() === 'POST' &&
          res.url().includes('/api/admin/gms/backtests') &&
          res.ok(),
        { timeout: 120_000 }
      ),
      createBtn.click()
    ])

    await expect(this.page.locator('.task-list-card .el-table tbody tr').first()).toBeVisible({
      timeout: 60_000
    })
  }

  async getLatestTaskStatus(): Promise<string | null> {
    const firstStatusTag = this.page.locator('.task-list-card .el-table .el-tag').first()
    await firstStatusTag.waitFor({ state: 'visible', timeout: 30000 })
    return firstStatusTag.textContent()
  }
}
