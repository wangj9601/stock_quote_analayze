import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class ContentPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/content')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('heading', { name: '内容管理' }),
      this.page.getByText('内容管理功能')
    ])
  }
}
