import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class DataSourcePage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/datasource')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('heading', { name: '数据源配置' }),
      this.page.getByText('数据源配置功能')
    ])
  }
}
