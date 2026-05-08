import { expect, type Locator, type Page } from '@playwright/test'

export class BaseAdminPage {
  constructor(protected readonly page: Page) {}

  async goto(path: string): Promise<void> {
    await this.page.goto(path)
    await this.expectAdminContentReady()
  }

  async expectAdminContentReady(): Promise<void> {
    await expect(this.page.locator('.admin-content')).toBeVisible()
  }

  async expectOneVisible(candidates: Locator[]): Promise<void> {
    const errors: string[] = []
    for (const locator of candidates) {
      try {
        await expect(locator.first()).toBeVisible({ timeout: 8_000 })
        return
      } catch (err) {
        errors.push(String(err))
      }
    }
    throw new Error(`页面断言锚点均不可见: ${errors.join(' | ')}`)
  }
}
