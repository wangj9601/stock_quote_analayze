import { expect, type Page } from '@playwright/test'
import { BaseAdminPage } from './base-admin.page'

/**
 * GMS 相关 E2E 固定单股代码（对接后端查询参数 `code`）。
 * 所有「选股结果 / 策略管理」冒烟仅使用该标的，禁止默认全市场。
 */
export const GMS_E2E_SINGLE_STOCK = '000001'

/** 本地日历昨天 YYYY-MM-DD，用于 GMS 单日参数，避免冒烟时用默认区间拉全市场大量计算 */
export function yesterdayLocalIso(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export class SelectionResultsPage extends BaseAdminPage {
  constructor(page: Page) {
    super(page)
  }

  /**
   * 默认：昨日 + {@link GMS_E2E_SINGLE_STOCK}，与后端 `date` + `code` 一致，仅单股、不触全市场。
   * @param options.strategyDate 策略起始交易日期；省略则用 {@link yesterdayLocalIso}。
   * @param options.singleStockCode 限定股票代码；省略则用 {@link GMS_E2E_SINGLE_STOCK}。
   */
  async goto(options?: { strategyDate?: string; singleStockCode?: string }): Promise<void> {
    await super.goto('/selection-results')
    const strategyDate = options?.strategyDate ?? yesterdayLocalIso()
    const singleStockCode = options?.singleStockCode ?? GMS_E2E_SINGLE_STOCK
    await this.setStrategyStartDate(strategyDate)
    await this.setSingleStockCode(singleStockCode)
  }

  /** 对应 admin 选股结果页 GMS 参数「策略起始交易日期」（`gmsForm.start_date` → API `date`） */
  async setStrategyStartDate(isoDate: string): Promise<void> {
    const row = this.page.locator('.param-row').filter({ hasText: '策略起始交易日期' })
    await expect(row).toBeVisible({ timeout: 15_000 })
    const input = row.locator('input[type="date"]').first()
    await input.fill(isoDate)
  }

  /** 对应「限定股票代码（可选）」→ 接口 `code`，仅计算该只股票 */
  async setSingleStockCode(code: string): Promise<void> {
    const row = this.page.locator('.param-row').filter({ hasText: '限定股票代码' })
    await expect(row).toBeVisible({ timeout: 15_000 })
    const input = row.locator('input').first()
    await input.fill(code)
  }

  async expectLoaded(): Promise<void> {
    await this.expectOneVisible([
      this.page.getByRole('heading', { name: 'GMS策略管理' }),
      this.page.getByRole('tab', { name: '选股结果' })
    ])
  }
}
