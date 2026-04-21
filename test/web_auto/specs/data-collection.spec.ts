import { test, expect } from '../src/fixtures/auth.fixture.js'
import { DataCollectPage } from '../src/pages/data-collect.page.js'

test.describe('数据采集核心流程', () => {
  test('应该能成功启动一个测试模式的采集任务 @case', async ({ authenticatedPage }) => {
    const dataPage = new DataCollectPage(authenticatedPage)
    
    // 1. 进入数据采集页
    await dataPage.goto()
    
    // 2. 启动采集 (测试模式)
    await dataPage.startHistoricalCollection({
      startDate: '2024-01-01',
      endDate: '2024-01-10',
      type: 'single',
      stockCode: '000001',
      testMode: true
    })

    // 3. 验证任务出现在列表中
    await expect(authenticatedPage.getByText('任务ID:')).toBeVisible()
    
    // 4. 验证进度条出现
    const progress = await dataPage.getLatestTaskProgress()
    expect(progress).toBeGreaterThanOrEqual(0)
    
    // 5. 等待完成（测试模式通常很快）
    // await dataPage.waitForCollectionCompletion(60000)
    // await expect(authenticatedPage.getByText('已完成')).toBeVisible()
  })
})
