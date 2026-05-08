import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class ModelsPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/models')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('heading', { name: '预测模型' }),
      this.page.getByText('预测模型功能')
    ])
  }
}
