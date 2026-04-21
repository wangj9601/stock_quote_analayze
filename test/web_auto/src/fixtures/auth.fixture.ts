import { test as base, expect, type Page } from '@playwright/test'
import { config } from '../config.js'
import { performLogin } from '../auth/login-manager.js'

type AuthFixture = {
  authenticatedPage: Page
}

export const test = base.extend<AuthFixture>({
  authenticatedPage: async ({ page, context }, use) => {
    await performLogin(page, context)
    await expect(page).toHaveURL(/dashboard/)
    await use(page)
  }
})

export { expect, config }
