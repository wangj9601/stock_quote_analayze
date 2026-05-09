import { test as base, expect, type Page, type TestInfo } from '@playwright/test'
import { config } from '../config.js'
import { performLogin } from '../auth/login-manager.js'

type AuthFixture = {
  authenticatedPage: Page
}

export const test = base.extend<AuthFixture>({
  authenticatedPage: async ({ page, context }, use, testInfo: TestInfo) => {
    // 登录 + waitForURL + 侧边栏断言 + storageState；串行冒烟后半段偶发 XHR 挂起，清 Cookie 重试一次
    testInfo.setTimeout(320_000)
    try {
      await performLogin(page, context)
    } catch {
      await context.clearCookies()
      await page.goto('/login', { waitUntil: 'domcontentloaded' })
      await performLogin(page, context)
    }
    await use(page)
  }
})

export { expect, config }
