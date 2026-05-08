import { test as base, expect, type Page, type TestInfo } from '@playwright/test'
import { config } from '../config.js'
import { performLogin } from '../auth/login-manager.js'

type AuthFixture = {
  authenticatedPage: Page
}

export const test = base.extend<AuthFixture>({
  authenticatedPage: async ({ page, context }, use, testInfo: TestInfo) => {
    // 登录 + waitForURL + 侧边栏断言 + storageState，长套件后半段可能较慢
    testInfo.setTimeout(180_000)
    await performLogin(page, context)
    await use(page)
  }
})

export { expect, config }
