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
  await expect(page).toHaveURL(/dashboard/)

  await ensureStorageDir(config.storageStatePath)
  await context.storageState({ path: config.storageStatePath })
}
