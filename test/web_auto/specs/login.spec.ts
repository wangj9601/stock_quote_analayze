import { test, expect } from '@playwright/test'
import { LoginPage } from '../src/pages/login.page.js'

test.describe('登录与路由守卫 @module', () => {
  test('未登录访问受保护路由应重定向到登录页 @module @smoke', async ({ page }) => {
    await page.goto('/users')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: '管理后台登录' })).toBeVisible()
  })

  test('错误凭据登录后应停留在登录页并显示错误提示 @module', async ({ page }) => {
    test.setTimeout(120_000)
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.login(`invalid_user_${Date.now()}`, 'invalid_password')

    await expect(page).toHaveURL(/\/login/)
    const err = page.getByTestId('login-error')
    await expect(err).toBeVisible({ timeout: 30_000 })
    await expect(err).not.toHaveText('')
  })
})
