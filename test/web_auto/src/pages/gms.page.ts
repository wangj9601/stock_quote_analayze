import type { Locator, Page } from '@playwright/test'

export class GMSPage {
  readonly page: Page
  readonly backtestTab: Locator
  readonly reportsTab: Locator
  readonly configTab: Locator
  readonly createTaskButton: Locator

  constructor(page: Page) {
    this.page = page
    this.backtestTab = page.locator('.management-tabs').getByText('回测任务管理')
    this.reportsTab = page.locator('.management-tabs').getByText('报告与分析')
    this.configTab = page.locator('.management-tabs').getByText('策略配置')
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
    await this.createTaskButton.click()
    const dialog = this.page.getByRole('dialog')
    await dialog.locator('input[placeholder*="任务名称"]').fill(details.name)
    
    // 假设是基础的选择器
    await dialog.locator('input[placeholder*="选择股票池"]').click()
    await this.page.locator('ul.el-select-dropdown__list').getByText(details.stockPool).click()
    
    await dialog.getByRole('button', { name: '确定' }).click()
  }

  async getLatestTaskStatus(): Promise<string | null> {
    const table = this.page.locator('.backtest-management .el-table')
    return table.locator('tr').first().locator('td').nth(4).textContent() // 假设状态在第5列
  }
}
