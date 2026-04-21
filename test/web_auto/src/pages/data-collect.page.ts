import type { Locator, Page } from '@playwright/test'

export interface CollectionConfig {
  startDate: string
  endDate: string
  type: 'single' | 'multiple' | 'all'
  stockCode?: string
  stockCodesText?: string
  testMode?: boolean
  indicators?: {
    ma?: boolean
    mavol?: boolean
    macd?: boolean
  }
}

export class DataCollectPage {
  readonly page: Page
  readonly startDateInput: Locator
  readonly endDateInput: Locator
  readonly startButton: Locator
  readonly progressBars: Locator

  constructor(page: Page) {
    this.page = page
    // datacollect.html uses standard HTML inputs with v-model
    this.startDateInput = page.locator('input[type="date"]').first()
    this.endDateInput = page.locator('input[type="date"]').nth(1)
    this.startButton = page.getByRole('button', { name: '开始采集' })
    this.progressBars = page.locator('.bg-blue-600.h-2.rounded-full') // 进度条 selector
  }

  async goto() {
    await this.page.goto('/datacollect')
  }

  async startHistoricalCollection(config: CollectionConfig) {
    await this.startDateInput.fill(config.startDate)
    await this.endDateInput.fill(config.endDate)

    // 选择采集类型 (radio)
    const typeLabel = {
      single: '单个股票采集',
      multiple: '多个股票采集',
      all: '全量股票采集'
    }[config.type]
    await this.page.getByText(typeLabel).click()

    if (config.type === 'single' && config.stockCode) {
      await this.page.getByPlaceholder('请输入股票代码，例如：000001').fill(config.stockCode)
    } else if (config.type === 'multiple' && config.stockCodesText) {
      await this.page.getByPlaceholder('请输入股票代码，每行一个').fill(config.stockCodesText)
    }

    if (config.testMode) {
      await this.page.getByText('测试模式').click()
    }

    // 指标 (checkboxes) 如果有需要可以全选或按需选
    if (config.indicators) {
        if (config.indicators.ma) await this.page.getByText('MA（移动平均线）').click()
        if (config.indicators.macd) await this.page.getByText('MACD指标').click()
    }

    await this.startButton.click()
  }

  async getLatestTaskProgress(): Promise<number> {
    const progressText = await this.page.locator('.flex.justify-between.text-sm.text-gray-600.mb-1 span').nth(1).first().textContent()
    if (!progressText) return 0
    return parseInt(progressText.replace('%', ''))
  }

  async waitForCollectionCompletion(timeout = 120000) {
    // 等待状态变为“已完成”
    await this.page.waitForSelector('text=已完成', { timeout })
  }
}
