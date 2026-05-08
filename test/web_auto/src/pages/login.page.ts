import type { Locator, Page } from '@playwright/test'

export class LoginPage {
  private readonly usernameInput: Locator
  private readonly passwordInput: Locator

  constructor(private readonly page: Page) {
    this.usernameInput = page.locator('#username')
    this.passwordInput = page.locator('#password')
  }

  async goto(): Promise<void> {
    await this.page.goto('/login')
  }

  async login(username: string, password: string): Promise<void> {
    await this.usernameInput.fill(username)
    await this.passwordInput.fill(password)
    // 避免点击 type=submit 时 Playwright 等待「整页导航」直至超时（管理端为 Vue SPA + axios，无 document 导航）
    await this.passwordInput.press('Enter')
  }
}
