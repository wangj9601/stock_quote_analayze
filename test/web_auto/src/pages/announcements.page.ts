import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class AnnouncementsPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/announcements')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('heading', { name: '公告发布' }),
      this.page.getByText('公告发布功能')
    ])
  }
}
