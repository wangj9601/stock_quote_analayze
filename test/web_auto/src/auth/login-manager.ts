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

  // 支持 dev 根路径 `/dashboard` 与生产式 `/admin/dashboard`
  const dashboardRe = /\/(?:admin\/)?dashboard(?:\/|$|\?|#)/i

  // 须在提交前监听 POST（用于失败时区分 401/500）；成功路径只看路由进入 dashboard。
  // 必须 .catch：否则 listener 在超时 reject 时会变成未处理的 Promise（成功路径从不 await 该 listener）。
  const loginPostPromise = page
    .waitForResponse(
      (resp) => {
        if (resp.request().method() !== 'POST') return false
        const u = resp.url()
        if (/oauth/i.test(u)) return false
        return /\/auth\/login\b/i.test(u) || u.includes('admin/auth/login')
      },
      { timeout: 150_000 }
    )
    .catch(() => null as Response | null)

  await loginPage.login(config.username, config.password)

  try {
    await page.waitForURL(dashboardRe, { timeout: 150_000 })
  } catch {
    const postResp = await Promise.race([
      loginPostPromise,
      new Promise<Response | null>((resolve) => setTimeout(() => resolve(null), 8000)),
    ])

    if (postResp && !postResp.ok()) {
      const status = postResp.status()
      const errUi =
        (await page.getByTestId('login-error').textContent().catch(() => null))?.trim() ||
        (await page.locator('[role="alert"], .el-alert, .el-message').first().textContent().catch(() => null))?.trim()
      const serverHint =
        status >= 500
          ? ' 此为服务端错误，请查看后端日志（POST /api/admin/auth/login）：数据库连接、依赖服务或代码异常。'
          : ''
      throw new Error(`登录接口 HTTP ${status}${errUi ? `：${errUi}` : ''}。${serverHint}`.trim())
    }

    if (!dashboardRe.test(page.url())) {
      const buttonText = (await page.getByRole('button', { name: /登录|登录中/ }).first().textContent().catch(() => null))?.trim()
      const loginErr = (await page.getByTestId('login-error').textContent().catch(() => null))?.trim()
      throw new Error(
        `登录后未进入 dashboard。当前URL=${page.url()}，按钮=${buttonText || '未知'}${loginErr ? `，登录错误区=${loginErr}` : ''}。请确认后端已启动、Vite 将 /api 代理到后端（默认管理端 :8001 → /api/admin/auth/login）。`
      )
    }
  }

  // 以侧边栏出现为准，避免仅 URL 匹配但布局未挂载（此时误匹配到别处的「登录」按钮文案）
  await expect(page.locator('.sidebar-nav').first()).toBeVisible({ timeout: 30_000 })
  await page.waitForLoadState('load')

  await ensureStorageDir(config.storageStatePath)
  await context.storageState({ path: config.storageStatePath })
}
