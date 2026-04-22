import type { Locator, Page } from '@playwright/test'

export class QuotesPage {
  readonly page: Page
  readonly mainTabAShare: Locator
  readonly mainTabHKShare: Locator
  readonly searchInputA: Locator
  readonly searchInputHK: Locator
  readonly refreshButton: Locator

  constructor(page: Page) {
    this.page = page
    this.mainTabAShare = page.getByRole('tab', { name: 'A股数据' })
    this.mainTabHKShare = page.getByRole('tab', { name: '港股数据' })
    this.searchInputA = page.locator('input[placeholder="搜索股票代码或名称"]:visible').first()
    this.searchInputHK = page.getByPlaceholder('搜索港股代码或名称')
    this.refreshButton = page.getByRole('button', { name: '刷新数据' })
  }

  async goto() {
    await this.page.goto('/quotes')
  }

  async switchToMarket(market: 'A' | 'HK') {
    if (market === 'A') await this.mainTabAShare.click()
    else await this.mainTabHKShare.click()
  }

  async searchStock(market: 'A' | 'HK', keyword: string) {
    const input = market === 'A' ? this.searchInputA : this.searchInputHK
    await input.fill(keyword)
    await this.page.keyboard.press('Enter')
    await this.page.waitForLoadState('networkidle')
  }

  async isStockInList(code: string): Promise<boolean> {
    const table = this.page.locator('.el-table__body-wrapper table')
    return (await table.locator('tr').filter({ hasText: code }).count()) > 0
  }
}
