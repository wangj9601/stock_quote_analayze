import { test, expect } from '../src/fixtures/auth.fixture.js'
import { PVFRSPage } from '../src/pages/pvfrs.page.js'

test.describe('PVFRS 策略管理核心流程', () => {
  test('应该能成功创建一个单股回测任务 @case', async ({ authenticatedPage }) => {
    const pvfrsPage = new PVFRSPage(authenticatedPage)
    
    // 1. 进入 PVFRS 管理页
    await pvfrsPage.goto()
    
    // 2. 创建一个单股回测任务
    const taskName = `AutoTest_${Date.now()}`
    await pvfrsPage.createTask({
      name: taskName,
      mode: 'single',
      startDate: '2024-01-01',
      endDate: '2024-01-31',
      stockCode: '000001',
      initialCapital: 100000
    })

    // 3. 验证列表出现该任务
    const status = await pvfrsPage.getTaskStatus(taskName)
    expect(status).not.toBeNull()
    // 初始状态通常是 '等待中' 或 '运行中'
    expect(['等待中', '运行中', '已完成']).toContain(status?.trim())

    // 4. 等待一段时间或验证状态更新（可选，视后端速度而定）
    // await pvfrsPage.waitForTaskCompletion(taskName, 30000)
    // const finalStatus = await pvfrsPage.getTaskStatus(taskName)
    // expect(finalStatus).toBe('已完成')
  })
})
