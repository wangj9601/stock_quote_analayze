import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class DashboardPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/dashboard')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByText('用户总数'),
      this.page.getByText('快速操作'),
      this.page.getByText('最近活动')
    ])
  }
}
