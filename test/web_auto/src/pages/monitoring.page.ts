import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class MonitoringPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/monitoring')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('heading', { name: '系统监控' }),
      this.page.getByText('数据库存储占用 (MB)')
    ])
  }
}
