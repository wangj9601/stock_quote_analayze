import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class StockBasicPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/stock-basic')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('heading', { name: '股票基本信息管理' }),
      this.page.getByRole('tab', { name: '基本信息查询' })
    ])
  }
}
