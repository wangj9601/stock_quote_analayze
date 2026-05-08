import { type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export class IndicatorsPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(): Promise<void> {
    await super.goto('/indicators')
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('tab', { name: '指标数据查询' }),
      this.page.getByRole('tab', { name: '指标数据生成' })
    ])
  }
}
