import { expect, type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

export type ReportManagementTab = 'sender' | 'push' | 'logs'

export class ReportManagementPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  async goto(tab?: ReportManagementTab): Promise<void> {
    const suffix = tab ? `?tab=${tab}` : ''
    await super.goto(`/report-management${suffix}`)
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('tab', { name: '发送邮箱配置' }),
      this.page.getByRole('tab', { name: '报告推送配置' }),
      this.page.getByRole('tab', { name: '报告发送日志' })
    ])
  }

  async switchTab(tab: ReportManagementTab): Promise<void> {
    const tabNameMap: Record<ReportManagementTab, string> = {
      sender: '发送邮箱配置',
      push: '报告推送配置',
      logs: '报告发送日志'
    }
    await this.page.getByRole('tab', { name: tabNameMap[tab] }).click()
    await expect(this.page).toHaveURL(new RegExp(`tab=${tab}`))
  }
}
