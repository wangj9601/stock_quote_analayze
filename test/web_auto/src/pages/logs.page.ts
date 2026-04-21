import type { Locator, Page } from '@playwright/test'

export class LogsPage {
  readonly page: Page
  readonly historicalTab: Locator
  readonly realtimeTab: Locator
  readonly operationTab: Locator
  readonly logTable: Locator

  constructor(page: Page) {
    this.page = page
    this.historicalTab = page.getByRole('tab', { name: '历史采集日志' })
    this.realtimeTab = page.getByRole('tab', { name: '实时行情采集日志' })
    this.operationTab = page.getByRole('tab', { name: '操作日志' })
    this.logTable = page.locator('.el-table')
  }

  async goto() {
    await this.page.goto('/logs')
  }

  async switchTab(tab: 'historical' | 'realtime' | 'operation') {
    const tabLocator = {
      historical: this.historicalTab,
      realtime: this.realtimeTab,
      operation: this.operationTab
    }[tab]
    await tabLocator.click()
    await this.page.waitForLoadState('networkidle')
  }

  async getLatestLogRowText(): Promise<string | null> {
    const firstRow = this.logTable.locator('tr').nth(1) // skipping header
    return firstRow.textContent()
  }
}
