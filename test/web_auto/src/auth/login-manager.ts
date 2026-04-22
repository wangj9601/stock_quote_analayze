import { expect, type BrowserContext, type Page } from '@playwright/test'
import { existsSync } from 'node:fs'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { config } from '../config'
import { LoginPage } from '../pages/login.page'

async function ensureStorageDir(storageStatePath: string): Promise<void> {
  const dir = path.dirname(storageStatePath)
  await mkdir(dir, { recursive: true })
}

export async function performLogin(page: Page, context: BrowserContext): Promise<void> {
  const loginPage = new LoginPage(page)

  if (config.loginMode === 'storage_state' && existsSync(config.storageStatePath)) {
    return
  }

  if (config.loginMode === 'manual_captcha') {
    await loginPage.goto()
    await page.pause()
    await expect(page).toHaveURL(/dashboard/)
    await ensureStorageDir(config.storageStatePath)
    await context.storageState({ path: config.storageStatePath })
    return
  }

  if (!config.username || !config.password) {
    throw new Error('缺少 WEB_USERNAME 或 WEB_PASSWORD，无法执行账号密码登录。')
  }

  if (config.captchaBypassHeaderKey && config.captchaBypassHeaderValue) {
    await context.setExtraHTTPHeaders({
      [config.captchaBypassHeaderKey]: config.captchaBypassHeaderValue
    })
  }

  await loginPage.goto()
  await loginPage.login(config.username, config.password)
  
  // 等待 URL 变更并进入稳定状态
  try {
    await expect(page).toHaveURL(/dashboard/, { timeout: 45_000 })
  } catch {
    const buttonText = (await page.getByRole('button', { name: /登录|登录中/ }).first().textContent().catch(() => null))?.trim()
    const alertText = (await page.locator('[role="alert"], .el-alert, .el-message').first().textContent().catch(() => null))?.trim()
    throw new Error(
      `登录后 45 秒仍未跳转到 dashboard。当前URL=${page.url()}，按钮=${buttonText || '未知'}${alertText ? `，提示=${alertText}` : ''}`
    )
  }
  await page.waitForLoadState('networkidle')

  await ensureStorageDir(config.storageStatePath)
  await context.storageState({ path: config.storageStatePath })
}
