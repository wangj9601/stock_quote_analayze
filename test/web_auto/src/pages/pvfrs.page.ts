import type { Locator, Page } from '@playwright/test'

export interface BacktestDetails {
  name: string
  mode: 'single' | 'batch' | 'optimize' | 'portfolio'
  startDate: string
  endDate: string
  stockCode?: string
  stockList?: string
  initialCapital?: number
}

export class PVFRSPage {
  readonly page: Page
  readonly nameInput: Locator
  readonly modeSelect: Locator
  readonly startDatePicker: Locator
  readonly endDatePicker: Locator
  readonly stockCodeInput: Locator
  readonly stockListInput: Locator
  readonly submitButton: Locator
  readonly taskTable: Locator

  constructor(page: Page) {
    this.page = page
    this.nameInput = page.getByPlaceholder('请输入任务名称')
    this.modeSelect = page.locator('.task-form').getByPlaceholder('选择回测模式')
    this.startDatePicker = page.getByPlaceholder('选择开始日期')
    this.endDatePicker = page.getByPlaceholder('选择结束日期')
    this.stockCodeInput = page.getByPlaceholder('例如：000001')
    this.stockListInput = page.getByPlaceholder('请输入股票代码，每行一个')
    this.submitButton = page.getByRole('button', { name: '创建任务' })
    this.taskTable = page.locator('.task-table')
  }

  async goto() {
    await this.page.goto('/pvfrs-management')
  }

  async createTask(details: BacktestDetails) {
    await this.nameInput.fill(details.name)
    
    // 处理 Element Plus Select
    await this.modeSelect.click()
    const modeLabel = {
      single: '单股回测',
      batch: '批量回测',
      optimize: '参数优化',
      portfolio: '组合回测'
    }[details.mode]
    await this.page.locator('ul.el-select-dropdown__list').getByText(modeLabel).click()

    await this.startDatePicker.fill(details.startDate)
    await this.page.keyboard.press('Enter') // 触发日期选择器关闭
    
    await this.endDatePicker.fill(details.endDate)
    await this.page.keyboard.press('Enter')

    if (details.mode === 'single' && details.stockCode) {
      await this.stockCodeInput.fill(details.stockCode)
    } else if (details.mode === 'batch' && details.stockList) {
      await this.stockListInput.fill(details.stockList)
    }

    if (details.initialCapital) {
      // Element Plus InputNumber 可能需要特殊处理
      await this.page.locator('.task-form').getByPlaceholder('100000').fill(details.initialCapital.toString())
    }

    await this.submitButton.click()
  }

  async getTaskStatus(taskIdOrName: string): Promise<string | null> {
    const row = this.taskTable.locator('tr').filter({ hasText: taskIdOrName }).first()
    if (await row.count() === 0) return null
    // 状态在第四列 (根据 Vue 源码 index 0 开始算, prop="status" 是第4个 el-table-column)
    return row.locator('td').nth(3).textContent()
  }

  async waitForTaskCompletion(taskIdOrName: string, timeout = 60000) {
    await this.page.waitForFunction(
      (args) => {
        const rows = Array.from(document.querySelectorAll('.task-table tr'))
        const targetRow = rows.find(r => r.textContent?.includes(args.id))
        if (!targetRow) return false
        const status = targetRow.querySelectorAll('td')[3]?.textContent?.trim()
        return status === '已完成' || status === '已失败'
      },
      { id: taskIdOrName },
      { timeout }
    )
  }
}
