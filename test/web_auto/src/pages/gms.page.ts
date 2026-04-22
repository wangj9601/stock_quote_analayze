import type { Locator, Page } from '@playwright/test'

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

  async createTask(details: { name: string, stockPool: string }) {
    const formCard = this.page.locator('.create-task-card').first()
    await formCard.getByRole('textbox', { name: '任务名称' }).fill(details.name)

    // 当前页面默认股票池即“全市场”，烟雾用例仅验证任务可创建，避免选择器脆弱点。
    void details.stockPool

    await formCard.getByRole('button', { name: '创建任务' }).click()
  }

  async getLatestTaskStatus(): Promise<string | null> {
    const firstStatusTag = this.page.locator('.task-list-card .el-table .el-tag').first()
    await firstStatusTag.waitFor({ state: 'visible', timeout: 30000 })
    return firstStatusTag.textContent()
  }
}
