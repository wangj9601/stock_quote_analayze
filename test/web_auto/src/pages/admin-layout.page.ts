import type { Locator, Page } from '@playwright/test'

export class AdminLayoutPage {
  readonly sidebarLinks: Locator

  constructor(private readonly page: Page) {
    this.sidebarLinks = page.locator('.sidebar-nav .nav-item')
  }

  async gotoDashboard(): Promise<void> {
    await this.page.goto('/dashboard')
  }

  async openMenuByText(menuText: string): Promise<void> {
    await this.page.getByRole('link', { name: menuText }).click()
  }
}
