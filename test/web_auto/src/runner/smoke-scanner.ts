import { expect, type Page } from '@playwright/test'

export interface SmokeScanResult {
  menu: string
  ok: boolean
  error?: string
}

export async function runSmokeScan(page: Page): Promise<SmokeScanResult[]> {
  const results: SmokeScanResult[] = []
  const menuItems = page.locator('.sidebar-nav .nav-item')
  const count = await menuItems.count()

  for (let i = 0; i < count; i += 1) {
    const link = menuItems.nth(i)
    const menu = (await link.innerText()).trim()

    try {
      await link.click()
      await page.waitForLoadState('networkidle')
      await expect(page.locator('.admin-content')).toBeVisible()
      results.push({ menu, ok: true })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      results.push({ menu, ok: false, error: message })
    }
  }

  return results
}
