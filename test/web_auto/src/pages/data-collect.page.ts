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

  constructor(page: Page) {
    this.page = page
  }

  private getAksharePane(): Locator {
    return this.page.getByRole('tabpanel', { name: '历史数据采集-AkShare' }).first()
  }

  private getStartDateInput(): Locator {
    return this.getAksharePane().getByRole('combobox', { name: /开始日期/ }).first()
  }

  private getEndDateInput(): Locator {
    return this.getAksharePane().getByRole('combobox', { name: /结束日期/ }).first()
  }

  async goto() {
    await this.page.goto('/datacollect')
    // 显式切到 A股/AkShare 标签，避免命中其他采集表单
    await this.page.getByRole('tab', { name: 'A股历史数据采集' }).click()
    await this.page.getByRole('tab', { name: '历史数据采集-AkShare' }).click()
    await this.getStartDateInput().waitFor({ state: 'visible' })
  }

  async startHistoricalCollection(config: CollectionConfig) {
    const pane = this.getAksharePane()
    await this.getStartDateInput().fill(config.startDate)
    await this.getEndDateInput().fill(config.endDate)

    // 选择采集类型 (radio)
    const typeLabel = {
      single: '单个股票采集',
      multiple: '多个股票采集',
      all: '全量股票采集'
    }[config.type]
    await pane.getByText(typeLabel, { exact: true }).click()

    if (config.type === 'single' && config.stockCode) {
      await pane.getByPlaceholder('请输入股票代码，例如：000001').fill(config.stockCode)
    } else if (config.type === 'multiple' && config.stockCodesText) {
      await pane.getByPlaceholder('请输入股票代码，每行一个').fill(config.stockCodesText)
    }

    if (config.testMode) {
      await pane.getByText('测试模式（只采集前5只股票）').click()
    }

    // 指标 (checkboxes) 如果有需要可以全选或按需选
    if (config.indicators) {
        if (config.indicators.ma) await pane.getByText('MA移动平均线').click()
        if (config.indicators.macd) await pane.getByText('MACD指标').click()
    }

    const startButton = pane.getByRole('button', { name: '开始采集' })
    if (await startButton.isVisible().catch(() => false)) {
      await startButton.click()
      return
    }

    // 若当前已有任务运行，页面会显示“等待当前任务完成”，此时用例继续做只读校验即可
    await pane.getByText('等待当前任务完成').waitFor({ state: 'visible', timeout: 15000 })
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
