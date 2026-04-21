import { test, expect } from '../src/fixtures/auth.fixture.js'
import { GMSPage } from '../src/pages/gms.page.js'

test.describe('GMS 回测管理核心流程', () => {
  test('应该能切换 GMS 管理标签并打开创建任务对话框 @case', async ({ authenticatedPage }) => {
    const gmsPage = new GMSPage(authenticatedPage)
    await gmsPage.goto()
    
    // 切换到策略配置标签
    await gmsPage.switchTab('config')
    await expect(authenticatedPage.getByText('策略参数配置')).toBeVisible()
    
    // 返回任务管理并尝试打开对话框
    await gmsPage.switchTab('backtest')
    await gmsPage.createTaskButton.click()
    await expect(authenticatedPage.getByText('创建回测任务')).toBeVisible()
    
    // 关闭对话框 (点击取消按钮)
    await authenticatedPage.getByRole('button', { name: '取消' }).click()
  })

  test('应该能成功创建一个 GMS 基本回测任务 @smoke', async ({ authenticatedPage }) => {
    const gmsPage = new GMSPage(authenticatedPage)
    await gmsPage.goto()
    
    const taskName = `GMS_Auto_${Date.now()}`
    await gmsPage.createTask({
      name: taskName,
      stockPool: '中证800' // 假设环境中存在的股票池名称
    })
    
    // 检查列表状态
    const status = await gmsPage.getLatestTaskStatus()
    expect(status).not.toBeNull()
  })
})
