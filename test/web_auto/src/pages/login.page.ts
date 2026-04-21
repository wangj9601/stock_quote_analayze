import type { Locator, Page } from '@playwright/test'

export class LoginPage {
  private readonly usernameInput: Locator
  private readonly passwordInput: Locator
  private readonly submitButton: Locator

  constructor(private readonly page: Page) {
    this.usernameInput = page.locator('#username')
    this.passwordInput = page.locator('#password')
    this.submitButton = page.getByRole('button', { name: /登录|登录中/ })
  }

  async goto(): Promise<void> {
    await this.page.goto('/login')
  }

  async login(username: string, password: string): Promise<void> {
    await this.usernameInput.fill(username)
    await this.passwordInput.fill(password)
    await this.submitButton.click()
  }
}
